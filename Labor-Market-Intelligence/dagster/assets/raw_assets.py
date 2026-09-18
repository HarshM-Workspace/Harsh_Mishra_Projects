"""
raw_assets.py
-------------
Dagster software-defined assets for the extraction layer.

Asset dependency graph:
    github_raw_repos
    github_ecosystem_snapshots
    adzuna_jobs_csv
    stackoverflow_parquet
         ↓
    github_all_repos_parquet    (via prepare_raw.py logic)
    github_all_snapshots_parquet
         ↓
    [dbt assets in dbt_assets.py]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    MaterializeResult,
    MetadataValue,
    asset,
    define_asset_job,
)

_REPO_ROOT = Path(__file__).parent.parent   # Labor-Market-Intelligence/
_RAW       = _REPO_ROOT / "raw"
_PYTHON    = sys.executable                 # use same Python as this process


# ---------------------------------------------------------------------------
# Stack Overflow (annual, full-refresh)
# ---------------------------------------------------------------------------

@asset(
    group_name="extraction",
    description=(
        "Stack Overflow Developer Survey — filters the raw 140MB CSV to a slim "
        "parquet containing only tech columns. Full-refresh, annual cadence."
    ),
    tags={"source": "stackoverflow", "cadence": "annual"},
)
def stackoverflow_parquet(context: AssetExecutionContext) -> MaterializeResult:
    out_path = _RAW / "stackoverflow" / "filtered_survey.parquet"
    csv_path = _RAW / "stackoverflow" / "survey_result.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"SO Survey CSV not found: {csv_path}")

    # Re-use prepare_raw logic — import directly to avoid subprocess overhead
    import pandas as pd

    TECH_COLS = [
        "ResponseId",
        "LanguageHaveWorkedWith", "LanguageWantToWorkWith",
        "DatabaseHaveWorkedWith", "DatabaseWantToWorkWith",
        "WebframeHaveWorkedWith", "WebframeWantToWorkWith",
        "PlatformHaveWorkedWith", "PlatformWantToWorkWith",
        # Keep demographic signals useful for the dashboard
        "DevType", "YearsCode", "RemoteWork", "Employment",
    ]
    df = pd.read_csv(csv_path, usecols=lambda c: c in TECH_COLS, low_memory=False)
    tech_only = [c for c in TECH_COLS if c != "ResponseId"]
    df = df[df[tech_only].notna().any(axis=1)].copy()
    df.to_parquet(out_path, index=False)

    context.log.info(f"Wrote {len(df):,} rows to {out_path}")
    return MaterializeResult(metadata={
        "row_count":  MetadataValue.int(len(df)),
        "output_path": MetadataValue.path(str(out_path)),
    })


# ---------------------------------------------------------------------------
# Adzuna (daily/weekly incremental)
# ---------------------------------------------------------------------------

@asset(
    group_name="extraction",
    description=(
        "Adzuna India tech job postings — keyword-matched against tech dimension table. "
        "Appends new job IDs only (idempotent)."
    ),
    tags={"source": "adzuna", "cadence": "daily"},
)
def adzuna_jobs_csv(context: AssetExecutionContext) -> MaterializeResult:
    # Step 1: Fetch new daily data from Adzuna API (skips if today's JSON exists)
    fetch_script = _RAW / "adzuna" / "daily_data.py"
    fetch_result = subprocess.run(
        [_PYTHON, str(fetch_script)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    context.log.info(fetch_result.stdout)
    if fetch_result.returncode != 0:
        context.log.warning(f"daily_data.py returned non-zero: {fetch_result.stderr}")

    # Step 2: Build CSV from all accumulated JSON files
    script = _RAW / "adzuna" / "build_adzuna_csv.py"
    result = subprocess.run(
        [_PYTHON, str(script)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    context.log.info(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    csv_path = _RAW / "adzuna" / "adzuna_extracted.csv"
    import csv
    with open(csv_path, encoding="utf-8") as f:
        row_count = sum(1 for _ in f) - 1  # subtract header

    return MaterializeResult(metadata={
        "row_count":   MetadataValue.int(row_count),
        "output_path": MetadataValue.path(str(csv_path)),
    })


# ---------------------------------------------------------------------------
# GitHub (monthly snapshots)
# ---------------------------------------------------------------------------

@asset(
    group_name="extraction",
    description=(
        "GitHub ecosystem snapshots — Top 100 repos per technology, "
        "quality-classified and relevance-scored. Monthly cadence."
    ),
    tags={"source": "github", "cadence": "monthly"},
)
def github_ecosystem_snapshots(context: AssetExecutionContext) -> MaterializeResult:
    script = _RAW / "github" / "github_extractor.py"
    result = subprocess.run(
        [_PYTHON, str(script)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    context.log.info(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    # Count how many snapshot files were written today
    from datetime import date
    today_dir = _RAW / "github" / date.today().isoformat() / "snapshots"
    snap_count = len(list(today_dir.glob("*.json"))) if today_dir.exists() else 0

    return MaterializeResult(metadata={
        "snapshots_written": MetadataValue.int(snap_count),
    })


# ---------------------------------------------------------------------------
# Parquet consolidation (runs after extraction, before dbt)
# ---------------------------------------------------------------------------

@asset(
    group_name="preparation",
    deps=[stackoverflow_parquet, adzuna_jobs_csv, github_ecosystem_snapshots],
    description="Consolidates raw JSONs into all_repos.parquet and all_snapshots.parquet for dbt.",
)
def consolidated_parquet(context: AssetExecutionContext) -> MaterializeResult:
    script = _RAW / "prepare_raw.py"
    result = subprocess.run(
        [_PYTHON, str(script)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    context.log.info(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return MaterializeResult(metadata={"status": MetadataValue.text("ok")})


# ---------------------------------------------------------------------------
# Jobs for scheduling
# ---------------------------------------------------------------------------

daily_extraction_job = define_asset_job(
    name="daily_extraction",
    selection=["adzuna_jobs_csv", "consolidated_parquet"],
)

monthly_github_job = define_asset_job(
    name="monthly_github_snapshot",
    selection=["github_ecosystem_snapshots", "consolidated_parquet"],
)

annual_so_job = define_asset_job(
    name="annual_stackoverflow_refresh",
    selection=["stackoverflow_parquet", "consolidated_parquet"],
)
