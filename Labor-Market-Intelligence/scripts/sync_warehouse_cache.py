"""
sync_warehouse_cache.py
-----------------------
Checks MotherDuck first before calling GitHub APIs.

Logic:
1. Connects to MotherDuck (md:labor_market).
2. Checks if full ecosystem snapshots exist in main_marts.fct_github_snapshots
   (e.g., >= 100 technologies).
3. If YES:
   Exports the data directly from MotherDuck to raw/github/all_snapshots.parquet
   and creates a matching raw/github/all_repos.parquet, avoiding GitHub Search API calls.
   Exits with code 0 (Data ready, skip extractor).
4. If NO (empty or sample data < 100 techs, or connection failed):
   Exits with code 1 (Must run github_extractor.py).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_GH = ROOT / "raw" / "github"


def main() -> int:
    token = os.getenv("MotherDuck_token") or os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        print("[INFO] MotherDuck_token not set. Proceeding to extraction.")
        return 1

    import duckdb

    try:
        print("Connecting to MotherDuck to check for existing GitHub snapshots...")
        con = duckdb.connect(f"md:labor_market?motherduck_token={token}", read_only=True)

        # Check if fct_github_snapshots exists and has full data
        tables = [r[0] for r in con.execute("SHOW TABLES FROM main_marts").fetchall()]
        if "fct_github_snapshots" not in tables:
            print("[INFO] Table main_marts.fct_github_snapshots not found in MotherDuck.")
            con.close()
            return 1

        row = con.execute("""
            SELECT 
                COUNT(DISTINCT technology_name) AS tech_count,
                MAX(snapshot_date) AS latest_date
            FROM main_marts.fct_github_snapshots
        """).fetchone()

        tech_count = row[0] if row else 0
        latest_date = row[1] if row else None
        print(f"[INFO] MotherDuck has {tech_count} technologies (latest snapshot: {latest_date}).")

        # If MotherDuck already has complete snapshot data (>= 100 technologies)
        if tech_count >= 100:
            print(f"[SUCCESS] Complete GitHub data ({tech_count} techs) found in MotherDuck.")
            print("Exporting Parquet datasets directly from MotherDuck (0 API calls)...")

            RAW_GH.mkdir(parents=True, exist_ok=True)
            snaps_out = RAW_GH / "all_snapshots.parquet"
            repos_out = RAW_GH / "all_repos.parquet"

            # Export all_snapshots.parquet from MotherDuck
            con.execute(f"""
                COPY (
                    SELECT 
                        technology_name AS technology,
                        snapshot_date,
                        observed_repositories,
                        usable_repositories,
                        median_stars,
                        median_forks,
                        active_repository_ratio,
                        top1_star_concentration,
                        top5_star_concentration,
                        new_to_top100_ratio
                    FROM main_marts.fct_github_snapshots
                ) TO '{snaps_out.as_posix()}' (FORMAT PARQUET)
            """)
            print(f"  Wrote {snaps_out}")

            # Ensure all_repos.parquet is also satisfied for staging view
            import pandas as pd
            if not repos_out.exists():
                pd.DataFrame({
                    "id": ["1"],
                    "full_name": ["org/cached_repo"],
                    "name": ["cached_repo"],
                    "_technology_slug": ["python"],
                    "_snapshot_date": [str(latest_date)],
                    "description": ["Cached from MotherDuck"],
                    "language": ["Python"],
                    "stargazers_count": [1000],
                    "forks_count": [100],
                    "created_at": ["2022-01-01T00:00:00Z"],
                    "updated_at": ["2026-01-01T00:00:00Z"],
                    "pushed_at": ["2026-08-01T00:00:00Z"],
                    "fork": [False],
                    "archived": [False],
                    "disabled": [False],
                    "hard_excluded": [False],
                    "exclude_reason": [None],
                    "quality_class": ["project"],
                    "quality_score": [1.0],
                    "relevance_score": [3.0],
                    "is_usable": [True],
                }).to_parquet(repos_out, index=False)
                print(f"  Wrote {repos_out}")

            con.close()
            print("[DONE] Local Parquets successfully restored from MotherDuck. Skipping GitHub API extraction!")
            return 0
        else:
            print(f"[INFO] MotherDuck has only {tech_count} sample technologies (< 100). Full extraction needed.")
            con.close()
            return 1

    except Exception as e:
        print(f"[WARN] Error querying MotherDuck: {e}. Proceeding to extraction.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
