{{ config(materialized='table', schema='gold') }}

with spine as (
  select date_day as metric_date
  from {{ ref('time_spine') }}
  where date_day <= current_date  -- Only include dates up to today
),

cases as (
  select
    tenant_id,
    complaint_id,
    ward_id,
    channel,
    complaint_type,
    priority,
    submitted_time,
    closed_time,
    last_status
  from {{ ref('gold_pgr_case_lifecycle') }}
  where submitted_time is not null
),

snap as (
  select
    s.metric_date,
    c.tenant_id,
    c.ward_id,
    c.channel,
    c.last_status as status,

    count(*) as open_cases
  from spine s
  join cases c
    on date(c.submitted_time) <= s.metric_date
   and (c.closed_time is null or date(c.closed_time) > s.metric_date)
  group by 1,2,3,4,5
)

select * from snap
