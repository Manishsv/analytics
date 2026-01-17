# Superset Setup for PGR Analytics

Complete guide for setting up Apache Superset with PGR (Public Grievance Redressal) data.

## Prerequisites

1. Docker Compose stack running (MinIO, Nessie, Trino, Superset)
2. PGR data loaded in Bronze/Silver/Gold layers
3. dbt models run successfully (`dbt run`)

## Quick Start

### Step 1: Initialize Superset (One-Time Setup)

```bash
# Ensure Superset container is running
docker compose up -d superset

# Wait for Superset to be ready (about 30 seconds)
docker compose ps superset

# Initialize Superset database
docker exec -it dap-superset superset db upgrade

# Create admin user
docker exec -it dap-superset superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@example.com \
  --password admin

# Initialize Superset (load examples, set permissions)
docker exec -it dap-superset superset init
```

### Step 2: Access Superset Web UI

Navigate to: **http://localhost:8088**

- **Username**: `admin`
- **Password**: `admin`

### Step 3: Install Trino Connector

Superset doesn't include the Trino connector by default. Install it:

```bash
# Install sqlalchemy-trino in the Superset container
docker exec -it dap-superset pip install sqlalchemy-trino

# Restart Superset to load the new driver
docker compose restart superset

# Wait for Superset to restart (about 30 seconds)
docker compose ps superset
```

**Alternative**: If you need persistence, create a requirements file:

```bash
# Create requirements file
echo "sqlalchemy-trino" > superset/requirements-local.txt

# Update docker-compose.yml to mount and install requirements
# (See Advanced Setup section below)
```

### Step 4: Connect to Trino Database

1. **Go to Data → Databases**
2. **Click "+ Database"**
3. **Select "Trino"** from the list (should now be available after installing connector)
4. **Configure Connection**:

**Basic Configuration:**
```
Display Name: Trino Analytics
SQLAlchemy URI: trino://admin@trino:8080/iceberg
```

**Advanced Configuration (Recommended):**
```
Database Name: Trino Analytics
SQLAlchemy URI: trino://admin@trino:8080/iceberg

Advanced → Engine Parameters (JSON):
{
  "connect_args": {
    "http_scheme": "http",
    "verify": false
  }
}
```

**Alternative Connection String (if above doesn't work):**
```
trino://admin@trino:8080/iceberg?protocol=http
```

5. **Click "Test Connection"** (should show "Connection looks good!")
6. **Click "Connect"**

**Troubleshooting Connection:**
- If "Trino" doesn't appear in the list, ensure `sqlalchemy-trino` is installed
- If connection fails, verify Trino is accessible: `docker exec -it dap-trino trino --server http://trino:8080 -e "SELECT 1"`
- Try using `trino` as hostname instead of `localhost` (from within Superset container)

### Step 4: Import PGR Datasets

#### Import Gold Tables

1. **Go to Data → Datasets**
2. **Click "+ Dataset"**
3. **Select Database**: `Trino Analytics`
4. **Select Schema**: `gold`
5. **Select Tables**:
   - `gold_pgr_case_lifecycle` - One row per complaint with lifecycle metrics
   - `gold_pgr_funnel_daily` - Daily funnel metrics
   - `gold_pgr_backlog_daily` - Daily backlog snapshots
   - `gold_pgr_sla_breaches` - SLA breach analysis

6. **Click "Create"** for each table

#### Configure Dataset Metrics

For each dataset, add metrics in Superset:

**For `gold_pgr_case_lifecycle`:**
- Metrics:
  - `complaints_count` (COUNT DISTINCT of `complaint_id`)
  - `resolved_complaints` (COUNT DISTINCT WHERE `last_status = 'RESOLVED'`)
  - `avg_tat_hours` (AVG of `t_submit_to_resolve_hours`)
  - `sla_breach_count` (COUNT WHERE `breach_flag = true`)

- Dimensions:
  - `ward_id`
  - `channel`
  - `complaint_type`
  - `priority`
  - `last_status`
  - `submitted_time` (time column)

**For `gold_pgr_funnel_daily`:**
- Metrics:
  - `submitted_events`
  - `assigned_events`
  - `resolved_events`
  - `closed_events`
  - `reopened_events`
  - `submitted_cases`
  - `resolved_cases`
  - `closed_cases`

- Dimensions:
  - `metric_date` (time column)
  - `tenant_id`
  - `ward_id`
  - `channel`

**For `gold_pgr_backlog_daily`:**
- Metrics:
  - `open_cases` (SUM of `open_cases`)

- Dimensions:
  - `metric_date` (time column)
  - `tenant_id`
  - `ward_id`
  - `channel`
  - `status`

**For `gold_pgr_sla_breaches`:**
- Metrics:
  - `breached_cases` (COUNT DISTINCT of `complaint_id`)
  - `total_breach_hours` (SUM of `breach_hours`)

- Dimensions:
  - `ward_id`
  - `channel`
  - `priority`
  - `breach_time` (time column)

### Step 5: Create PGR Dashboards

#### Dashboard 1: PGR Overview

**Charts:**
1. **Total Complaints** (Big Number)
   - Dataset: `gold_pgr_case_lifecycle`
   - Metric: `complaints_count`
   - Time filter: Last 30 days

2. **Complaints by Ward** (Bar Chart)
   - Dataset: `gold_pgr_case_lifecycle`
   - Metric: `complaints_count`
   - Dimension: `ward_id`
   - Group by: `ward_id`
   - Order by: `complaints_count` DESC
   - Limit: Top 10

3. **Complaints by Status** (Pie Chart)
   - Dataset: `gold_pgr_case_lifecycle`
   - Metric: `complaints_count`
   - Dimension: `last_status`
   - Group by: `last_status`

4. **Daily Complaint Trends** (Line Chart)
   - Dataset: `gold_pgr_funnel_daily`
   - Metric: `submitted_cases`
   - Time Column: `metric_date`
   - Time Range: Last 30 days
   - Time Granularity: Day

#### Dashboard 2: Resolution & SLA

**Charts:**
1. **Resolution Rate** (Big Number with %)
   - Dataset: `gold_pgr_case_lifecycle`
   - Metric: `resolved_complaints / complaints_count * 100`
   - Time filter: Last 30 days

2. **Average TAT by Ward** (Bar Chart)
   - Dataset: `gold_pgr_case_lifecycle`
   - Metric: `avg_tat_hours`
   - Dimension: `ward_id`
   - Group by: `ward_id`
   - Filter: `last_status = 'RESOLVED'`

3. **SLA Breaches Over Time** (Line Chart)
   - Dataset: `gold_pgr_sla_breaches`
   - Metric: `breached_cases`
   - Time Column: `breach_time`
   - Time Range: Last 30 days
   - Time Granularity: Day

4. **SLA Breaches by Priority** (Bar Chart)
   - Dataset: `gold_pgr_sla_breaches`
   - Metric: `breached_cases`
   - Dimension: `priority`
   - Group by: `priority`

#### Dashboard 3: Daily Funnel & Backlog

**Charts:**
1. **Daily Funnel** (Multi-Line Chart)
   - Dataset: `gold_pgr_funnel_daily`
   - Metrics: `submitted_cases`, `assigned_events`, `resolved_cases`, `closed_cases`
   - Time Column: `metric_date`
   - Time Range: Last 30 days
   - Time Granularity: Day

2. **Backlog Trend** (Area Chart)
   - Dataset: `gold_pgr_backlog_daily`
   - Metric: `open_cases`
   - Time Column: `metric_date`
   - Time Range: Last 30 days
   - Time Granularity: Day

3. **Backlog by Status** (Stacked Bar Chart)
   - Dataset: `gold_pgr_backlog_daily`
   - Metric: `open_cases`
   - Dimensions: `metric_date`, `status`
   - Time Column: `metric_date`
   - Time Range: Last 7 days
   - Group by: `status`

4. **Backlog by Ward** (Table)
   - Dataset: `gold_pgr_backlog_daily`
   - Metric: `open_cases`
   - Dimensions: `ward_id`, `status`, `channel`
   - Time filter: Latest date
   - Order by: `open_cases` DESC

## Sample SQL Queries for Superset

### Total Complaints by Ward (Last 30 Days)

```sql
SELECT 
    ward_id,
    COUNT(DISTINCT complaint_id) as complaints_count,
    COUNT(DISTINCT CASE WHEN last_status = 'RESOLVED' THEN complaint_id END) as resolved_count
FROM iceberg.gold.gold_pgr_case_lifecycle
WHERE submitted_time >= CURRENT_DATE - INTERVAL '30' DAY
GROUP BY ward_id
ORDER BY complaints_count DESC
```

### Resolution Rate by Channel

```sql
SELECT 
    channel,
    COUNT(DISTINCT complaint_id) as total_complaints,
    COUNT(DISTINCT CASE WHEN last_status = 'RESOLVED' THEN complaint_id END) as resolved_complaints,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN last_status = 'RESOLVED' THEN complaint_id END) / 
          COUNT(DISTINCT complaint_id), 2) as resolution_rate_pct
FROM iceberg.gold.gold_pgr_case_lifecycle
WHERE submitted_time >= CURRENT_DATE - INTERVAL '30' DAY
GROUP BY channel
ORDER BY resolution_rate_pct DESC
```

### Daily Funnel Metrics

```sql
SELECT 
    metric_date,
    SUM(submitted_cases) as submitted,
    SUM(assigned_events) as assigned,
    SUM(resolved_cases) as resolved,
    SUM(closed_cases) as closed
FROM iceberg.gold.gold_pgr_funnel_daily
WHERE metric_date >= CURRENT_DATE - INTERVAL '30' DAY
GROUP BY metric_date
ORDER BY metric_date ASC
```

### Top 10 Wards with Open Complaints

```sql
SELECT 
    ward_id,
    SUM(open_cases) as open_complaints,
    channel
FROM iceberg.gold.gold_pgr_backlog_daily
WHERE metric_date = (SELECT MAX(metric_date) FROM iceberg.gold.gold_pgr_backlog_daily)
GROUP BY ward_id, channel
ORDER BY open_complaints DESC
LIMIT 10
```

## Troubleshooting

### Trino Connector Issues

**Problem**: "Could not load database driver: TrinoEngineSpec"

**Solution**:
```bash
# Install Trino connector in Superset container
docker exec -it dap-superset pip install sqlalchemy-trino

# Restart Superset to load the new driver
docker compose restart superset

# Wait for Superset to restart (about 30 seconds)
docker compose ps superset

# Verify installation
docker exec -it dap-superset pip list | grep trino
# Should show: sqlalchemy-trino
```

**Problem**: "Trino" option not appearing in database list

**Solution**:
- Ensure `sqlalchemy-trino` is installed: `docker exec -it dap-superset pip list | grep trino`
- Restart Superset: `docker compose restart superset`
- Clear browser cache and refresh Superset UI
- Check Superset logs: `docker compose logs superset | grep -i trino`

### Connection Issues

**Problem**: "Connection refused" when testing Trino connection

**Solution**:
```bash
# Verify Trino is running
docker compose ps trino

# Check Trino logs
docker compose logs trino

# Verify Trino is accessible from Superset container
docker exec -it dap-superset sh -c "curl -s http://trino:8080/v1/info || echo 'Connection failed'"

# Verify Trino is accessible from host
docker exec -it dap-trino trino --server http://trino:8080 -e "SELECT 1"
```

### SQL Errors

**Problem**: "Schema not found" or "Table not found"

**Solution**:
```bash
# Verify schemas exist
docker exec -it dap-trino trino --server http://trino:8080 -e "SHOW SCHEMAS FROM iceberg"

# Verify tables exist
docker exec -it dap-trino trino --server http://trino:8080 -e "SHOW TABLES FROM iceberg.gold"

# Verify PGR tables
docker exec -it dap-trino trino --server http://trino:8080 -e "SELECT COUNT(*) FROM iceberg.gold.gold_pgr_case_lifecycle"
```

### Performance Issues

**Problem**: Charts loading slowly

**Solutions**:
1. **Add time filters** to queries (limit date range)
2. **Use materialized views** (future enhancement)
3. **Add LIMIT clauses** to large datasets
4. **Filter by specific wards/channels** to reduce data volume

### Date/Time Issues

**Problem**: Time column not recognized

**Solution**:
- Ensure time column is set correctly in dataset configuration
- Use `metric_date` for daily tables
- Use `submitted_time` for case lifecycle table
- Set time granularity to "Day" for daily data

## Advanced Configuration

### Custom Metrics

You can create custom metrics in Superset for common PGR KPIs:

**Resolution Rate**:
```sql
COUNT(DISTINCT CASE WHEN last_status = 'RESOLVED' THEN complaint_id END) * 100.0 / 
COUNT(DISTINCT complaint_id)
```

**Average TAT (Time to Resolve)**:
```sql
AVG(t_submit_to_resolve_hours)
```

**SLA Breach Rate**:
```sql
COUNT(DISTINCT CASE WHEN breach_flag = true THEN complaint_id END) * 100.0 / 
COUNT(DISTINCT complaint_id)
```

### Row-Level Security (Future)

For multi-tenant scenarios, you can add row-level security:
- Create separate datasets per tenant
- Use SQLAlchemy URI with query filters
- Implement custom security rules

## Reference

- **Superset Documentation**: https://superset.apache.org/docs/
- **Trino Connector**: https://superset.apache.org/docs/databases/trino
- **PGR Data Models**: See [dbt/models/pgr_README.md](dbt/models/pgr_README.md)

---

**Last Updated**: January 2025
