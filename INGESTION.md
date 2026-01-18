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

### Method 4: Real-Time Ingestion via Kafka (Recommended for Production Streams)

For real-time event streaming from applications, use Kafka to buffer events before writing to Bronze tables:

#### Architecture

```
Application → Kafka Topic → Kafka Consumer → Trino → iceberg.bronze.*
```

#### Step 1: Start RedPanda Services

```bash
# Start RedPanda (Kafka-compatible, no Zookeeper needed) and consumer service
docker compose up -d redpanda kafka-consumer

# Wait for services to be healthy
docker compose ps
```

#### Step 2: Publish Events to Kafka

**Option A: Use Python Producer Script**

```bash
# Install dependencies
pip install kafka-python

# Run producer (generates sample PGR events)
python scripts/kafka_producer.py
```

**Option B: Use RedPanda CLI (rpk)**

```bash
# Create topic (if not exists)
docker exec dap-redpanda rpk topic create pgr-events --partitions 1 --replicas 1

# Publish event via console producer
echo '{"event_date":"2024-12-17","event_time":"2024-12-17 10:00:00","tenant_id":"TENANT_001","service":"PGR","entity_type":"complaint","entity_id":"CMP_001","event_type":"CaseSubmitted","status":"OPEN","actor_type":"CITIZEN","actor_id":"CIT_001","channel":"WEB","ward_id":"WARD_001","locality_id":"LOC_001","attributes_json":{"complaint_type":"Water Supply","priority":"MEDIUM","sla_hours":72},"raw_payload":null}' | \
  docker exec -i dap-redpanda rpk topic produce pgr-events --format json
```

**Option C: Use Kafka Producer from Application (RedPanda is Kafka-compatible)**

```python
from kafka import KafkaProducer
import json

# RedPanda is fully Kafka protocol compatible
producer = KafkaProducer(
    bootstrap_servers=["localhost:19092"],  # External port for host access
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

event = {
    "event_date": "2024-12-17",
    "event_time": "2024-12-17 10:00:00",
    "tenant_id": "TENANT_001",
    "service": "PGR",
    "entity_type": "complaint",
    "entity_id": "CMP_001",
    "event_type": "CaseSubmitted",
    "status": "OPEN",
    # ... other fields
}

producer.send("pgr-events", value=event)
producer.flush()
```

#### Step 3: Consumer Automatically Writes to Bronze

The `kafka-consumer` service automatically:
- Consumes events from RedPanda topic (`pgr-events`) - RedPanda is Kafka protocol compatible
- Validates event structure
- Batches events (default: 100 events or 5 seconds)
- Inserts batches into `iceberg.bronze.service_events_raw` via Trino
- Commits Kafka offsets after successful insert

**Monitor Consumer Logs**:

```bash
# View consumer logs
docker logs -f dap-kafka-consumer

# Expected output:
# [INFO] Connected to Kafka (RedPanda)
# [INFO] Starting consumer loop (batch_size=100, flush_interval=5s)...
# [INFO] ✅ Inserted 100 events into Bronze table
```

#### Configuration

Environment variables (in `docker-compose.yml` or `.env`):

```bash
KAFKA_TOPIC=pgr-events              # RedPanda/Kafka topic name
KAFKA_GROUP_ID=bronze-ingestion     # Consumer group ID
BATCH_SIZE=100                       # Events per batch
FLUSH_INTERVAL_SEC=5                # Max seconds between flushes
TRINO_HOST=trino                     # Trino hostname
TRINO_PORT=8080                      # Trino port
TRINO_USER=trino                     # Trino user
```

#### Verification

```bash
# Check events in Bronze table
docker exec -it dap-trino trino --server http://trino:8080

# Query recent events
SELECT 
    event_date, 
    event_time, 
    entity_id, 
    event_type, 
    status
FROM iceberg.bronze.service_events_raw
WHERE event_date = CURRENT_DATE
ORDER BY event_time DESC
LIMIT 10;

# Check consumer lag using RedPanda CLI (rpk)
docker exec dap-redpanda rpk group describe bronze-ingestion
```

#### Benefits

- **Real-Time**: Events ingested within seconds of publishing
- **Resilient**: Kafka buffers events if downstream services are unavailable
- **Scalable**: Multiple consumers can process different partitions
- **Batch Optimization**: Reduces Trino insert overhead
- **Exactly-Once**: Kafka consumer commits offsets after successful insert

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
