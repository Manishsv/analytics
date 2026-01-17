# Data Ingestion Guide

This document describes how to add new data to the Data Analytics Platform.

## Current Architecture

The platform uses **Iceberg tables** stored in **MinIO (S3)** with the following layers:
- **Bronze**: Raw landing tables (e.g., `iceberg.bronze.service_events_raw`)
- **Silver**: Typed, conformed tables (dbt models)
- **Gold**: Business marts (dbt models)

## Ingestion Methods

### Method 1: Direct SQL INSERT (Recommended for Small Batches)

For development, testing, or small data loads, you can INSERT directly into Bronze tables via Trino:

```bash
# Connect to Trino
docker exec -it dap-trino trino --server http://trino:8080

# Insert PGR events
INSERT INTO iceberg.bronze.service_events_raw (
    event_date, event_time, tenant_id, service, entity_type, entity_id,
    event_type, status, actor_type, actor_id, channel, ward_id, locality_id,
    attributes_json, raw_payload
) VALUES
(DATE '2024-12-01', TIMESTAMP '2024-12-01 10:00:00', 'TENANT_001', 'PGR', 'complaint', 'CMP_001', ...),
...;
```

### Method 2: File Upload to MinIO + Trino INSERT (Recommended for Production)

For larger datasets or production workflows:

#### Step 1: Prepare Data File

Create a CSV or Parquet file with your data. For PGR events, the file should have columns matching `service_events_raw` table:

```csv
event_date,event_time,tenant_id,service,entity_type,entity_id,event_type,status,actor_type,actor_id,channel,ward_id,locality_id,attributes_json,raw_payload
2024-12-01,2024-12-01 10:00:00,TENANT_001,PGR,complaint,CMP_001,CaseSubmitted,OPEN,CITIZEN,CIT_001,WEB,WARD_001,LOC_001,"{""complaint_type"":""Water Supply"",""priority"":""MEDIUM"",""sla_hours"":72}",NULL
```

#### Step 2: Upload to MinIO

```bash
# Upload file to MinIO staging bucket
docker exec dap-minio mc cp /path/to/data.csv local/warehouse/staging/pgr_events_20241201.csv

# Or using MinIO Console: http://localhost:9001
# - Navigate to warehouse bucket
# - Create "staging" folder
# - Upload your file
```

#### Step 3: Create Temporary External Table (Optional)

You can create a temporary external table to read from the file:

```sql
-- Create external table pointing to S3 file
CREATE TABLE iceberg.bronze.temp_pgr_events_staging (
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
    attributes_json VARCHAR,
    raw_payload VARCHAR
)
WITH (
    format = 'CSV',  -- or 'PARQUET'
    external_location = 's3://warehouse/staging/pgr_events_20241201.csv',
    skip_header_line_count = 1  -- if CSV has header
);

-- Insert from staging table to Bronze
INSERT INTO iceberg.bronze.service_events_raw
SELECT * FROM iceberg.bronze.temp_pgr_events_staging;

-- Drop staging table (optional)
DROP TABLE iceberg.bronze.temp_pgr_events_staging;
```

#### Step 4: Or Use Trino INSERT with S3 Path Directly

```sql
-- Insert directly from S3 file (if supported by Trino connector)
INSERT INTO iceberg.bronze.service_events_raw
SELECT * FROM TABLE(
    EXTERNAL('s3://warehouse/staging/pgr_events_20241201.csv', 
             CSV, 
             'event_date DATE, event_time TIMESTAMP, ...')
);
```

### Method 3: Programmatic Ingestion (Python/API)

For automated ingestion from applications:

```python
import trino

# Connect to Trino
conn = trino.dbapi.connect(
    host='localhost',
    port=8090,
    user='trino',
    catalog='iceberg',
    schema='bronze'
)

cur = conn.cursor()

# Insert events
cur.execute("""
    INSERT INTO iceberg.bronze.service_events_raw VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (event_date, event_time, tenant_id, ...))

conn.commit()
```

## After Ingestion: Transform with dbt

Once data is in Bronze, run dbt to build Silver and Gold layers:

```bash
cd dbt
source ../.venv310/bin/activate

# Run Silver transformations
dbt run --select silver_pgr_events --profiles-dir .

# Run Gold transformations
dbt run --select gold_pgr_case_lifecycle gold_pgr_funnel_daily --profiles-dir .

# Or run everything
dbt run --profiles-dir .
```

## File Formats

### CSV
- Good for: Small files, human-readable, easy to generate
- Location: `s3://warehouse/staging/your_file.csv`
- Trino format: `format = 'CSV'`

### Parquet (Recommended for Production)
- Good for: Large files, columnar format, better performance
- Location: `s3://warehouse/staging/your_file.parquet`
- Trino format: `format = 'PARQUET'`

### JSON Lines (JSONL)
- Good for: Event streams, flexible schema
- Location: `s3://warehouse/staging/your_file.jsonl`
- Trino format: `format = 'JSON'`

## Partitioning

The `service_events_raw` table is partitioned by `event_date` and `service`:

```sql
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['event_date', 'service']
)
```

**Best Practice**: When inserting data, ensure:
- Data spans appropriate date ranges
- All rows for a given date/service are inserted together
- Avoid many small inserts (batch larger volumes)

## MinIO Console Access

- **URL**: http://localhost:9001
- **Username**: `minioadmin` (from `.env`)
- **Password**: `minioadmin123` (from `.env`)
- **Browse**: Navigate to `warehouse` bucket to see data files

## Example: Complete PGR Event Ingestion Workflow

```bash
# 1. Prepare CSV file: pgr_events_20241217.csv
# (with columns matching service_events_raw schema)

# 2. Upload to MinIO
docker exec -i dap-minio mc cp /path/to/pgr_events_20241217.csv local/warehouse/staging/

# 3. Connect to Trino
docker exec -it dap-trino trino --server http://trino:8080

# 4. Create staging table and insert
CREATE TABLE iceberg.bronze.temp_pgr_staging_20241217 (...) WITH (...);
INSERT INTO iceberg.bronze.service_events_raw SELECT * FROM iceberg.bronze.temp_pgr_staging_20241217;
DROP TABLE iceberg.bronze.temp_pgr_staging_20241217;

# 5. Run dbt transformations
cd dbt && dbt run --select silver_pgr_events+ --profiles-dir .
```

## Troubleshooting

### File Not Found
- Verify file exists in MinIO: `docker exec dap-minio mc ls local/warehouse/staging/`
- Check S3 path format: Use `s3://warehouse/...` not `file://...`

### Schema Mismatch
- Verify column names and types match Bronze table schema
- Use `DESCRIBE iceberg.bronze.service_events_raw` to check schema

### Partition Pruning Not Working
- Ensure `event_date` and `service` columns are populated correctly
- Verify date format matches table schema (DATE type)
