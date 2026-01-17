{{ config(
    materialized='table',
    schema='gold',
    description='Materialized view: Monthly PGR trends (refreshed daily)'
) }}

-- Pre-aggregated monthly trends for common time-based queries
-- Speeds up "complaints by month" queries
select
    date_trunc('month', submitted_time) as month_start,
    count(distinct complaint_id) as total_complaints,
    count(distinct case when last_status = 'RESOLVED' then complaint_id end) as resolved_complaints,
    count(distinct case when last_status = 'CLOSED' then complaint_id end) as closed_complaints,
    avg(t_submit_to_resolve_hours) as avg_tat_hours,
    count(distinct case when breach_flag = true then complaint_id end) as breached_complaints,
    count(distinct case when breach_flag = true then complaint_id end) * 100.0 / 
        nullif(count(distinct complaint_id), 0) as breach_rate_pct
from {{ ref('gold_pgr_case_lifecycle') }}
where submitted_time is not null
group by date_trunc('month', submitted_time)
