{{
  config(materialized='table')
}}

-- stg_adzuna.sql
-- One row per job posting per matched technology.
-- Source: raw/adzuna/adzuna_extracted.csv

with raw as (
    select * from read_csv_auto(
        '{{ env_var("PROJECT_ROOT", "..") }}/raw/adzuna/adzuna_extracted.csv',
        header = true,
        types = {'id': 'VARCHAR', 'created_date': 'DATE'}
    )
),

exploded as (
    -- Each job can match multiple technologies (comma-separated)
    select
        id                              as job_id,
        created_date,
        title,
        location,
        trim(tech)                      as technology_keyword
    from raw,
    unnest(string_split(coalesce(technologies, ''), ',')) as t(tech)
    where trim(tech) != ''
)

select
    job_id,
    created_date,
    title,
    location,
    technology_keyword,
    -- natural key
    job_id || '|' || technology_keyword as record_id
from exploded
