# Testing Real-Time Ingestion Pipeline

This guide explains how to test the real-time ingestion pipeline and understand the data flow from RedPanda to Bronze, Silver, and Gold tables.

## Current Architecture

```
RedPanda Topic → Kafka Consumer → Trino → iceberg.bronze.service_events_raw
                                                              ↓
                                                      (Manual: dbt run)
                                                              ↓
                                                    iceberg.silver.*
                                                              ↓
                                                      (Manual: dbt run)
                                                              ↓
                                                      iceberg.gold.*
```

**Important**: Currently, `dbt run` is **not automatic**. Events flow automatically from RedPanda → Bronze, but Silver and Gold transformations require manual execution.

## Testing Steps

### Step 1: Start Services

```bash
# Start RedPanda and consumer
docker compose up -d redpanda kafka-consumer

# Verify services are running
docker compose ps | grep -E "redpanda|kafka-consumer"

# Check consumer logs (should show "✅ Connected")
docker logs -f dap-kafka-consumer
```

### Step 2: Create Topic (if not exists)

```bash
# Topic auto-creates, but you can verify:
docker exec dap-redpanda rpk topic list

# Or create explicitly:
docker exec dap-redpanda rpk topic create pgr-events --partitions 1 --replicas 1
```

### Step 3: Produce Test Events

**Option A: Use Python Producer Script**

```bash
# Install dependencies (if not already installed)
pip install kafka-python

# Run producer (sends 1 event per second)
python scripts/kafka_producer.py

# Press Ctrl+C to stop after sending a few events
```

**Option B: Send Single Event via CLI**

```bash
# Send a single event
echo '{
  "event_date": "2024-12-17",
  "event_time": "2024-12-17 10:00:00",
  "tenant_id": "TENANT_001",
  "service": "PGR",
  "entity_type": "complaint",
  "entity_id": "CMP_TEST_001",
  "event_type": "CaseSubmitted",
  "status": "OPEN",
  "actor_type": "CITIZEN",
  "actor_id": "CIT_001",
  "channel": "WEB",
  "ward_id": "WARD_001",
  "locality_id": "LOC_001",
  "attributes_json": {"complaint_type": "Water Supply", "priority": "MEDIUM", "sla_hours": 72},
  "raw_payload": null
}' | docker exec -i dap-redpanda rpk topic produce pgr-events --format json
```

**Option C: Use Python Script Directly**

```python
from kafka import KafkaProducer
import json
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers=["localhost:19092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

event = {
    "event_date": datetime.now().date().isoformat(),
    "event_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "tenant_id": "TENANT_001",
    "service": "PGR",
    "entity_type": "complaint",
    "entity_id": f"CMP_{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "event_type": "CaseSubmitted",
    "status": "OPEN",
    "actor_type": "CITIZEN",
    "actor_id": "CIT_001",
    "channel": "WEB",
    "ward_id": "WARD_001",
    "locality_id": "LOC_001",
    "attributes_json": {"complaint_type": "Water Supply", "priority": "MEDIUM", "sla_hours": 72},
    "raw_payload": None
}

producer.send("pgr-events", value=event)
producer.flush()
print(f"✅ Event sent: {event['entity_id']}")
```

### Step 4: Verify Events in Bronze Table

```bash
# Connect to Trino
docker exec -it dap-trino trino --server http://trino:8080

# Query Bronze table for recent events
SELECT 
    event_date,
    event_time,
    entity_id,
    event_type,
    status,
    ward_id
FROM iceberg.bronze.service_events_raw
WHERE event_date = CURRENT_DATE
ORDER BY event_time DESC
LIMIT 10;

# Count events from today
SELECT COUNT(*) as today_events
FROM iceberg.bronze.service_events_raw
WHERE event_date = CURRENT_DATE;
```

**Expected**: Events should appear within **5-10 seconds** of sending (depending on batch size and flush interval).

### Step 5: Check Consumer Logs

```bash
# View consumer logs
docker logs -f dap-kafka-consumer

# Look for:
# - "[INFO] ✅ Inserted 100 events into Bronze table" (or fewer if batch flushed)
# - Any error messages
```

### Step 6: Transform to Silver and Gold (Manual)

**Important**: Silver and Gold tables are **not updated automatically**. You must run dbt manually:

```bash
cd dbt
source ../.venv310/bin/activate  # or your venv path

# Run Silver transformations
dbt run --select silver_pgr_events --profiles-dir .

# Run Gold transformations
dbt run --select gold_pgr_* --profiles-dir .

# Or run everything
dbt run --profiles-dir .
```

**Verify transformations:**

```sql
-- Check Silver
SELECT COUNT(*) 
FROM iceberg.silver.pgr.silver_pgr_events
WHERE event_date = CURRENT_DATE;

-- Check Gold (case lifecycle)
SELECT COUNT(*) 
FROM iceberg.gold.pgr.gold_pgr_case_lifecycle
WHERE submit_date = CURRENT_DATE;
```

## Complete End-to-End Test

```bash
# 1. Start services
docker compose up -d redpanda kafka-consumer

# 2. Send a test event
python scripts/kafka_producer.py
# Let it run for ~30 seconds to send ~30 events, then Ctrl+C

# 3. Wait a few seconds for consumer to flush batch
sleep 10

# 4. Verify in Bronze
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT COUNT(*) FROM iceberg.bronze.service_events_raw WHERE event_date = CURRENT_DATE;"

# 5. Transform to Silver/Gold
cd dbt && dbt run --profiles-dir .

# 6. Verify in Gold
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT COUNT(*) FROM iceberg.gold.pgr.gold_pgr_case_lifecycle WHERE submit_date = CURRENT_DATE;"
```

## Monitoring

### Check Consumer Status

```bash
# View consumer group status (RedPanda)
docker exec dap-redpanda rpk group describe bronze-ingestion

# Should show:
# - Consumer ID
# - Partition assignments
# - Current offsets
```

### Check Topic Status

```bash
# List topics
docker exec dap-redpanda rpk topic list

# Describe topic
docker exec dap-redpanda rpk topic describe pgr-events

# Should show:
# - Partition count
# - Replication factor
# - Message count
```

## Troubleshooting

### Events Not Appearing in Bronze

1. **Check consumer is running:**
   ```bash
   docker ps | grep kafka-consumer
   ```

2. **Check consumer logs:**
   ```bash
   docker logs dap-kafka-consumer | tail -20
   ```

3. **Check consumer connected to RedPanda:**
   - Should see "✅ Connected to Kafka" in logs

4. **Check batch size/flush interval:**
   - Default: 100 events or 5 seconds
   - Small batches may take 5 seconds to flush

5. **Check event schema:**
   - Events must match Bronze table schema exactly
   - Check consumer logs for validation errors

### Consumer Restarting

1. **Check Trino connection:**
   ```bash
   docker exec dap-kafka-consumer python -c "import trino; print('Trino client OK')"
   ```

2. **Check RedPanda connectivity:**
   ```bash
   docker exec dap-kafka-consumer ping -c 1 redpanda
   ```

### Silver/Gold Not Updating

**Expected Behavior**: Silver and Gold tables are **NOT automatically updated**. They require manual `dbt run` execution.

**Options for Automation** (future enhancement):
- Scheduled cron job: `*/5 * * * * cd /path/to/dbt && dbt run`
- dbt Cloud scheduling
- Event-driven dbt (listen to Bronze table changes)
- Airflow/Dagster for orchestration

## Performance Tips

1. **Batch Size**: Larger batches (e.g., 500) = fewer Trino inserts but higher latency
2. **Flush Interval**: Lower interval (e.g., 2s) = faster visibility but more inserts
3. **Consumer Scaling**: Run multiple consumer instances for parallel processing

## Next Steps

For **automatic Silver/Gold updates**, consider:
1. Scheduled dbt runs (cron)
2. Event-driven dbt triggers
3. Orchestration tool (Airflow, Dagster, Prefect)
4. Stream processing (dbt-materialize, Flink, Spark Streaming)
