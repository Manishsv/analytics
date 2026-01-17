{{ config(materialized='table', schema='gold') }}

with e as (
  select
    tenant_id,
    ward_id,
    channel,
    date(event_time) as metric_date,
    event_type,
    complaint_id
  from {{ ref('silver_pgr_events') }}
),

counts as (
  select
    metric_date,
    tenant_id,
    ward_id,
    channel,

    count_if(event_type = 'CaseSubmitted') as submitted_events,
    count_if(event_type = 'CaseAssigned')  as assigned_events,
    count_if(event_type = 'CaseResolved')  as resolved_events,
    count_if(event_type = 'CaseClosed')    as closed_events,
    count_if(event_type = 'CaseReopened')  as reopened_events,

    -- distinct complaint counts by stage (often more meaningful than raw events)
    count(distinct if(event_type = 'CaseSubmitted', complaint_id, null)) as submitted_cases,
    count(distinct if(event_type = 'CaseResolved', complaint_id, null))  as resolved_cases,
    count(distinct if(event_type = 'CaseClosed', complaint_id, null))    as closed_cases
  from e
  group by 1,2,3,4
)

select * from counts
