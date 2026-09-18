{{
  config(materialized='table')
}}

-- fct_skill_signals.sql
-- Fact table: skill demand + ecosystem signals joined by canonical technology.
--
-- Grain: one row per canonical technology per week (Adzuna) + snapshot (GitHub).
-- Adzuna is weekly; GitHub is monthly snapshots.
-- SO Survey is annual; included as a baseline adoption_pct column.
--
-- Signal interpretation guide (per github_ecosystem_process.md section 14):
--   jobs_count UP  + github_usable UP   -> strong/thriving signal
--   jobs_count UP  + github_usable DOWN -> labor demand despite weaker ecosystem
--   jobs_count DOWN + github_usable UP  -> developer interest despite weaker hiring
--   jobs_count DOWN + github_usable DOWN -> broad weakening

with dim_tech as (
    select * from {{ ref('dim_technology') }}
),

-- ── Adzuna: weekly job posting counts per technology ──────────────────────
adzuna_weekly as (
    select
        upper(technology_keyword)       as adzuna_keyword,
        date_trunc('week', created_date) as week_start,
        count(distinct job_id)          as job_count
    from {{ ref('stg_adzuna') }}
    where technology_keyword is not null
      and created_date is not null
    group by 1, 2
),

adzuna_with_tech as (
    select
        dt.tech_id,
        dt.canonical_name,
        aw.week_start,
        aw.job_count
    from adzuna_weekly aw
    inner join dim_tech dt
        on upper(aw.adzuna_keyword) = upper(dt.adzuna_keyword)
),

-- ── SO Survey: baseline adoption pct per technology ───────────────────────
-- Counts respondents who listed the technology in any "have worked with" column.
-- Used as a one-time baseline signal, not a time series.
so_adoption as (
    select
        technology_raw,
        count(distinct respondent_id)   as respondent_count
    from {{ ref('stg_stackoverflow') }}
    group by technology_raw
),

so_total as (
    select count(distinct respondent_id) as total_respondents
    from {{ ref('stg_stackoverflow') }}
),

so_with_tech as (
    select
        dt.tech_id,
        dt.canonical_name,
        round(
            cast(sa.respondent_count as double) / st.total_respondents * 100, 2
        )                               as so_adoption_pct
    from so_adoption sa
    inner join dim_tech dt
        on lower(sa.technology_raw) = lower(dt.canonical_name)
    cross join so_total st
),

-- ── GitHub: ecosystem snapshot signals per technology ─────────────────────
github_with_tech as (
    select
        dt.tech_id,
        dt.canonical_name,
        gs.snapshot_date,
        gs.usable_repositories,
        gs.median_stars,
        gs.median_forks,
        gs.active_repository_ratio,
        gs.top5_star_concentration,
        gs.new_to_top100_ratio
    from {{ ref('stg_github_snapshots') }} gs
    inner join dim_tech dt
        on lower(gs.technology_name) = lower(dt.canonical_name)
),

-- ── Combined fact: Adzuna weekly + GitHub closest prior snapshot ──────────
combined as (
    select
        a.tech_id,
        a.canonical_name,
        a.week_start                        as signal_week,

        -- Adzuna signals
        a.job_count                         as weekly_job_count,

        -- SO Survey baseline (static)
        so.so_adoption_pct,

        -- GitHub: most recent snapshot on or before the week
        gh.snapshot_date                    as github_snapshot_date,
        gh.usable_repositories              as gh_usable_repos,
        gh.median_stars                     as gh_median_stars,
        gh.median_forks                     as gh_median_forks,
        gh.active_repository_ratio          as gh_active_ratio,
        gh.top5_star_concentration          as gh_top5_concentration,
        gh.new_to_top100_ratio              as gh_turnover_ratio,

        -- Composite signal label (descriptive, not causal)
        case
            when a.job_count >= 5 and coalesce(gh.usable_repositories, 0) >= 30
                then 'thriving'
            when a.job_count >= 5 and coalesce(gh.usable_repositories, 0) < 30
                then 'demand_led'
            when a.job_count < 5  and coalesce(gh.usable_repositories, 0) >= 30
                then 'hype_led'
            else 'weak'
        end                                 as composite_signal

    from adzuna_with_tech a

    left join so_with_tech so
        on a.tech_id = so.tech_id

    -- Left join to nearest GitHub snapshot on or before each week
    left join (
        select
            a2.tech_id,
            a2.week_start,
            gh1.snapshot_date,
            gh1.usable_repositories,
            gh1.median_stars,
            gh1.median_forks,
            gh1.active_repository_ratio,
            gh1.top5_star_concentration,
            gh1.new_to_top100_ratio,
            -- rank snapshots per tech per week, pick most recent on or before the week
            row_number() over (
                partition by a2.tech_id, a2.week_start
                order by gh1.snapshot_date desc
            ) as rn
        from adzuna_with_tech a2
        inner join github_with_tech gh1
            on a2.tech_id = gh1.tech_id
            and gh1.snapshot_date <= a2.week_start
    ) gh on a.tech_id = gh.tech_id and a.week_start = gh.week_start and gh.rn = 1
)

select
    {{ dbt_utils.generate_surrogate_key(['tech_id', 'signal_week']) }} as signal_id,
    tech_id,
    canonical_name,
    signal_week,
    weekly_job_count,
    so_adoption_pct,
    github_snapshot_date,
    gh_usable_repos,
    gh_median_stars,
    gh_median_forks,
    gh_active_ratio,
    gh_top5_concentration,
    gh_turnover_ratio,
    composite_signal
from combined
