# learn.md — Labor Market Intelligence

## 1. WHAT AND WHY

This pipeline answers: **which technology skills have real employer demand, and which are just developer hype?** It does this by triangulating three signals: Adzuna job postings (hiring demand), GitHub ecosystem snapshots (developer activity), and Stack Overflow survey data (self-reported adoption).

Three sources, not one, because no single API captures the full picture. Adzuna shows what companies pay for but can't distinguish dead-enterprise (COBOL) from thriving. GitHub measures what developers build in the open but ignores proprietary ecosystems (SQL Server, SAP). SO Survey captures what individuals actually use but it's annual and self-selected. The value is in the *disagreement* between signals — a tech that's DEMAND-LED (high jobs, low GitHub) tells a different story than one that's HYPE-LED (low jobs, high GitHub).

---

## 2. DIRECTORY MAP

```
Labor-Market-Intelligence/
├── raw/                                    # EXTRACTION LAYER
│   ├── tech_dimension_table.json           # Crosswalk: SO name → GitHub slug → Adzuna keyword
│   ├── emerging_tech.json                  # Techs not in SO Survey (LangChain, CrewAI, etc.)
│   ├── curated_tech.py                     # One-time builder for tech_dimension_table.json
│   ├── prepare_raw.py                      # Consolidates all raw JSONs → parquet for dbt
│   ├── adzuna/
│   │   ├── initial_data.py                 # Historical backfill (60-day window), run once
│   │   ├── daily_data.py                   # Daily incremental fetch, paginated + checkpointed
│   │   └── build_adzuna_csv.py             # Keyword-matches jobs against tech table → CSV
│   ├── github/
│   │   ├── config.py                       # All tunable weights/thresholds, single-file edit
│   │   ├── classifier.py                   # Pure functions: quality_class + relevance_score
│   │   ├── snapshot.py                     # Pure functions: ecosystem metrics from classified repos
│   │   └── github_extractor.py             # Main entry: fetch → classify → snapshot → write JSON
│   └── stackoverflow/
│       └── get_data.py                     # Downloads 140MB survey CSV, streaming with timeout
├── dbt/                                    # TRANSFORMATION LAYER
│   ├── profiles.yml                        # dev=local DuckDB, prod=MotherDuck
│   ├── models/staging/
│   │   ├── stg_adzuna.sql                  # Explodes comma-separated techs → one row per job×tech
│   │   ├── stg_stackoverflow.sql           # Explodes semicolon-separated techs → one row per respondent×tech
│   │   ├── stg_github_repos.sql            # Casts + renames parquet columns
│   │   └── stg_github_snapshots.sql        # Casts + derives usable_ratio
│   ├── models/intermediate/
│   │   └── int_tech_crosswalk.sql          # Entity resolution: maps all source names → canonical
│   ├── models/marts/
│   │   ├── dim_technology.sql              # One row per canonical tech (surrogate key, flags)
│   │   ├── fct_skill_signals.sql           # Weekly grain: jobs + SO adoption + GitHub snapshot
│   │   └── fct_github_snapshots.sql        # Pass-through mart for dashboard/MotherDuck access
│   └── tests/
│       ├── assert_crosswalk_resolves_known_techs.sql   # C#, C++, Node.js resolve correctly
│       └── assert_composite_signal_consistent.sql      # Signal labels match their thresholds
├── dagster/                                # ORCHESTRATION LAYER
│   ├── definitions.py                      # Assets + schedules + resources wired together
│   └── assets/
│       ├── raw_assets.py                   # Software-defined assets for each extractor
│       └── dbt_assets.py                   # Wraps dbt models as Dagster assets, depends on consolidated_parquet
├── dashboard/
│   └── app.py                              # Streamlit dashboard — reads from DuckDB or MotherDuck
├── scripts/
│   ├── sync_warehouse_cache.py             # CI shortcut: pull GitHub data from MotherDuck, skip API
│   ├── create_md_db.py                     # One-time: creates labor_market DB on MotherDuck
│   └── ci_stub_data.py                     # Generates schema-compatible test stubs for CI
└── .github/workflows/
    └── production_pipeline.yml             # Daily cron: extract → consolidate → dbt run → dbt test
```

---

## 3. DATA FLOW — tracing "Python" end-to-end

**Extraction.** `tech_dimension_table.json` has `{"StackOverflow": "Python", "Github_Topic": "python", "Adzuna": "PYTHON"}`. Three extractors use it independently:

- **Adzuna path:** `daily_data.py` paginates the Adzuna API (`results_per_page=50`, `max_days_old=1`) and writes `raw/adzuna/2026-07-19.json`. Then `build_adzuna_csv.py` runs `extract_techs()`: uppercases the job text, searches for `PYTHON` with `(?<![A-Z0-9])PYTHON(?![A-Z0-9])` (negative lookaround, not `\b`), and writes a row to `adzuna_extracted.csv` with `technologies=PYTHON,SQL`.

- **GitHub path:** `github_extractor.py` calls `fetch_repos_for_tech()` with `q=topic:python&sort=stars&per_page=100`. Each repo runs through `classify_repo()` (contamination keywords vs. positive signals → `quality_class`) then `score_relevance()` (topic/language/name matching → `is_usable`). `compute_snapshot()` aggregates usable repos into metrics: `usable_repositories`, `median_stars`, `active_repository_ratio`. Output: `raw/github/2026-09-05/repos/python.json` + `snapshots/python.json`.

- **SO path:** `get_data.py` streams the 140MB CSV. `prepare_raw.py` filters it to tech columns → `filtered_survey.parquet`. The raw value is `LanguageHaveWorkedWith = "Python;JavaScript;SQL"`.

**Consolidation.** `prepare_raw.py` globs all `repos/*.json` → `all_repos.parquet`, all `snapshots/*.json` → `all_snapshots.parquet`.

**Staging.** `stg_adzuna.sql` explodes `technologies` by comma with `unnest(string_split(...))` — one row with `technology_keyword = 'PYTHON'`. `stg_stackoverflow.sql` explodes by semicolon — one row with `technology_raw = 'Python'`.

**Entity resolution.** `int_tech_crosswalk.sql` reads `tech_dimension_table.json` directly via `read_json_auto()`. The `so_map` CTE produces `canonical_name='Python', github_slug='python', adzuna_keyword='PYTHON'`. The dedup CTE partitions by `lower(canonical_name)` and ranks `emerging_tech > so_survey > adzuna`.

**Mart.** `dim_technology.sql` collapses to one row: `tech_id = surrogate_key('Python')`. `fct_skill_signals.sql` joins on three keys: Adzuna via `upper(adzuna_keyword) = upper(adzuna_keyword)`, SO via `lower(technology_raw) = lower(canonical_name)`, GitHub via `lower(technology_name) = lower(canonical_name)`. The GitHub join finds the most recent snapshot **on or before** each Adzuna week (`partition by tech_id, week_start ... where snapshot_date <= week_start`). The CASE expression assigns `composite_signal = 'thriving'` (jobs ≥ 5 AND usable repos ≥ 30).

**Dashboard.** `app.py` connects to either local DuckDB or MotherDuck, queries `main_marts.fct_skill_signals` and `dim_technology`, and renders a quadrant scatter plot (x = weekly jobs √-scaled, y = usable repos).

---

## 4. CODE PATTERNS BY STAGE

**API extraction — paginated, rate-limited, incremental.** Both Adzuna and GitHub extractors paginate, but they differ fundamentally. Adzuna (`daily_data.py`) is *watermarked*: `max_days_old=1` + file-per-day naming means each run fetches only new data. It checkpoints progress to `progess-{date}.json` after each page so a crash resumes mid-run. GitHub (`github_extractor.py`) is *idempotent by file existence*: if `repos/python.json` exists, the tech is skipped entirely. It does *not* checkpoint mid-tech — a crash during Python's fetch loses that tech's data but doesn't corrupt others. GitHub also has explicit rate-limit handling: `_check_rate_limit()` reads `X-RateLimit-Remaining` headers and sleeps adaptively (max 65s). Both use `fetch_with_retry()` / timeout patterns, but Adzuna retries with exponential backoff while GitHub retries once on 403 then breaks. See `daily_data.py:22-42` and `github_extractor.py:181-197`.

**Flat-file extraction — full-refresh, annual.** `get_data.py` is fundamentally different: one 140MB download, no pagination, no incrementality. It streams with `iter_content(chunk_size=8192)` to avoid loading 140MB into memory. There's no resume — if it fails, you re-download. This is appropriate because it runs annually. See `get_data.py`.

**Staging pattern.** Every staging model does exactly three things: (1) reads a raw file via `read_parquet()` or `read_csv_auto()`, (2) casts/renames columns to consistent types, (3) explodes multi-value columns into one row per entity. They deliberately do *not* filter, join, or aggregate — that's the intermediate/mart layer's job. All are materialized as views. See `stg_adzuna.sql` (comma-split), `stg_stackoverflow.sql` (semicolon-split via 4-way UNION ALL).

**Entity resolution pattern.** `int_tech_crosswalk.sql` uses exact-match via a pre-validated lookup table, not fuzzy matching. This is a deliberate choice: the tech names come from a controlled vocabulary (SO Survey options), so exact match produces zero false positives. The failure mode is *false negatives* — a tech not in `tech_dimension_table.json` won't resolve. The `emerging_tech.json` file extends coverage beyond the SO Survey baseline. The crosswalk deduplicates by `lower(canonical_name)` with a priority ranking: emerging > SO > Adzuna.

**Mart pattern.** `fct_skill_signals` has grain = one row per canonical technology per Adzuna week. It's a fact table because the grain is an event (a week of observed demand), not an entity. The join to GitHub snapshots is a *temporal as-of join* — it picks the most recent snapshot on or before each week, using `row_number() over (partition by tech_id, week_start)`. The `composite_signal` label is a derived column — a 2×2 classification on (jobs ≥ 5, repos ≥ 30). See `fct_skill_signals.sql:114-122`.

**Orchestration pattern.** Dagster uses *software-defined assets*, not tasks/ops. Each extractor is an asset (`stackoverflow_parquet`, `adzuna_jobs_csv`, `github_ecosystem_snapshots`). `consolidated_parquet` depends on all three. dbt assets use `non_argument_deps` to declare the file-system dependency that Dagster can't infer. Schedules: daily Adzuna at 02:00 IST, monthly GitHub on the 1st. SO is manual-only. See `definitions.py:42-53`, `raw_assets.py`, `dbt_assets.py`.

**Testing pattern.** Three layers: (1) `schema.yml` generic tests — `unique`, `not_null`, `accepted_values`, `relationships` on PKs and FKs. (2) Singular tests — `assert_crosswalk_resolves_known_techs.sql` validates C#/C++/Node.js resolve with non-null slugs; `assert_composite_signal_consistent.sql` validates signal labels match thresholds. (3) CI structural validation via `ci_stub_data.py` which generates schema-compatible stubs so `dbt run + dbt test` passes without real API data.

---

## 5. WHY THESE TOOLS

**Dagster** over Airflow: asset-centric model maps naturally to "this parquet file depends on this extraction". Tradeoff: smaller ecosystem, fewer deploy-to-prod options.

**dbt + DuckDB** over Spark/Snowflake: the dataset is small (~1K jobs, ~100 techs × 100 repos). DuckDB runs dbt locally in seconds with zero infrastructure. Tradeoff: no concurrent writes, no multi-user access — hence MotherDuck for prod/dashboard.

**MotherDuck**: serverless DuckDB in the cloud. Dashboard reads from it, CI writes to it. Tradeoff: young product, no SLA guarantees, limited region availability.

**Streamlit**: fastest path from SQL results to interactive charts. Tradeoff: limited layout control, heavy custom CSS needed for anything beyond defaults (see the 400-line CSS block in `app.py`).

---

## 6. KNOWN LIMITATIONS

- **India-only, IT-only Adzuna data.** `category=it-jobs` + India endpoint. Not representative of global demand.
- **GitHub top-100-by-stars bias.** Popular ≠ actively-used-in-production. The "usable repos" metric measures open-source visibility, not industry adoption. SQL Server has almost zero GitHub traction but massive enterprise demand.
- **Single GitHub snapshot.** With only one snapshot, `new_to_top100_ratio` and all trend metrics are null. The temporal join in `fct_skill_signals` degrades gracefully but produces flat GitHub data across all weeks. The header badge now shows snapshot count explicitly ("1 snapshot") so the staleness is visible without reading the code.
- **No NLP on job descriptions.** Keyword matching (even with correct regex) misses implicit skill requirements. A job asking for "machine learning engineer" won't match "PyTorch" unless PyTorch appears in the text.
- **Adzuna deduplication is by `id` only.** If the same job is reposted with a new ID, it's counted twice.
- **SO Survey is annual and self-selected.** Participation skews toward engaged developers, not representative of enterprise IT.
- **At 100× volume** (100K jobs/day, 10K techs): DuckDB would need to be replaced. The `string_split` + `unnest` in staging would need columnar optimization. The GitHub extractor is serially rate-limited — 10K techs would take days.
- **Dashboard `job_trend_pct` is simulated** — `app.py:505` generates a deterministic pseudo-trend from a hash, not from actual week-over-week deltas. The `TOTAL_JOBS = 1788` on line 515 is hardcoded.
