{{ config(
    materialized='table',
    schema='gold',
    description='Materialized view: PGR complaints by ward and channel (refreshed daily)'
) }}

-- Pre-aggregated summary for "complaints by ward and channel" queries
select
    ward_id,
    channel,
    count(distinct complaint_id) as total_complaints,
    count(distinct case when last_status = 'RESOLVED' then complaint_id end) as resolved_complaints,
    avg(t_submit_to_resolve_hours) as avg_tat_hours
from {{ ref('gold_pgr_case_lifecycle') }}
where ward_id is not null
  and channel is not null
group by ward_id, channel
