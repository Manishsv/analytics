{{ config(
    materialized='table',
    schema='gold',
    description='Materialized view: PGR complaints summary by ward (refreshed daily)'
) }}

-- Pre-aggregated summary for common "complaints by ward" queries
-- This materialized view speeds up frequent queries
select
    ward_id,
    count(distinct complaint_id) as total_complaints,
    count(distinct case when last_status = 'RESOLVED' then complaint_id end) as resolved_complaints,
    count(distinct case when last_status = 'CLOSED' then complaint_id end) as closed_complaints,
    count(distinct case when last_status not in ('CLOSED', 'RESOLVED') then complaint_id end) as open_complaints,
    avg(t_submit_to_resolve_hours) as avg_tat_hours,
    count(distinct case when breach_flag = true then complaint_id end) as breached_complaints,
    count(distinct case when breach_flag = true then complaint_id end) * 100.0 / 
        nullif(count(distinct complaint_id), 0) as breach_rate_pct
from {{ ref('gold_pgr_case_lifecycle') }}
where ward_id is not null
group by ward_id
