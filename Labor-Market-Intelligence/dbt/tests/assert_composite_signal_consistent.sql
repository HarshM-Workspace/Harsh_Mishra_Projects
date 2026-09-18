-- assert_composite_signal_consistent.sql
-- Validates that the composite_signal label matches the actual
-- weekly_job_count and gh_usable_repos values per the documented rules.
--
-- Catches: logic drift between the CASE expression in fct_skill_signals.sql
-- and the intended signal interpretation guide.

select *
from {{ ref('fct_skill_signals') }}
where
    -- "thriving" must have jobs >= 5 AND usable >= 30
    (composite_signal = 'thriving'   and (weekly_job_count < 5 or coalesce(gh_usable_repos, 0) < 30))

    -- "demand_led" must have jobs >= 5 AND usable < 30
    or (composite_signal = 'demand_led' and (weekly_job_count < 5 or coalesce(gh_usable_repos, 0) >= 30))

    -- "hype_led" must have jobs < 5 AND usable >= 30
    or (composite_signal = 'hype_led'   and (weekly_job_count >= 5 or coalesce(gh_usable_repos, 0) < 30))

    -- "weak" must have jobs < 5 AND usable < 30
    or (composite_signal = 'weak'       and (weekly_job_count >= 5 or coalesce(gh_usable_repos, 0) >= 30))
