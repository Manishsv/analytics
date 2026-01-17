# Data Analytics Platform - Docker Compose Setup

Base Docker Compose development environment with MinIO (S3) + Iceberg (Nessie catalog) + Trino + Superset.

## Prerequisites

- Docker Desktop (or Docker Engine) + Docker Compose v2
- git
- Optional: make

## Quick Start

1. **Start all services:**
   ```bash
   docker compose up -d
   ```

2. **Initialize Superset (one-time):**
   ```bash
   docker exec -it dap-superset superset db upgrade
   docker exec -it dap-superset superset fab create-admin \
     --username admin --firstname Admin --lastname User \
     --email admin@example.com --password admin
   docker exec -it dap-superset superset init
   ```

3. **Access services:**
   - MinIO Console: http://localhost:9001 (login with `.env` credentials)
   - Nessie API: http://localhost:19120/api/v2/config
   - Trino UI: http://localhost:8090 (changed from 8080 to avoid conflicts)
   - Superset: http://localhost:8088

## Smoke Test

Connect to Trino and create a test table:

```bash
docker exec -it dap-trino trino
```

Then run:

```sql
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;

-- Creates schema with default warehouse location (s3://warehouse/)
CREATE SCHEMA IF NOT EXISTS iceberg.bronze;

CREATE TABLE iceberg.bronze.sample_sales (
  period_yyyymm varchar,
  pack_id varchar,
  geo_id varchar,
  channel_id varchar,
  units bigint,
  standard_units bigint,
  value_lc double
)
WITH (
  format = 'PARQUET',
  partitioning = ARRAY['period_yyyymm']
);

INSERT INTO iceberg.bronze.sample_sales VALUES
('202412', 'PCK_001', 'GEO_345', 'RET', 12450, 62250, 1845000.0);

SELECT * FROM iceberg.bronze.sample_sales;
```

**Note**: Bronze/Silver/Gold schemas are pre-created. All tables use Nessie catalog and MinIO (native S3) storage.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture and design
- **[INGESTION.md](INGESTION.md)** - Data ingestion workflows and examples
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Roadmap and future enhancements
- **[dbt/models/pgr_README.md](dbt/models/pgr_README.md)** - PGR reference implementation guide
- **[agent/README.md](agent/README.md)** - AI Agent service documentation

**Quick Start**: Create Silver/Gold schemas:
```sql
CREATE SCHEMA IF NOT EXISTS iceberg.silver;
CREATE SCHEMA IF NOT EXISTS iceberg.gold;
```

## Architecture

- **Nessie**: Iceberg catalog (replaces Hive Metastore)
- **MinIO**: S3-compatible object storage
- **Trino**: SQL query engine with native S3 filesystem
- **Iceberg**: Table format with schema evolution
- **Superset**: BI dashboard tool

## Configuration Files

- `.env` - Environment variables (credentials)
- `docker-compose.yml` - Service definitions (includes Nessie, MinIO, Trino, Superset)
- `trino/etc/catalog/iceberg.properties` - Trino Iceberg catalog (Nessie + native S3)
- `superset/superset_config.py` - Superset feature flags

## Current Schemas

- `iceberg.bronze` - Raw ingested tables
- `iceberg.silver` - Conformed/typed tables
- `iceberg.gold` - Star schema / marts / certified views