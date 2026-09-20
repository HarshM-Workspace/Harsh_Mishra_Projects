{{
  config(materialized='table')
}}

-- stg_adzuna_postings.sql
-- One row per unique Adzuna job posting (raw unexploded).
-- Source: raw/adzuna/adzuna_extracted.csv

select
    cast(id as varchar)        as job_id,
    cast(created_date as date) as created_date,
    title,
    location,
    technologies
from read_csv_auto(
    '{{ env_var("PROJECT_ROOT", "..") }}/raw/adzuna/adzuna_extracted.csv',
    header = true,
    types = {'id': 'VARCHAR', 'created_date': 'DATE'}
)
where id is not null
