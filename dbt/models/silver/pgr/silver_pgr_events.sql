{{ config(materialized='table', schema='silver') }}

with src as (
  select
    -- Generate event_id (bronze table doesn't have it yet; will be added in future)
    'EVT_' || cast(row_number() over (order by event_time, entity_id) as varchar) as event_id,
    cast(event_time as timestamp) as event_time,
    cast(event_date as date) as event_date,

    tenant_id,
    service,
    entity_type,
    entity_id as complaint_id,

    event_type,
    status,

    actor_type,
    actor_id,
    channel,

    ward_id,
    locality_id,

    -- Keep attributes as JSON string for now; parse key fields below as columns
    attributes_json
  from {{ source('bronze', 'service_events_raw') }}
  where service = 'PGR'
    and entity_type = 'complaint'
),

typed as (
  select
    event_id,
    event_time,
    event_date,
    tenant_id,
    complaint_id,
    event_type,
    status,
    actor_type,
    actor_id,
    channel,
    ward_id,
    locality_id,

    -- Extract common analytics fields from attributes (keys can be adapted)
    json_extract_scalar(attributes_json, '$.complaint_type') as complaint_type,
    json_extract_scalar(attributes_json, '$.priority') as priority,
    try_cast(json_extract_scalar(attributes_json, '$.sla_hours') as integer) as sla_hours,
    json_extract_scalar(attributes_json, '$.from_status') as from_status,
    json_extract_scalar(attributes_json, '$.to_status') as to_status
  from src
)

select *
from typed
where tenant_id is not null
  and complaint_id is not null
  and event_time is not null
  and event_type is not null
