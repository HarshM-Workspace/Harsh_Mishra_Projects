-- assert_crosswalk_resolves_known_techs.sql
-- Validates that known tricky technology names (C#, C++, .NET, Node.js, AWS)
-- are present in the crosswalk with non-null github_slug.
--
-- Catches: entity resolution failures where symbol-containing names
-- don't match through the crosswalk pipeline.

with expected_techs as (
    select unnest(['C#', 'C++', 'Node.js', 'Python', 'JavaScript']) as expected_name
),

resolved as (
    select
        e.expected_name,
        c.canonical_name,
        c.github_slug
    from expected_techs e
    left join {{ ref('int_tech_crosswalk') }} c
        on lower(e.expected_name) = lower(c.canonical_name)
)

-- Return rows where a tech we expect to resolve did NOT resolve
select *
from resolved
where canonical_name is null
   or github_slug is null
