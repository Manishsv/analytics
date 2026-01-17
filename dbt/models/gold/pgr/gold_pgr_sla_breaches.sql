{{ config(materialized='table', schema='gold') }}

with c as (
  select *
  from {{ ref('gold_pgr_case_lifecycle') }}
),

calc as (
  select
    tenant_id,
    complaint_id,
    ward_id,
    channel,
    complaint_type,
    priority,
    sla_hours,
    submitted_time,
    resolved_time,
    t_submit_to_resolve_hours,

    case
      when sla_hours is null or t_submit_to_resolve_hours is null then null
      when t_submit_to_resolve_hours > sla_hours then true
      else false
    end as breach_flag,

    -- breach amount and breach time (approx: submitted + sla_hours)
    case
      when sla_hours is null or t_submit_to_resolve_hours is null then null
      when t_submit_to_resolve_hours > sla_hours then (t_submit_to_resolve_hours - sla_hours)
      else 0.0
    end as breach_hours,

    case
      when sla_hours is null or submitted_time is null then null
      else date_add('hour', cast(sla_hours as integer), submitted_time)
    end as breach_time
  from c
)

select * from calc
