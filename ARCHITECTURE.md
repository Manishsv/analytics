# Data Analytics Platform - Architecture Document

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Data Architecture](#data-architecture)
5. [Component Details](#component-details)
6. [Data Flow](#data-flow)
7. [Storage & Catalog](#storage--catalog)
8. [Security & Governance](#security--governance)
9. [Deployment](#deployment)
10. [Scalability & Performance](#scalability--performance)

---

## Overview

The Data Analytics Platform is a modern, cloud-native analytics stack built on open-source technologies, designed to support multi-tenant event analytics with natural language querying capabilities.

### Key Capabilities

- **Event Ingestion**: Support for streaming and batch event data (PGR, Sales, etc.)
- **Data Lakehouse Architecture**: Bronze/Silver/Gold layered data processing
- **Semantic Layer**: MetricFlow-powered metrics and dimensions
- **Natural Language Queries**: AI-powered NLQ agent for business users
- **BI Integration**: Superset for dashboards and visualizations
- **Scalable Storage**: Iceberg tables on S3-compatible storage

### Design Principles

- **Open Source**: Built on open-source technologies
- **Schema Evolution**: Iceberg tables support schema changes
- **Time Travel**: Iceberg enables point-in-time queries
- **Semantic Consistency**: MetricFlow ensures metric definitions are consistent
- **Guardrails**: AI agent enforces security and performance limits

---
## Architecture Rationale

This architecture is designed to solve a recurring problem in government and enterprise analytics: transactional systems are excellent at running operations, but poorly suited for flexible, cross-cutting analytics—especially when many departments, tenants, and services must be compared consistently over time. The platform therefore separates operational truth from analytical truth, and introduces a controlled pathway from raw events to trusted business metrics that can be queried safely—both through dashboards and natural language.

At the core is a simple principle: treat service activity as standardized events, land them in an immutable lake, transform them into stable analytics contracts, and expose them through a semantic layer rather than direct SQL. This makes analytics scalable across services (PGR, Sales, etc.), across tenants (multiple cities), and across time (historical trend analysis), without repeatedly rebuilding bespoke reports or fragile query logic.

The choice of a lakehouse (Iceberg on S3-compatible storage) provides durable, low-cost storage with the key properties analytics teams require: schema evolution, ACID-like consistency, partition pruning, and time travel. Nessie adds versioned cataloging so that datasets can be promoted, audited, and reproduced—particularly useful in regulated or multi-stakeholder environments. Trino provides a fast, flexible SQL execution layer that can query large datasets directly in object storage without proprietary infrastructure.

On top of this, the platform uses the Bronze/Silver/Gold pattern to enforce increasing levels of structure and trust. Bronze preserves raw data for audit and reprocessing; Silver standardizes and validates; Gold produces optimized marts that reflect business grains (case-level, daily funnel, backlog snapshots). This prevents downstream users from repeatedly reinventing transformations and keeps performance predictable.

A critical design decision is the inclusion of a semantic layer (MetricFlow). Without it, every dashboard, report, or agent must encode its own definitions of “complaints,” “resolution rate,” “SLA breach,” “sales,” “growth,” etc.—leading to inconsistency, disputes, and high maintenance. MetricFlow creates a single source of truth for metrics and dimensions, enabling governance, reuse, and controlled evolution of definitions as programs change.

Finally, the platform introduces natural language querying through an AI agent, but with strict guardrails. Rather than allowing an LLM to generate raw SQL against evolving datasets (which is fragile, difficult to govern, and risky), the agent is constrained to selecting approved metrics, dimensions, and filters from the semantic layer, and then executing through MetricFlow. This approach preserves the usability benefits of NLQ while maintaining security, performance controls, and semantic consistency.

In summary, this architecture is not just a technology stack—it is a governance and scale strategy: events to lakehouse, lakehouse to trusted marts, marts to semantic metrics, and metrics to safe self-service access (BI + NLQ). This combination enables multi-tenant service analytics that is auditable, consistent, and extensible as DIGIT services expand and evolve.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Sources                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   PGR API    │  │  Sales DB    │  │   Events     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼──────────────────┼──────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Ingestion Layer                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  File Upload / API / Batch Insert → MinIO (S3)              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Storage Layer (MinIO)                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │         s3://warehouse/                                      │   │
│  │         ├── bronze/    (Raw events)                          │   │
│  │         ├── silver/    (Conformed data)                      │   │
│  │         └── gold/      (Business marts)                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Catalog Layer (Nessie)                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Git-like catalog with branches, commits, time travel        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Processing Layer                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │   Trino (SQL)    │  │   dbt (ETL)      │  │  MetricFlow      │ │
│  │   Query Engine   │  │   Transformations│  │  Semantic Layer  │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘ │
└───────────┼──────────────────────┼──────────────────────┼───────────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Access Layer                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  AI Agent (NLQ)  │  │   Superset (BI)  │  │  Web Chat UI     │ │
│  │  FastAPI + LLM   │  │   Dashboards     │  │  Natural Lang    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User Query (NLQ)
    │
    ▼
┌─────────────────┐
│  Web UI / API   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI Agent       │──► Ollama (LLM) ──► Plan (metrics, dimensions, filters)
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MetricFlow     │──► Translate plan to SQL
│  (Semantic)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Trino          │──► Execute SQL against Iceberg tables
│  (Query Engine) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Nessie Catalog │──► Resolve table metadata
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MinIO (S3)     │──► Read Parquet data
└─────────────────┘
```

---

## Technology Stack

### Core Infrastructure

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Object Storage** | MinIO | Latest | S3-compatible storage for Iceberg data |
| **Table Format** | Apache Iceberg | Latest | Open table format with schema evolution |
| **Catalog** | Project Nessie | 0.103.2 | Git-like catalog for Iceberg tables |
| **Query Engine** | Trino | 455 | Distributed SQL query engine |
| **Transformations** | dbt Core | 1.11.2 | Data build tool for transformations |
| **Semantic Layer** | MetricFlow | 0.11.0 | Metrics and dimensions abstraction |

### Application Layer

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **AI Agent** | FastAPI + Python 3.10 | NLQ planning and execution |
| **LLM** | Ollama (gpt-oss:120b-cloud) | Natural language understanding |
| **Web UI** | HTML + JavaScript | Chat interface for queries |
| **BI Tool** | Apache Superset | Dashboards and visualizations |

### Data Formats

- **Storage**: Parquet (columnar, compressed)
- **Serialization**: JSON (events, attributes)
- **Partitioning**: Date-based, service-based

---

## Data Architecture

### Bronze/Silver/Gold Pattern

#### Bronze Layer (Raw Landing)

**Purpose**: Store raw, unprocessed events as received from source systems.

**Characteristics**:
- Minimal transformation (type casting only)
- Partitioned by `event_date` and `service`
- Retains all original fields + `raw_payload`
- Append-only (immutable)

**Example Tables**:
- `iceberg.bronze.service_events_raw` - All service events (PGR, etc.)
- `iceberg.bronze.sample_sales` - Sales transactions

**Schema Pattern**:
```sql
CREATE TABLE iceberg.bronze.service_events_raw (
    event_date DATE,
    event_time TIMESTAMP,
    tenant_id VARCHAR,
    service VARCHAR,
    entity_type VARCHAR,
    entity_id VARCHAR,
    event_type VARCHAR,
    status VARCHAR,
    actor_type VARCHAR,
    actor_id VARCHAR,
    channel VARCHAR,
    ward_id VARCHAR,
    locality_id VARCHAR,
    attributes_json VARCHAR,  -- Flexible JSON for varying attributes
    raw_payload VARCHAR        -- Full original payload
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['event_date', 'service']
);
```

#### Silver Layer (Conformed)

**Purpose**: Typed, validated, and normalized data ready for analytics.

**Characteristics**:
- Data quality checks (not-null, valid values)
- Type conversions and standardization
- Extracted attributes from JSON
- Filtered invalid records

**Example Models**:
- `silver_pgr_events` - Typed PGR events with extracted attributes
- `silver_sales` - Typed sales transactions

**Transformation Example**:
```sql
-- Extract from attributes_json
json_extract_scalar(attributes_json, '$.complaint_type') as complaint_type,
json_extract_scalar(attributes_json, '$.priority') as priority,
try_cast(json_extract_scalar(attributes_json, '$.sla_hours') as integer) as sla_hours
```

#### Gold Layer (Business Marts)

**Purpose**: Business-ready aggregates, facts, and dimensions for analytics.

**Characteristics**:
- Aggregated at business grain (e.g., case-level, daily)
- Denormalized for query performance
- Certified metrics and KPIs
- Optimized for common query patterns

**Example Models**:
- `gold_pgr_case_lifecycle` - One row per complaint with lifecycle metrics
- `gold_pgr_funnel_daily` - Daily funnel metrics
- `gold_pgr_backlog_daily` - Daily backlog snapshots
- `gold_sales_monthly` - Monthly sales aggregates

**Design Pattern**:
- Case-level facts (for TAT, SLA metrics)
- Event-level daily aggregates (for throughput trends)
- Snapshot tables (for point-in-time analysis)

---

## Component Details

### 1. MinIO (Object Storage)

**Role**: S3-compatible object storage for Iceberg table data.

**Configuration**:
- Bucket: `warehouse`
- Access: MinIO Console (port 9001) or S3 API (port 9000)
- Credentials: Configured via `.env`

**Storage Layout**:
```
s3://warehouse/
├── bronze/
│   ├── service_events_raw/
│   │   ├── event_date=2024-10-01/
│   │   │   └── service=PGR/
│   │   │       └── data.parquet
│   └── sample_sales/
├── silver/
│   └── silver_pgr_events/
└── gold/
    ├── gold_pgr_case_lifecycle/
    └── gold_sales_monthly/
```

### 2. Nessie (Catalog)

**Role**: Git-like catalog for Iceberg table metadata.

**Features**:
- Branching and versioning
- Time travel queries
- Schema evolution tracking
- In-memory for dev (can use PostgreSQL/JDBC for production)

**API**: REST API on port 19120

### 3. Trino (Query Engine)

**Role**: Distributed SQL engine for querying Iceberg tables.

**Configuration**:
- Port: 8090 (mapped from container port 8080)
- Catalog: `iceberg`
- Native S3 filesystem enabled (no Hadoop dependencies)
- Iceberg connector configured for Nessie catalog

**Key Capabilities**:
- SQL queries across Bronze/Silver/Gold
- Parquet file reading
- Partition pruning
- Query federation (future)

### 4. dbt (Transformations)

**Role**: Data transformation pipeline (Bronze → Silver → Gold).

**Structure**:
```
dbt/
├── models/
│   ├── bronze/
│   │   └── sources.yml      # Source table definitions
│   ├── silver/
│   │   ├── silver_sales.sql
│   │   └── pgr/
│   │       └── silver_pgr_events.sql
│   ├── gold/
│   │   ├── gold_sales_monthly.sql
│   │   └── pgr/
│   │       ├── gold_pgr_case_lifecycle.sql
│   │       ├── gold_pgr_funnel_daily.sql
│   │       └── gold_pgr_backlog_daily.sql
│   └── semantic/
│       ├── sales_monthly_semantic.yml
│       ├── pgr_case_lifecycle_semantic.yml
│       ├── metrics.yml
│       └── pgr_metrics.yml
└── dbt_project.yml
```

**Materialization Strategies**:
- Bronze sources: `view` (read-only references)
- Silver: `table` (typed, validated data)
- Gold: `table` (aggregated marts)
- Views: Not supported (Iceberg Nessie limitation)

### 5. MetricFlow (Semantic Layer)

**Role**: Abstract metrics and dimensions from underlying tables.

**Components**:
- **Semantic Models**: Map Gold tables to entities, dimensions, measures
- **Metrics**: Business metrics (counts, ratios, derived)
- **Time Spine**: Date dimension for time-based calculations

**Example Semantic Model**:
```yaml
semantic_models:
  - name: pgr_case_lifecycle
    model: ref('gold_pgr_case_lifecycle')
    entities:
      - name: complaint
        expr: complaint_id
    dimensions:
      - name: submitted_time
        type: time
      - name: ward_id
        type: categorical
    measures:
      - name: complaints
        agg: count_distinct
        expr: complaint_id
```

**Query Interface**:
```bash
mf query --metrics pgr_complaints --group-by complaint__ward_id
```

### 6. AI Agent Service (FastAPI)

**Role**: Natural language query planning and execution.

**Components**:
- **LLM Client** (Ollama): Converts NL → structured query plan
- **MetricFlow Client**: Executes planned queries
- **Guardrails**: Validates plans against allowlists
- **Rate Limiting**: Prevents abuse (60/min, 1000/hour)

**Flow**:
1. Receive NL query from user
2. LLM generates plan (metrics, dimensions, filters, time_granularity)
3. Validate plan against MetricFlow catalog (allowlist)
4. Auto-detect "which X has the most Y" queries and adjust plan
5. Compile safe WHERE clauses from filters (with case normalization)
6. Execute via MetricFlow
7. Post-process results (time aggregation if needed)
8. Return results + explanation

**API Endpoints**:
- `GET /health` - Health check
- `GET /catalog` - List available metrics/dimensions
- `POST /query` - Direct MetricFlow query
- `POST /nlq` - Natural language query

**Advanced Features**:
- **Time Granularity Detection**: Automatically detects "by days/weeks/months/years" and sets appropriate granularity
- **Top N Query Handling**: Detects "which X has the most Y" queries, aggregates across filter dimensions client-side
- **Case Sensitivity**: Normalizes status values to uppercase (e.g., "Closed" → "CLOSED")
- **Rate Limiting**: Token bucket algorithm (60 requests/min, 1000/hour per IP)
- **Query Explanation**: Returns metric definitions, dimensions used, filters applied, and generated WHERE clause
- **Structured Logging**: Logs request, plan, execution time, row count for observability

### 7. Web UI

**Role**: User-friendly interface for NLQ queries.

**Features**:
- Chat-like interface
- Query plan display
- Formatted table results (with automatic sorting and aggregation)
- User-friendly error messages with actionable suggestions
- Example queries
- **PGR Demo Mode**: Automated demo that runs 10 PGR queries sequentially
- **Persistent Catalog Sidebar**: Always-accessible metrics and dimensions discovery
- **Dimension Discovery**: Grouped display of available dimensions with usage hints
- **Time Granularity Support**: Automatic aggregation for week/month/year from day-level data
- **Top N Queries**: Client-side aggregation for "which X has the most Y" queries
- **Smart Formatting**: Number formatting, date formatting (ISO → readable), scientific notation conversion

**Technology**: Single-page HTML + JavaScript

**Demo Mode**:
- One-click button to run 10 pre-configured PGR queries
- Progress indicator with spinner and progress bar
- Sequential execution with configurable delays
- Stop/start controls
- Perfect for platform demonstrations

**Catalog Features**:
- Toggleable sidebar (always accessible)
- Metrics and dimensions grouped by domain (PGR, Sales)
- Tooltips with usage examples
- Auto-discovered from MetricFlow catalog

---

## Data Flow

### Event Ingestion Flow

```
1. Source System
   │
   ├─► File Upload ──► MinIO staging/
   │                        │
   │                        ├─► Batch INSERT ──► iceberg.bronze.*
   │                        │
   ├─► Kafka Producer ──► RedPanda Topic ──► Kafka Consumer ──► Trino ──► iceberg.bronze.*
   │                        (Real-time streaming, Kafka-compatible)
   │
   └─► API/Stream ──────────┘   (via Trino)
```

### Transformation Flow

```
Bronze (Raw)
    │
    ├─► dbt run silver_* ──► Silver (Typed)
    │                              │
    │                              ├─► dbt run gold_* ──► Gold (Marts)
    │                              │
    └─► MetricFlow Semantic Model ─┘
```

### Query Flow

```
User Query
    │
    ├─► Web UI ──► AI Agent ──► LLM (Plan)
    │                              │
    │                              ▼
    │                         MetricFlow
    │                              │
    └─► Superset ──────────────────┘
                              │
                              ▼
                         Trino
                              │
                              ▼
                    Nessie (Catalog)
                              │
                              ▼
                    MinIO (Parquet)
                              │
                              ▼
                         Results
```

---

## Storage & Catalog

### Iceberg Table Format

**Benefits**:
- **Schema Evolution**: Add/remove columns without rewriting data
- **Time Travel**: Query data at any point in time
- **Partition Evolution**: Change partitioning without full rewrite
- **ACID Transactions**: Consistent reads and writes
- **Metadata Management**: Efficient metadata with file-level statistics

**File Organization**:
- **All layers (Bronze/Silver/Gold) store data as Parquet files**
- Data files: Parquet format (compressed, columnar)
- Metadata files: JSON (manifests, snapshots)
- Stored in: `s3://warehouse/<schema>/<table>/`

**Storage Format**:
```sql
-- All Iceberg tables use PARQUET format
WITH (
    format = 'PARQUET',
    compression_codec = 'ZSTD'  -- Optional, defaults to ZSTD
)
```

**Why Parquet for All Layers?**:
- **Bronze**: Efficient storage of raw events, column pruning for selective reads
- **Silver**: Columnar format enables fast analytical queries during transformation
- **Gold**: Optimized for query performance, supports predicate pushdown

### Nessie Catalog

**Git-like Features**:
- Branches: `main`, `dev`, `feature/*`
- Commits: Track metadata changes
- Time Travel: Query tables at specific commits
- Merging: Merge branches (future)

**Catalog References**:
- Tables referenced by: `catalog.schema.table`
- Default branch: `main`
- Metadata stored: Table location, schema, partitions

### Partitioning Strategy

**Bronze Tables**:
- Partition by: `event_date`, `service`
- Rationale: Time-based queries, service isolation

**Silver Tables**:
- Typically no partitioning (smaller volume)
- Or partition by: `period_yyyymm` for time-series

**Gold Tables**:
- Partition by business grain (if needed)
- Example: `gold_pgr_backlog_daily` partitioned by `metric_date`

---

## Security & Governance

### Access Control

**Current State (Dev)**:
- MinIO: Single admin credentials
- Trino: No authentication (development mode)
- Nessie: In-memory (no persistence)

**Production Considerations**:
- MinIO: IAM policies, bucket policies
- Trino: LDAP/OAuth2 authentication
- Nessie: Database-backed with access control
- Agent API: API keys, OAuth2 tokens

### Data Governance

**Guardrails in AI Agent**:
- Allowlist validation (metrics/dimensions)
- Query timeouts (60 seconds)
- Row limits (1-1000)
- Rate limiting (60/min, 1000/hour per IP)

**Audit Trail**:
- Query explanations (metrics, dimensions, filters used)
- Structured logging (request → plan → execution → timing)
- Nessie catalog commits (metadata changes)

### Data Quality

**dbt Tests**:
- Not-null constraints on critical fields
- Uniqueness checks on primary keys
- Referential integrity between layers
- Accepted values for enumerations

### Multi-Tenant Data Isolation

**Approach**: Application-level tenant filtering using dbt variables and macros.

**Implementation**:
- **`tenant_filter` Macro**: Row-level security filtering in dbt models (`dbt/macros/tenant_filter.sql`)
- **Tenant Variable**: Passed via `--vars '{"tenant_id": "TENANT_001"}'` to dbt commands
- **Scope**: Model-level (materialized views, transformations)

**Usage Pattern**:
```sql
-- In any dbt model
SELECT *
FROM {{ ref('gold_pgr_case_lifecycle') }}
WHERE {{ tenant_filter() }}
  AND ward_id is not null
```

**Example Models**:
- `mv_pgr_ward_summary_tenant` - Tenant-isolated materialized view
- Automatically filters by `tenant_id` when variable is set

**Testing**: See `TESTING_MULTITENANCY.md` for detailed testing guide.

**Production Considerations**:
- Application layer must pass `tenant_id` variable per user/session
- Consider tenant-specific views for each tenant (e.g., `gold.mv_pgr_ward_summary_TENANT_001`)
- For PostgreSQL-backed systems, use native Row-Level Security (RLS)
- API layer should enforce tenant context before querying

**Limitations**:
- Current implementation: Application-level filtering (no database-level enforcement)
- Future: Database-level RLS for stronger isolation guarantees

### Testing & Validation

**Test Suite**:
- **Unit Tests**: Golden prompts, filter compilation, plan validation (`test_nlq_planning.py`)
- **Integration Tests**: End-to-end HTTP requests (`test_integration.py`)
- **Comprehensive AI Tests**: 34+ test cases covering all query types (`test_ai_comprehensive.py`)
  - Basic metric queries
  - Queries with dimensions and filters
  - "Which X has the most Y" queries
  - Time-based queries (days/weeks/months/years)
  - PGR-specific queries
  - Sales-specific queries
  - Edge cases and error handling
  - Response structure validation
  - Explanation accuracy
  - Case sensitivity for filters

**Test Coverage**:
- Natural language interpretation
- Query plan generation
- Filter handling (including case sensitivity)
- Time granularity detection
- Top N aggregation
- Error handling
- Response formatting
- Multi-tenant isolation (see `TESTING_MULTITENANCY.md`)

---

## Deployment

### Docker Compose Stack

**Services**:
```yaml
- minio: S3-compatible storage
- minio-init: Bucket initialization
- nessie: Catalog service
- trino: Query engine
- superset: BI tool (optional)
```

**Ports**:
- MinIO Console: 9001
- MinIO API: 9000
- Nessie: 19120
- Trino: 8090
- Superset: 8088

### Agent Service

**Local Development**:
```bash
source .venv310/bin/activate
uvicorn agent.app.main:app --reload --port 8000
```

**Production Options**:
- Docker container (see `agent/Dockerfile`)
- Kubernetes deployment
- Cloud-managed (AWS ECS, GCP Cloud Run)

### Environment Variables

```bash
# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123

# Agent
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud
DBT_PROJECT_DIR=./dbt
DBT_PROFILES_DIR=./dbt
```

---

## Scalability & Performance

### Horizontal Scaling

**Trino**:
- Add worker nodes for parallel query execution
- Coordinator + workers architecture
- Query distribution across workers

**MinIO**:
- Multi-node distributed MinIO cluster
- Erasure coding for redundancy
- Load balancing across nodes

**Agent Service**:
- Stateless FastAPI instances
- Load balancer (nginx, AWS ALB)
- Horizontal pod autoscaling (K8s)

### Performance Optimizations

**Storage**:
- Parquet columnar format (column pruning)
- Partition pruning (date/service filters)
- Compression (ZSTD codec)
- File-level statistics (min/max values)

**Query**:
- Materialized views (future)
- Query result caching (future)
- Predicate pushdown (Iceberg)
- Vectorized reads (Parquet)

**Catalog**:
- Metadata caching
- Batch metadata reads
- Lazy catalog loading

### Capacity Planning

**Current Dev Capacity**:
- Storage: Limited by Docker volume size
- Memory: 2-4GB per container
- CPU: Shared host resources

**Production Estimates** (per 1M events/day):
- Storage: ~10-50GB/year (compressed Parquet)
- Trino: 4-8 workers, 16GB RAM each
- MinIO: 3-5 nodes for HA
- Agent: 2-4 instances for redundancy

---

## Future Enhancements

### Short Term
- [x] PostgreSQL backend for Nessie (persistence)
- [x] Authentication for Trino/Agent (API key auth for Agent)
- [x] Query result caching (LRU cache with 5min TTL)
- [x] Additional semantic models (Sales, etc.)
- [x] PGR demo mode (automated query execution)
- [x] Dimension discovery UI
- [x] Comprehensive test suite
- [x] Time granularity support (day/week/month/year)
- [x] Top N query aggregation

### Medium Term
- [x] Real-time ingestion (Kafka/Event Streams with consumer service)
- [x] Materialized views for common queries (pre-aggregated tables: ward summary, monthly trends, ward+channel, sales geo)
- [x] Multi-tenant data isolation (tenant_filter macro, RLS patterns)
- [x] Advanced dbt tests (custom tests: SLA validation, TAT reasonableness, status transitions)

### Long Term
- [ ] Multi-region deployment
- [ ] Query federation across catalogs
- [ ] ML model integration (anomaly detection)
- [ ] Self-service data onboarding

---

## References

- [Iceberg Specification](https://iceberg.apache.org/spec/)
- [Nessie Documentation](https://projectnessie.org/)
- [Trino Documentation](https://trino.io/docs/)
- [dbt Documentation](https://docs.getdbt.com/)
- [MetricFlow Documentation](https://docs.transform.co/docs/metricflow)

---

**Last Updated**: January 2025  
**Version**: 1.1

### Recent Updates (v1.1)

**Web UI Enhancements** (January 2025):
- Added PGR Demo Mode with automated query execution
- Persistent catalog sidebar with dimension discovery
- Improved table formatting with automatic sorting
- Enhanced error messages with actionable suggestions
- Time granularity aggregation (week/month/year from day-level)
- Top N query aggregation client-side

**AI Agent Improvements** (January 2025):
- Case sensitivity normalization for status filters
- Time granularity detection in NLQ
- Top N query handling with client-side aggregation
- Improved error message parsing and translation
- Structured logging and observability

**Testing** (January 2025):
- Comprehensive test suite (34+ test cases)
- Golden prompts for regression testing
- Integration tests for end-to-end validation
