{{ config(
    materialized='table',
    schema='gold',
    description='Multi-tenant PGR ward summary with tenant isolation'
) }}

-- Example of multi-tenant materialized view
-- Uses tenant_filter macro for data isolation
select
    tenant_id,
    ward_id,
    count(distinct complaint_id) as total_complaints,
    count(distinct case when last_status = 'RESOLVED' then complaint_id end) as resolved_complaints,
    avg(t_submit_to_resolve_hours) as avg_tat_hours
from {{ ref('gold_pgr_case_lifecycle') }}
where {{ tenant_filter() }}
  and ward_id is not null
group by tenant_id, ward_id
