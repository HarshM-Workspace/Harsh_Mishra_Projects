"""
github_extractor.py
-------------------
Main entry point for the GitHub ecosystem extraction pipeline.

Per github_ecosystem_process.md:
  - Fetches Top 100 repositories per technology sorted by stars descending
  - Technology sources: tech_dimension_table.json (SO Survey) + emerging_tech.json
  - Classifies every repo (quality_class, quality_score) using classifier.py
  - Scores technology relevance (relevance_score, is_usable) using classifier.py
  - Computes ecosystem snapshot metrics using snapshot.py
  - Writes output to:
      raw/github/<YYYY-MM-DD>/repos/<tech_slug>.json       ← per-repo records
      raw/github/<YYYY-MM-DD>/snapshots/<tech_slug>.json   ← snapshot metrics
      raw/github/<YYYY-MM-DD>_manifest.json                ← run summary

Idempotency:
  - Skips a technology if today's repos/<tech_slug>.json already exists.
  - Re-running the script after a partial failure picks up where it left off.

Rate-limit safety:
  - Checks X-RateLimit-Remaining header after every Search API response.
  - Sleeps RATE_LIMIT_SLEEP_SECONDS when remaining drops below RATE_LIMIT_BUFFER.
  - Uses authenticated requests (token from .env) — 5,000 req/hour limit.

Usage:
  python github_extractor.py

  Optional:
  python github_extractor.py --date 2026-08-01   # force a past snapshot date
  python github_extractor.py --tech python        # run only one technology (by slug)
  python github_extractor.py --dry-run            # print tech list, skip API calls
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Ensure sibling modules (classifier, config, snapshot) are importable
# regardless of the working directory the script is launched from.
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from classifier import classify_repo, score_relevance
from config import (
    API_TIMEOUT,
    GITHUB_API_BASE,
    PER_PAGE,
    RATE_LIMIT_BUFFER,
    RATE_LIMIT_SLEEP_SECONDS,
    REPOS_PER_TECH,
)
from snapshot import compute_snapshot, compute_trend

# ---------------------------------------------------------------------------
# Paths — all relative to this script's directory
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_RAW_ROOT = _HERE.parent                        # raw/
_TECH_TABLE = _RAW_ROOT / "tech_dimension_table.json"
_EMERGING_TECH = _RAW_ROOT / "emerging_tech.json"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv(_HERE.parent.parent / ".env")       # Labor-Market-Intelligence/.env
_TOKEN = os.getenv("GitHub_access_token") or os.getenv("GITHUB_ACCESS_TOKEN")

if not _TOKEN:
    print("[WARN] No GitHub token found in .env — running unauthenticated (60 req/hour).")
    GITHUB_HEADERS: dict[str, str] = {"Accept": "application/vnd.github+json"}
else:
    GITHUB_HEADERS = {
        "Authorization": f"token {_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


# ---------------------------------------------------------------------------
# Tech list builder
# ---------------------------------------------------------------------------

def _load_tech_table(path: Path) -> list[dict[str, Any]]:
    """
    Load tech_dimension_table.json.
    Returns a list of dicts, each with keys: StackOverflow, Github_Topic.
    Only includes rows where Github_Topic is not None.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    valid = [row for row in raw if row.get("Github_Topic")]
    skipped = len(raw) - len(valid)
    if skipped:
        print(f"  [INFO] tech_dimension_table: {skipped} rows skipped (no Github_Topic)")
    return valid


def _load_emerging_tech(path: Path) -> list[dict[str, Any]]:
    """
    Load emerging_tech.json.
    Returns a list of dicts, each with keys: canonical_name, github_topic,
    aliases, category, status. Only includes status=='active' entries.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    techs = data.get("technologies", [])
    active = [t for t in techs if t.get("status") == "active"]
    skipped = len(techs) - len(active)
    if skipped:
        print(f"  [INFO] emerging_tech: {skipped} rows skipped (not active)")
    return active


def build_unified_tech_list(
    so_table: list[dict],
    emerging: list[dict],
) -> list[dict[str, Any]]:
    """
    Merge SO Survey techs and emerging techs into a single normalised list.

    Unified tech dict schema:
      canonical_name  str
      github_topic    str    ← slug used in GitHub Search API query
      aliases         list[str]
      languages       list[str]  ← relevant GitHub language values for relevance scoring
      topics          list[str]  ← additional relevant topic slugs for relevance scoring
      source          str   ← 'so_survey' | 'emerging_tech'

    Deduplication: if the same github_topic slug appears in both sources,
    keep the emerging_tech entry (it has more metadata: aliases, category).
    """
    unified: dict[str, dict] = {}  # key: github_topic slug

    # Add SO Survey techs first
    for row in so_table:
        slug = row["Github_Topic"]
        canonical = row["StackOverflow"]
        unified[slug] = {
            "canonical_name": canonical,
            "github_topic":   slug,
            "aliases":        [],
            "languages":      [],      # SO table has no language metadata; populated below
            "topics":         [slug],  # the slug itself is the primary topic
            "source":         "so_survey",
        }

    # Add/override with emerging techs (richer metadata)
    for tech in emerging:
        slug = tech.get("github_topic")
        if not slug:
            continue
        canonical = tech["canonical_name"]
        aliases = tech.get("aliases") or []
        # emerging_tech.json has no explicit languages field; infer from slug for common cases
        unified[slug] = {
            "canonical_name": canonical,
            "github_topic":   slug,
            "aliases":        aliases,
            "languages":      [],      # can be extended by user via emerging_tech.json later
            "topics":         [slug] + [a.lower().replace(" ", "-") for a in aliases if a],
            "source":         "emerging_tech",
            "category":       tech.get("category", ""),
        }

    return list(unified.values())


# ---------------------------------------------------------------------------
# GitHub Search API
# ---------------------------------------------------------------------------

def _check_rate_limit(response: requests.Response) -> None:
    """
    Inspect X-RateLimit-Remaining header. Sleep if buffer threshold hit.
    This is called after every successful Search API response.
    """
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is None:
        return
    remaining_int = int(remaining)
    if remaining_int < RATE_LIMIT_BUFFER:
        reset_ts = response.headers.get("X-RateLimit-Reset")
        if reset_ts:
            wait = min(65, max(1, int(reset_ts) - int(time.time()) + 2))
        else:
            wait = RATE_LIMIT_SLEEP_SECONDS
        print(f"  [RATE LIMIT] {remaining_int} requests remaining — sleeping {wait}s")
        time.sleep(wait)


def fetch_repos_for_tech(tech: dict[str, Any]) -> tuple[list[dict], int]:
    """
    Fetch the top REPOS_PER_TECH repositories for a technology via GitHub Search API.

    Returns:
        (repos, observed_count)
        repos          — list of raw repo dicts from the API (up to REPOS_PER_TECH)
        observed_count — total_count from the first page response (before pagination)

    Pagination: GitHub Search API max per_page=100, so 100 repos = 1 page.
    If REPOS_PER_TECH > 100 this would need multi-page — currently it's exactly 100.
    """
    slug = tech["github_topic"]
    url = f"{GITHUB_API_BASE}/search/repositories"
    params = {
        "q":        f"topic:{slug}",
        "sort":     "stars",
        "order":    "desc",
        "per_page": min(REPOS_PER_TECH, 100),  # GitHub max per_page
        "page":     1,
    }

    repos: list[dict] = []
    observed_count = 0
    pages_needed = -(-REPOS_PER_TECH // 100)  # ceiling division → pages needed

    for page_num in range(1, pages_needed + 1):
        params["page"] = page_num
        try:
            resp = requests.get(url, headers=GITHUB_HEADERS, params=params, timeout=API_TIMEOUT)
        except requests.exceptions.Timeout:
            print(f"  [WARN] Timeout fetching page {page_num} for '{slug}'")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"  [WARN] Connection error for '{slug}': {e}")
            break

        if resp.status_code == 403:
            # Rate limit exceeded — wait and retry once
            print(f"  [WARN] 403 on page {page_num} for '{slug}' — rate limited, sleeping 60s")
            time.sleep(60)
            try:
                resp = requests.get(url, headers=GITHUB_HEADERS, params=params, timeout=API_TIMEOUT)
            except Exception:
                break

        if resp.status_code != 200:
            print(f"  [WARN] HTTP {resp.status_code} for '{slug}' page {page_num}")
            break

        _check_rate_limit(resp)

        data = resp.json()
        if page_num == 1:
            observed_count = data.get("total_count", 0)

        items = data.get("items", [])
        repos.extend(items)

        if len(items) < params["per_page"]:
            # Fewer results than requested — we've exhausted available repos
            break

        # Respect a small delay between pages to avoid burst-triggering secondary rate limits
        time.sleep(1)

    return repos[:REPOS_PER_TECH], observed_count


# ---------------------------------------------------------------------------
# Previous snapshot loader (for turnover calculation)
# ---------------------------------------------------------------------------

def _load_prev_snapshot_ids(snapshot_dir: Path, tech_slug: str) -> set[int]:
    """
    Find the most recent previous snapshot for a technology and return
    the set of usable repo IDs it contains.

    Walks snapshot_dir parent (raw/github/) looking for the most recent
    date directory that has a snapshots/<tech_slug>.json with _usable_repo_ids.
    """
    github_raw = snapshot_dir.parent.parent  # raw/github/
    # Find all date dirs older than snapshot_dir
    current_date_name = snapshot_dir.name
    date_dirs = sorted(
        [d for d in github_raw.iterdir() if d.is_dir() and d.name < current_date_name],
        reverse=True,  # most recent first
    )
    for date_dir in date_dirs:
        snap_file = date_dir / "snapshots" / f"{tech_slug}.json"
        if snap_file.exists():
            try:
                with open(snap_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ids = data.get("_usable_repo_ids", [])
                return set(ids)
            except (json.JSONDecodeError, OSError):
                continue
    return set()


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Single-technology pipeline
# ---------------------------------------------------------------------------

def process_technology(
    tech: dict[str, Any],
    snapshot_date: str,
    output_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Full pipeline for one technology:
      1. Fetch repos (or skip if already on disk)
      2. Classify quality + score relevance
      3. Compute ecosystem snapshot
      4. Write repos JSON + snapshot JSON

    Returns a result dict for the manifest.
    """
    slug = tech["github_topic"]
    canonical = tech["canonical_name"]

    repos_path = output_dir / "repos" / f"{slug}.json"
    snap_path = output_dir / "snapshots" / f"{slug}.json"

    # Idempotency check: skip if today's repos file already exists
    if repos_path.exists():
        print(f"  [SKIP] {canonical} — already fetched today")
        return {"technology": canonical, "slug": slug, "status": "skipped"}

    if dry_run:
        print(f"  [DRY RUN] Would fetch: {canonical} (topic:{slug})")
        return {"technology": canonical, "slug": slug, "status": "dry_run"}

    print(f"  [FETCH] {canonical} (topic:{slug})")
    raw_repos, observed_count = fetch_repos_for_tech(tech)

    if not raw_repos:
        print(f"  [WARN] No repos returned for '{slug}'")
        _write_json(repos_path, [])
        _write_json(snap_path, {
            "technology": canonical, "snapshot_date": snapshot_date,
            "observed_repositories": observed_count, "usable_repositories": 0,
            "median_stars": 0, "median_forks": 0, "active_repository_ratio": 0,
            "top1_star_concentration": 0, "top5_star_concentration": 0,
            "new_to_top100_ratio": None,
        })
        return {"technology": canonical, "slug": slug, "status": "empty", "observed": 0}

    # Classify and score every repo
    classified_repos: list[dict] = []
    for repo in raw_repos:
        quality_fields = classify_repo(repo)
        relevance_fields = score_relevance(repo, tech)
        enriched = {**repo, **quality_fields, **relevance_fields}
        classified_repos.append(enriched)

    # Load previous snapshot IDs for turnover calculation
    prev_ids = _load_prev_snapshot_ids(output_dir, slug)

    # Compute ecosystem snapshot
    snap = compute_snapshot(
        technology=canonical,
        snapshot_date=snapshot_date,
        repos=classified_repos,
        prev_repo_ids=prev_ids,
        observed_count=observed_count,
    )

    # Write outputs
    _write_json(repos_path, classified_repos)
    _write_json(snap_path, snap)

    usable = snap["usable_repositories"]
    print(f"  [OK] {canonical}: {len(raw_repos)} fetched, {usable} usable — snapshot written")

    return {
        "technology":    canonical,
        "slug":          slug,
        "status":        "ok",
        "observed":      observed_count,
        "fetched":       len(raw_repos),
        "usable":        usable,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub ecosystem extractor")
    parser.add_argument("--date", default=None,
                        help="Override snapshot date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--tech", default=None,
                        help="Run only the tech with this GitHub topic slug.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print tech list without making API calls.")
    args = parser.parse_args()

    snapshot_date = args.date or date.today().isoformat()
    print(f"\n=== GitHub Ecosystem Extractor — snapshot: {snapshot_date} ===\n")

    # Validate and load tech sources
    for label, path in [("tech_dimension_table", _TECH_TABLE), ("emerging_tech", _EMERGING_TECH)]:
        if not path.exists():
            sys.exit(f"[ERROR] {label} not found: {path}")

    so_table  = _load_tech_table(_TECH_TABLE)
    emerging  = _load_emerging_tech(_EMERGING_TECH)
    tech_list = build_unified_tech_list(so_table, emerging)
    print(f"Loaded {len(so_table)} SO Survey techs + {len(emerging)} emerging techs "
          f"-> {len(tech_list)} unique slugs\n")

    # Filter to single tech if --tech flag given
    if args.tech:
        tech_list = [t for t in tech_list if t["github_topic"] == args.tech]
        if not tech_list:
            sys.exit(f"[ERROR] No tech found with github_topic='{args.tech}'")
        print(f"[FILTER] Running only: {tech_list[0]['canonical_name']}\n")

    # Output directory for this snapshot date
    # _HERE = raw/github/ → output lands in raw/github/<YYYY-MM-DD>/
    output_dir = _HERE / snapshot_date

    results: list[dict] = []
    errors: list[str] = []

    for i, tech in enumerate(tech_list, start=1):
        print(f"[{i}/{len(tech_list)}] ", end="")
        try:
            result = process_technology(tech, snapshot_date, output_dir, dry_run=args.dry_run)
            results.append(result)
        except Exception as e:
            slug = tech.get("github_topic", "?")
            print(f"  [ERROR] {slug}: {e}")
            errors.append(f"{slug}: {e}")
            results.append({
                "technology": tech.get("canonical_name"), "slug": slug,
                "status": "error", "error": str(e),
            })

    # Write manifest
    ok_count    = sum(1 for r in results if r.get("status") == "ok")
    skip_count  = sum(1 for r in results if r.get("status") == "skipped")
    error_count = len(errors)

    manifest = {
        "snapshot_date":    snapshot_date,
        "run_timestamp":    datetime.now(timezone.utc).isoformat(),
        "total_techs":      len(tech_list),
        "ok":               ok_count,
        "skipped":          skip_count,
        "errors":           error_count,
        "error_details":    errors,
        "results":          results,
    }
    manifest_path = _HERE / f"{snapshot_date}_manifest.json"
    _write_json(manifest_path, manifest)

    print(f"\n=== Done: {ok_count} ok | {skip_count} skipped | {error_count} errors ===")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
