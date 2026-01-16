# Data Analytics Platform - Next Steps Roadmap

## Current Foundation ✅

- **Trino** (SQL engine on port 8090)
- **Iceberg** (table format)
- **Nessie** (catalog on port 19120)
- **MinIO** (S3-compatible storage, native S3 filesystem)
- **Superset** (BI on port 8088)

All services are operational with Bronze schema and sample table successfully created and tested.

---

## Build-Out Order (Recommended)

### 1. Lock in the Platform Contract

#### Catalog Conventions

Create these schemas (namespaces) up front:

```sql
-- Raw ingested tables (minimal transforms)
CREATE SCHEMA IF NOT EXISTS iceberg.bronze;

-- Conformed tables (typed, deduped, canonical IDs)
CREATE SCHEMA IF NOT EXISTS iceberg.silver;

-- Star schema / marts / certified views
CREATE SCHEMA IF NOT EXISTS iceberg.gold;
```

#### Storage Conventions

- **Bronze**: Partition by ingestion date/period
- **Silver/Gold**: Partition by business time grain (e.g., `period_yyyymm`) + high-cardinality dimensions only when proven necessary

---

### 2. Add dbt Core (Transformations + Tests + Docs)

**Goal**: dbt is the "compiler" for Silver/Gold.

**Implementation Approach**:
- Option A: Run dbt as local Python venv (fastest dev)
- Option B: Run dbt as container service in compose (more platform-like)

**dbt Models to Implement First** (IQVIA sales example):

**Silver Layer:**
- `silver_dim_product` - Product dimension
- `silver_dim_pack` - Pack dimension
- `silver_dim_geo` - Geography dimension
- `silver_dim_time` - Time dimension
- `silver_dim_channel` - Channel dimension
- `silver_fact_sales` - Typed + deduped sales facts

**Gold Layer:**
- `gold_fact_sales` - Fact table at chosen grain
- `gold_v_sales_monthly` - Certified view joining key dimensions

**dbt Tests (Minimum)**:
- Uniqueness on primary keys
- Not null on critical keys
- Accepted values for channels
- Referential integrity between facts and dimensions

**dbt Configuration**:
- Profile: `trino` connector
- Connection: `http://localhost:8090` (host port)
- Catalog: `iceberg`
- Default schemas: Bronze (source), Silver/Gold (models)

**dbt Project Structure** (✅ Created):
```
dbt/
  dbt_project.yml       # Project configuration
  profiles.yml          # Trino connection (dev only)
  packages.yml          # dbt packages
  models/
    bronze/sources.yml  # Bronze source declarations
    silver/
      silver_sales.sql  # First Silver model
    gold/
      gold_sales_monthly.sql  # Aggregated Gold fact
      v_sales_monthly.sql     # Certified view
```

**Quick Start**:
```bash
cd dbt
pip install dbt-trino
dbt debug    # Verify connection
dbt run      # Build all models
dbt test     # Run tests
```

---

### 3. Add MetricFlow (Semantic Layer)

**Goal**: Define certified business metrics once and let both BI and the agent use them consistently.

**Start with Minimal Semantic Model**:

**Entity**: `sales`

**Measures**:
- `value_lc` - Local currency value
- `standard_units` - Standardized units

**Dimensions**:
- `time` - Time period (quarter, month, year)
- `geo` - Geography hierarchy
- `product_hierarchy` - Product hierarchy
- `channel` - Sales channel

**Metrics**:
- `sales_value_lc` = `sum(value_lc)`
- `sales_volume_su` = `sum(standard_units)`
- `avg_price_lc_per_su` = `sales_value_lc / sales_volume_su`
- `sales_value_lc_yoy_growth_pct` - Year-over-year growth percentage

**Operational Rule**: MetricFlow should point only to Gold models/views (and selectively Silver), never Bronze.

---

### 4. Add AI Agent Service (LLM-pluggable)

**Goal**: NL → semantic request → MetricFlow query → Trino execution → explained answer.

**Minimal "Tools" the Agent Needs**:

1. **`metrics.search()`** - List metrics/dimensions/segments
2. **`metrics.query()`** - Execute a metric query (MetricFlow)
3. **`sql.execute_readonly()`** - Optional fallback, still allowlisted to gold views
4. **`explain()`** - Format results + disclose definitions/filters

**Guardrails to Implement Immediately**:
- **Allowlist schemas**: Only `iceberg.gold` (and maybe specific semantic views)
- **Query timeouts**: Max query execution time
- **Row limits**: Max rows returned per query
- **Mandatory disclosure**: Metric names + time grain + filters + segment version

**Implementation**:
- Python service (FastAPI/Flask) with LLM integration
- Tool calling interface for metrics/SQL operations
- Result formatting and explanation generation

---

### 5. Optionally Integrate Superset with Governed Objects

**Superset should query**:
- MetricFlow outputs (if exposed), or
- `iceberg.gold` certified views

**Avoid**: Giving Superset direct access to Bronze.

**Configuration**:
- Add Trino datasource pointing to `iceberg.gold` schema
- Create dashboards from certified Gold views
- Use MetricFlow-generated queries if available

---

## Definition of Done - MVP Milestone

The platform MVP is complete when:

1. ✅ **IQVIA raw file lands in `iceberg.bronze.*`**
   - Raw data ingestion working
   - Data partitioned by ingestion period

2. ✅ **dbt builds `silver.*` and `gold.*` successfully**
   - Silver transformations: deduplication, typing, canonical IDs
   - Gold transformations: star schema, marts, certified views
   - All dbt tests passing

3. ✅ **MetricFlow returns "Sales" and "YoY growth" for a slice** (brand/state/quarter)
   - Semantic model defined and validated
   - Metrics queryable via MetricFlow API
   - Results returned for specific dimensions/filters

4. ✅ **Agent answers: "Sales in Maharashtra last quarter and YoY growth"** using MetricFlow and shows the metric definitions used
   - Agent can parse natural language query
   - Agent calls MetricFlow correctly
   - Agent executes query via Trino
   - Agent formats and explains results with metric definitions

---

## Quick Reference

### Current Services

| Service | Port | Purpose |
|---------|------|---------|
| MinIO Console | 9001 | Object storage management |
| MinIO API | 9000 | S3-compatible API |
| Nessie | 19120 | Iceberg catalog (Nessie API) |
| Trino | 8090 | SQL query engine |
| Superset | 8088 | BI dashboard |

### Schema Structure

```
iceberg.bronze.*     # Raw ingested data
iceberg.silver.*     # Conformed/typed data
iceberg.gold.*       # Star schema / marts
```

### Warehouse Location

All Iceberg tables stored at: `s3://warehouse/` (MinIO)

---

## Next Immediate Actions

1. Create Silver and Gold schemas in Trino
2. Set up dbt project structure
3. Create first Silver model from Bronze sample data
4. Implement first Gold model/view
5. Add dbt tests
6. Configure MetricFlow semantic model
7. Build Agent service skeleton
8. Integrate Agent → MetricFlow → Trino flow
