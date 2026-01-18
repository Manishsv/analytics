# Kafka Consumer Service

Real-time ingestion service that consumes events from RedPanda (Kafka-compatible) and writes them to Bronze tables via Trino.

## Architecture

```
RedPanda Topic → Kafka Consumer → Trino → iceberg.bronze.service_events_raw
```

## Features

- **Batching**: Groups events into batches (default: 100 events or 5 seconds)
- **Validation**: Validates event structure before insert
- **Error Handling**: Logs errors but continues processing
- **Graceful Shutdown**: Flushes pending batch on SIGTERM/SIGINT
- **Offset Management**: Auto-commits Kafka offsets after successful insert

## Configuration

Environment variables:

- `KAFKA_BOOTSTRAP_SERVERS`: RedPanda broker addresses (default: `redpanda:9092` for internal Docker network, `localhost:19092` for host access)
- `KAFKA_TOPIC`: Topic to consume from (default: `pgr-events`)
- `KAFKA_GROUP_ID`: Consumer group ID (default: `bronze-ingestion`)
- `TRINO_HOST`: Trino hostname (default: `localhost`)
- `TRINO_PORT`: Trino port (default: `8080`)
- `TRINO_USER`: Trino user (default: `trino`)
- `BATCH_SIZE`: Events per batch (default: `100`)
- `FLUSH_INTERVAL_SEC`: Max seconds between flushes (default: `5`)

## Running

### Via Docker Compose

```bash
# Start consumer service
docker compose up -d kafka-consumer

# View logs
docker logs -f dap-kafka-consumer

# Stop service
docker compose stop kafka-consumer
```

### Standalone (for development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run consumer
python kafka_consumer.py
```

## Event Schema

Events must match the `iceberg.bronze.service_events_raw` table schema:

```json
{
  "event_date": "2024-12-17",
  "event_time": "2024-12-17 10:00:00",
  "tenant_id": "TENANT_001",
  "service": "PGR",
  "entity_type": "complaint",
  "entity_id": "CMP_001",
  "event_type": "CaseSubmitted",
  "status": "OPEN",
  "actor_type": "CITIZEN",
  "actor_id": "CIT_001",
  "channel": "WEB",
  "ward_id": "WARD_001",
  "locality_id": "LOC_001",
  "attributes_json": {
    "complaint_type": "Water Supply",
    "priority": "MEDIUM",
    "sla_hours": 72
  },
  "raw_payload": null
}
```

## Testing

See `scripts/kafka_producer.py` for a sample producer that generates test events.

```bash
# Start consumer
docker compose up -d kafka-consumer

# Run producer
python scripts/kafka_producer.py

# Verify in Trino
docker exec -it dap-trino trino --server http://trino:8080

SELECT COUNT(*) 
FROM iceberg.bronze.service_events_raw 
WHERE event_date = CURRENT_DATE;
```
