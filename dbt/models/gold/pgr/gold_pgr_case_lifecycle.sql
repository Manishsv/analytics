{{ config(materialized='table', schema='gold') }}

with e as (
  select *
  from {{ ref('silver_pgr_events') }}
),

agg as (
  select
    tenant_id,
    complaint_id,

    -- first timestamps by lifecycle event type
    min_by(event_time, event_time) filter (where event_type = 'CaseSubmitted') as submitted_time,
    min_by(event_time, event_time) filter (where event_type = 'CaseAssigned')  as assigned_time,
    min_by(event_time, event_time) filter (where event_type = 'CaseResolved')  as resolved_time,
    min_by(event_time, event_time) filter (where event_type = 'CaseClosed')    as closed_time,

    -- last known status (by latest event_time)
    max_by(status, event_time) as last_status,
    max(event_time) as last_status_time,

    -- stable slicing dimensions (choose latest non-null; adjust as needed)
    max_by(ward_id, event_time) as ward_id,
    max_by(channel, event_time) as channel,
    max_by(complaint_type, event_time) as complaint_type,
    max_by(priority, event_time) as priority,

    -- SLA (take latest non-null)
    max_by(sla_hours, event_time) as sla_hours
  from e
  group by 1,2
),

durations as (
  select
    *,
    -- durations in hours; only compute when both endpoints exist
    case
      when assigned_time is null or submitted_time is null then null
      else cast(date_diff('second', submitted_time, assigned_time) as double) / 3600.0
    end as t_submit_to_assign_hours,

    case
      when resolved_time is null or submitted_time is null then null
      else cast(date_diff('second', submitted_time, resolved_time) as double) / 3600.0
    end as t_submit_to_resolve_hours,

    case
      when closed_time is null or submitted_time is null then null
      else cast(date_diff('second', submitted_time, closed_time) as double) / 3600.0
    end as t_submit_to_close_hours
  from agg
),

sla_breach as (
  select
    *,
    -- SLA breach flags and calculations
    case
      when sla_hours is null or t_submit_to_resolve_hours is null then null
      when t_submit_to_resolve_hours > sla_hours then true
      else false
    end as breach_flag,

    -- breach amount in hours
    case
      when sla_hours is null or t_submit_to_resolve_hours is null then null
      when t_submit_to_resolve_hours > sla_hours then (t_submit_to_resolve_hours - sla_hours)
      else 0.0
    end as breach_hours,

    -- breach time (submitted + SLA hours)
    case
      when sla_hours is null or submitted_time is null then null
      else date_add('hour', cast(sla_hours as integer), submitted_time)
    end as breach_time
  from durations
)

select * from sla_breach
