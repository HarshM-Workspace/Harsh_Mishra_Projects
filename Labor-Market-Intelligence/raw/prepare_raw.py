"""
prepare_raw.py
--------------
One-time data preparation script. Run before dbt:
  python prepare_raw.py

Produces:
  raw/stackoverflow/filtered_survey.parquet  — slim SO survey (tech columns only)
  raw/github/all_repos.parquet               — all repos across all snapshot dates
  raw/github/all_snapshots.parquet           — all ecosystem snapshots across dates

These parquet files are what dbt reads via read_parquet() / read_csv_auto().

Idempotent: safe to re-run; overwrites outputs.
"""

import json
import glob
import os
from pathlib import Path

import pandas as pd
import duckdb

BASE = Path(__file__).parent

# ---------------------------------------------------------------------------
# 1. Stack Overflow survey → filtered_survey.parquet
# ---------------------------------------------------------------------------
SURVEY_CSV = BASE / "stackoverflow" / "survey_result.csv"
SURVEY_OUT  = BASE / "stackoverflow" / "filtered_survey.parquet"

TECH_COLS = [
    "ResponseId",
    "LanguageHaveWorkedWith", "LanguageWantToWorkWith",
    "DatabaseHaveWorkedWith", "DatabaseWantToWorkWith",
    "WebframeHaveWorkedWith", "WebframeWantToWorkWith",
    "PlatformHaveWorkedWith", "PlatformWantToWorkWith",
    # Keep demographic signals useful for the dashboard
    "DevType", "YearsCode", "RemoteWork", "Employment",
]

def build_survey_parquet() -> None:
    if SURVEY_OUT.exists() and SURVEY_OUT.stat().st_size > 0:
        print(f"  [INFO] {SURVEY_OUT.name} already exists ({SURVEY_OUT.stat().st_size:,} bytes). Skipping build.")
        return

    if not SURVEY_CSV.exists():
        print(f"  [INFO] {SURVEY_CSV.name} not found. Running get_data.py to download survey...")
        get_script = BASE / "stackoverflow" / "get_data.py"
        if get_script.exists():
            import subprocess
            import sys
            subprocess.run([sys.executable, str(get_script)], check=True)

    if not SURVEY_CSV.exists():
        print(f"  [ERROR] {SURVEY_CSV.name} not found and could not be fetched.")
        return

    print("Building filtered_survey.parquet...")
    df = pd.read_csv(SURVEY_CSV, usecols=lambda c: c in TECH_COLS, low_memory=False)
    # Normalise: only keep rows that have at least one tech column non-null
    tech_only = [c for c in TECH_COLS if c != "ResponseId"]
    df = df[df[tech_only].notna().any(axis=1)].copy()
    df.to_parquet(SURVEY_OUT, index=False)
    print(f"  {len(df):,} rows -> {SURVEY_OUT}")


# ---------------------------------------------------------------------------
# 2. GitHub repos JSONs → all_repos.parquet
# ---------------------------------------------------------------------------
REPOS_GLOB = str(BASE / "github" / "*" / "repos" / "*.json")
REPOS_OUT  = BASE / "github" / "all_repos.parquet"

REPO_KEEP_COLS = [
    "id", "full_name", "name", "description", "language",
    "stargazers_count", "forks_count",
    "created_at", "updated_at", "pushed_at",
    "fork", "archived", "disabled",
    "hard_excluded", "exclude_reason",
    "quality_class", "quality_score",
    "relevance_score", "is_usable",
    # Injected by extractor
    "_technology", "_snapshot_date",
]

def build_repos_parquet() -> None:
    json_files = sorted(glob.glob(REPOS_GLOB))

    # Guard: don't overwrite a good parquet if source JSONs are missing
    if not json_files:
        if REPOS_OUT.exists():
            print(f"  [SKIP] No repo JSON files found but {REPOS_OUT.name} exists. Keeping existing file.")
        else:
            print("  [WARN] No repo JSON files found. Run github_extractor.py first.")
        return

    print("Building all_repos.parquet...")
    all_repos = []
    for json_path in json_files:
        p = Path(json_path)
        snapshot_date = p.parent.parent.name   # raw/github/<date>/repos/<slug>.json
        technology_slug = p.stem               # slug = filename without .json

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                repos = json.load(f)
            except json.JSONDecodeError:
                print(f"  [WARN] Could not parse {json_path}")
                continue

        for repo in repos:
            repo["_snapshot_date"]  = snapshot_date
            repo["_technology_slug"] = technology_slug
            all_repos.append(repo)

    if not all_repos:
        print("  [WARN] JSON files found but all were empty or unparseable.")
        return

    df = pd.DataFrame(all_repos)
    # Keep only columns that exist in the dataframe
    keep = [c for c in REPO_KEEP_COLS + ["_technology_slug"] if c in df.columns]
    df = df[keep]
    df.to_parquet(REPOS_OUT, index=False)
    print(f"  {len(df):,} rows -> {REPOS_OUT}")


# ---------------------------------------------------------------------------
# 3. GitHub snapshot JSONs → all_snapshots.parquet
# ---------------------------------------------------------------------------
SNAPS_GLOB = str(BASE / "github" / "*" / "snapshots" / "*.json")
SNAPS_OUT  = BASE / "github" / "all_snapshots.parquet"

SNAP_KEEP_COLS = [
    "technology", "snapshot_date",
    "observed_repositories", "usable_repositories",
    "median_stars", "median_forks",
    "active_repository_ratio",
    "top1_star_concentration", "top5_star_concentration",
    "new_to_top100_ratio",
]

def build_snapshots_parquet() -> None:
    json_files = sorted(glob.glob(SNAPS_GLOB))

    # Guard: don't overwrite a good parquet if source JSONs are missing
    if not json_files:
        if SNAPS_OUT.exists():
            print(f"  [SKIP] No snapshot JSON files found but {SNAPS_OUT.name} exists. Keeping existing file.")
        else:
            print("  [WARN] No snapshot JSON files found.")
        return

    print("Building all_snapshots.parquet...")
    all_snaps = []
    for json_path in json_files:
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                snap = json.load(f)
            except json.JSONDecodeError:
                continue
        all_snaps.append(snap)

    if not all_snaps:
        print("  [WARN] JSON files found but all were unparseable.")
        return

    df = pd.DataFrame(all_snaps)
    keep = [c for c in SNAP_KEEP_COLS if c in df.columns]
    df = df[keep]
    df.to_parquet(SNAPS_OUT, index=False)
    print(f"  {len(df):,} rows -> {SNAPS_OUT}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    build_survey_parquet()
    build_repos_parquet()
    build_snapshots_parquet()
    print("\nAll raw files prepared. Ready for: cd dbt && dbt run")
