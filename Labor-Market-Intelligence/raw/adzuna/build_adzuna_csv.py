"""
build_adzuna_csv.py
-------------------
One-shot script to build adzuna_extracted.csv from all raw JSON files.

Fixes the original adzuna_data_extraction.py bug where unique_ids was read
from the CSV before it was written, causing a crash on a fresh run.

Run:
    python raw/adzuna/build_adzuna_csv.py

Idempotent: re-running appends only new job IDs not already in the CSV.
"""

import csv
import glob
import json
import os
import re
from pathlib import Path

BASE = Path(__file__).parent
CSV_PATH  = BASE / "adzuna_extracted.csv"
DIM_TABLE = BASE.parent / "tech_dimension_table.json"
JSON_GLOB = str(BASE / "*.json")


def extract_techs(title: str, description: str, ref_table: list[dict]) -> str:
    """
    Keyword-match job title+description against the Adzuna keyword column
    in the dimension table. Returns comma-separated matched tech names.
    """
    job_text = re.sub(r"[^A-Z #+]", " ", (title + " " + description).upper())
    matched = []
    for row in ref_table:
        keyword = row.get("Adzuna", "")
        if not keyword:
            continue
        pattern = r"(?<![A-Z0-9])" + re.escape(keyword) + r"(?![A-Z0-9])"
        if re.search(pattern, job_text):
            matched.append(keyword)
    return ",".join(matched)


def main() -> None:
    # Load reference table once
    with open(DIM_TABLE, "r", encoding="utf-8") as f:
        dim_table = json.load(f)

    # If running in CI/cloud where CSV_PATH is missing, restore accumulated jobs from MotherDuck
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        token = os.getenv("MotherDuck_token") or os.getenv("MOTHERDUCK_TOKEN")
        if token:
            try:
                import duckdb
                con = duckdb.connect(f"md:labor_market?motherduck_token={token}", read_only=True)
                tables = [r[0] for r in con.execute("SHOW TABLES FROM main_staging").fetchall()]
                if "stg_adzuna_postings" in tables:
                    df_existing = con.execute("SELECT job_id as id, created_date, title, location, technologies FROM main_staging.stg_adzuna_postings").df()
                    if not df_existing.empty:
                        df_existing.to_csv(CSV_PATH, index=False)
                        print(f"  [INFO] Restored {len(df_existing)} accumulated jobs from MotherDuck cache.")
                con.close()
            except Exception as e:
                print(f"  [WARN] MotherDuck sync check skipped: {e}")

    # Load existing IDs to avoid duplicates
    existing_ids: set[str] = set()
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 0:
        with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row["id"])

    # Write header if file is empty/new
    write_header = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0

    json_files = sorted(glob.glob(JSON_GLOB))
    total_written = 0

    with open(CSV_PATH, "a", encoding="utf-8", newline="") as out_f:
        writer = csv.writer(out_f)
        if write_header:
            writer.writerow(["id", "created_date", "title", "location", "technologies"])

        for json_file in json_files:
            file_name = Path(json_file).name
            if (
                file_name.startswith("progess-")
                or file_name.startswith("progress-")
                or json_file == str(CSV_PATH)
            ):
                continue
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    jobs = json.load(f)
                except json.JSONDecodeError:
                    print(f"  [WARN] Could not parse {json_file}")
                    continue

            if isinstance(jobs, dict) and "data" in jobs and isinstance(jobs["data"], list):
                jobs = jobs["data"]
            elif not isinstance(jobs, list):
                continue

            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("id", ""))
                if not job_id or job_id in existing_ids:
                    continue

                title       = job.get("title", "")
                description = job.get("description", "")
                created     = str(job.get("created", ""))[:10]
                location    = (job.get("location") or {}).get("display_name", "")
                techs       = extract_techs(title, description, dim_table)
                if not techs:
                    continue

                writer.writerow([job_id, created, title, location, techs])
                existing_ids.add(job_id)
                total_written += 1

    print(f"Done. {total_written} new rows written to {CSV_PATH}")
    print(f"Total unique jobs in CSV: {len(existing_ids)}")


if __name__ == "__main__":
    main()
