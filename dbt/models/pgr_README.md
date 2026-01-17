# PGR (Public Grievance Redressal) Reference Implementation

Complete data pipeline for PGR event analytics using Bronze/Silver/Gold architecture.

## Architecture

### Bronze Layer
- **`iceberg.bronze.service_events_raw`**: Raw event landing table for all services (PGR, etc.)
  - Partitioned by `event_date` and `service`
  - Includes event envelope fields + `attributes_json` for flexible attributes

### Silver Layer
- **`silver_pgr_events`**: Typed PGR events fact
  - Filters `service='PGR'` and `entity_type='complaint'`
  - Extracts key attributes: `complaint_type`, `priority`, `sla_hours`, `from_status`, `to_status`
  - Validates not-null on critical fields

### Gold Layer

1. **`gold_pgr_case_lifecycle`**: One row per complaint with lifecycle timestamps
   - Derived fields: `submitted_time`, `assigned_time`, `resolved_time`, `closed_time`
   - Duration calculations: `t_submit_to_assign_hours`, `t_submit_to_resolve_hours`, `t_submit_to_close_hours`
   - SLA breach flags: `breach_flag`, `breach_hours`, `breach_time`
   - Stable dimensions: `ward_id`, `channel`, `complaint_type`, `priority`, `last_status`

2. **`gold_pgr_funnel_daily`**: Daily funnel metrics by tenant/ward/channel
   - Event counts: `submitted_events`, `assigned_events`, `resolved_events`, `closed_events`, `reopened_events`
   - Case counts: `submitted_cases`, `resolved_cases`, `closed_cases`

3. **`gold_pgr_sla_breaches`**: SLA breach analysis (deprecated - merged into case lifecycle)

4. **`gold_pgr_backlog_daily`**: Daily snapshot of open cases by status
   - Joins `time_spine` to compute open cases at end of each day
   - Includes: `tenant_id`, `ward_id`, `channel`, `status`, `open_cases`

## Semantic Layer (MetricFlow)

### Semantic Model: `pgr_case_lifecycle`
- **Entity**: `complaint` (primary key: `complaint_id`)
- **Time Dimension**: `submitted_time` (day granularity)
- **Dimensions**: `tenant_id`, `ward_id`, `channel`, `complaint_type`, `priority`, `last_status`
- **Measures**:
  - `complaints`: Count distinct complaints
  - `resolved_complaints`: Count distinct resolved complaints
  - `pgr_tat_submit_to_resolve_hours_sum`: Sum of TAT hours
  - `pgr_tat_submit_to_resolve_hours_count`: Count with TAT
  - `breached_complaints`: Count distinct breached complaints

### Metrics

#### Core Metrics
- `pgr_complaints`: Total complaints submitted
- `pgr_resolved_complaints`: Total resolved complaints
- `pgr_resolution_rate`: Resolved / Total (ratio)

#### Performance Metrics
- `pgr_avg_tat_submit_to_resolve_hours`: Average time to resolve (hours)

#### SLA Metrics
- `pgr_sla_breached_complaints`: Count of breached complaints
- `pgr_sla_breach_rate`: Breached / Total (ratio)

## Usage

### Build Pipeline
```bash
cd dbt
source ../.venv310/bin/activate
dbt run --profiles-dir . --select silver_pgr_events gold_pgr_case_lifecycle gold_pgr_funnel_daily gold_pgr_backlog_daily
```

### Query Metrics
```bash
# List available PGR metrics
mf list metrics | grep pgr

# Complaints by ward and channel
mf query --metrics pgr_complaints --group-by pgr__ward_id,pgr__channel

# Resolution rate by ward
mf query --metrics pgr_resolution_rate --group-by pgr__ward_id

# Average TAT by channel
mf query --metrics pgr_avg_tat_submit_to_resolve_hours --group-by pgr__channel

# SLA breach rate for high priority complaints
mf query --metrics pgr_sla_breach_rate --group-by pgr__ward_id --where "pgr__priority = 'HIGH'"
```

### NLQ Examples (via Agent API)
- "How many PGR complaints were submitted by ward and channel?"
- "What is the resolution rate by ward?"
- "Average time to resolve by channel last month"
- "SLA breach rate by ward for high priority complaints"

## Event Schema

PGR services should emit events with this structure:

```json
{
  "event_id": "UUID",
  "event_time": "UTC timestamp",
  "event_date": "DATE",
  "tenant_id": "TENANT_001",
  "service": "PGR",
  "entity_type": "complaint",
  "entity_id": "CMP_001",
  "event_type": "CaseSubmitted|CaseAssigned|CaseResolved|CaseClosed|CaseReopened|StatusChanged",
  "status": "OPEN|ASSIGNED|RESOLVED|CLOSED|REOPENED|CANCELLED",
  "actor_type": "CITIZEN|EMPLOYEE|SYSTEM|INTEGRATION",
  "actor_id": "optional",
  "channel": "WEB|MOBILE|CSC|COUNTER|API",
  "ward_id": "WARD_001",
  "locality_id": "optional",
  "attributes_json": "{\"complaint_type\":\"Water Supply\",\"priority\":\"HIGH\",\"sla_hours\":24}",
  "raw_payload": "optional full event payload"
}
```

## Design Notes

- **Case-level Gold marts**: Business questions answered without complex event stitching at query time
- **SLA breach merged**: Breach calculations are now in `gold_pgr_case_lifecycle` to avoid semantic model conflicts
- **Flexible attributes**: JSON attributes allow schema evolution without dbt changes
- **Time-based operations**: Uses `submitted_time` DATE column for time-based filtering and aggregations
