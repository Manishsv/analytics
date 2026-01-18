#!/usr/bin/env python3
"""
Kafka consumer service for real-time ingestion to Bronze tables.

Consumes events from Kafka topics and writes them to Iceberg Bronze tables via Trino.
Supports batching for performance and graceful shutdown.
"""
import os
import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import trino

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "pgr-events")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "bronze-ingestion")
TRINO_HOST = os.getenv("TRINO_HOST", "localhost")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8090"))
TRINO_USER = os.getenv("TRINO_USER", "trino")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
FLUSH_INTERVAL_SEC = int(os.getenv("FLUSH_INTERVAL_SEC", "5"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(sig, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_flag
    logger.info("Received shutdown signal, flushing batch and exiting...")
    shutdown_flag = True


def validate_event(event: Dict[str, Any]) -> bool:
    """Validate event structure matches Bronze table schema."""
    required_fields = [
        "event_date", "event_time", "tenant_id", "service", 
        "entity_type", "entity_id", "event_type", "status"
    ]
    for field in required_fields:
        if field not in event:
            logger.warning(f"Event missing required field '{field}': {event}")
            return False
    return True


def format_value(value: Any) -> str:
    """Format value for SQL INSERT statement."""
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        # Escape single quotes
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, dict):
        # JSON fields
        return f"'{json.dumps(value).replace(chr(39), chr(39)+chr(39))}'"
    elif isinstance(value, datetime):
        if isinstance(value, datetime) and value.time() == datetime.min.time():
            return f"DATE '{value.strftime('%Y-%m-%d')}'"
        else:
            return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    else:
        return f"'{str(value)}'"


def build_insert_sql(events: List[Dict[str, Any]], table: str = "iceberg.bronze.service_events_raw") -> str:
    """Build SQL INSERT statement for batch of events."""
    if not events:
        return None
    
    # Column order matching Bronze table schema
    columns = [
        "event_date", "event_time", "tenant_id", "service", "entity_type", 
        "entity_id", "event_type", "status", "actor_type", "actor_id", 
        "channel", "ward_id", "locality_id", "attributes_json", "raw_payload"
    ]
    
    values_list = []
    for event in events:
        values = []
        for col in columns:
            value = event.get(col)
            
            # Handle date/timestamp columns - Trino expects DATE '...' and TIMESTAMP '...'
            if col == "event_date" and value:
                if isinstance(value, str):
                    values.append(f"DATE '{value}'")
                elif isinstance(value, datetime):
                    values.append(f"DATE '{value.strftime('%Y-%m-%d')}'")
                else:
                    values.append("NULL")
                continue
            elif col == "event_time" and value:
                if isinstance(value, str):
                    # Ensure timestamp format has both date and time
                    if len(value) == 10:  # Just date
                        values.append(f"TIMESTAMP '{value} 00:00:00'")
                    else:
                        values.append(f"TIMESTAMP '{value}'")
                elif isinstance(value, datetime):
                    values.append(f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'")
                else:
                    values.append("NULL")
                continue
            elif col == "attributes_json" and isinstance(value, dict):
                # Convert dict to JSON string
                formatted_value = json.dumps(value)
            else:
                formatted_value = value
            
            values.append(format_value(formatted_value))
        values_list.append(f"({', '.join(values)})")
    
    sql = f"INSERT INTO {table} VALUES\n"
    sql += ",\n".join(values_list) + ";"
    
    return sql


def insert_batch(events: List[Dict[str, Any]], conn: trino.dbapi.Connection) -> bool:
    """Insert batch of events into Bronze table via Trino."""
    if not events:
        return True
    
    try:
        sql = build_insert_sql(events)
        if not sql:
            return True
        
        # Log SQL for debugging (first 500 chars)
        logger.debug(f"Executing SQL (first 500 chars): {sql[:500]}...")
        
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.fetchall()  # Consume results
        cursor.close()
        
        logger.info(f"✅ Inserted {len(events)} events into Bronze table")
        return True
    except Exception as e:
        # Log the SQL that failed for debugging
        sql = build_insert_sql(events)
        if sql:
            logger.error(f"❌ Error inserting batch: {e}")
            logger.error(f"Failed SQL (first 1000 chars): {sql[:1000]}...")
        else:
            logger.error(f"❌ Error inserting batch: {e}", exc_info=True)
        return False


def main():
    """Main consumer loop."""
    global shutdown_flag
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Connect to Trino
    logger.info(f"Connecting to Trino at {TRINO_HOST}:{TRINO_PORT}...")
    trino_conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog="iceberg",
        schema="bronze"
    )
    logger.info("✅ Connected to Trino")
    
    # Connect to Kafka
    logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
    logger.info(f"  Topic: {KAFKA_TOPIC}")
    logger.info(f"  Group ID: {KAFKA_GROUP_ID}")
    
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        consumer_timeout_ms=1000  # Poll timeout
    )
    
    logger.info("✅ Connected to Kafka")
    
    # Batch processing
    batch: List[Dict[str, Any]] = []
    last_flush = time.time()
    total_processed = 0
    total_failed = 0
    
    logger.info(f"Starting consumer loop (batch_size={BATCH_SIZE}, flush_interval={FLUSH_INTERVAL_SEC}s)...")
    
    try:
        while not shutdown_flag:
            # Poll for messages
            message_pack = consumer.poll(timeout_ms=1000)
            
            for topic_partition, messages in message_pack.items():
                for message in messages:
                    try:
                        event = message.value
                        if not event:
                            continue
                        
                        # Validate event
                        if not validate_event(event):
                            total_failed += 1
                            continue
                        
                        # Add to batch
                        batch.append(event)
                        total_processed += 1
                        
                        # Flush if batch is full
                        if len(batch) >= BATCH_SIZE:
                            if insert_batch(batch, trino_conn):
                                batch.clear()
                            else:
                                # On error, keep batch for retry (or implement DLQ)
                                total_failed += len(batch)
                                batch.clear()
                    
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        total_failed += 1
            
            # Flush if interval elapsed
            if batch and (time.time() - last_flush) >= FLUSH_INTERVAL_SEC:
                if insert_batch(batch, trino_conn):
                    batch.clear()
                else:
                    total_failed += len(batch)
                    batch.clear()
                last_flush = time.time()
        
        # Final flush on shutdown
        if batch:
            logger.info(f"Flushing final batch of {len(batch)} events...")
            if insert_batch(batch, trino_conn):
                batch.clear()
            else:
                total_failed += len(batch)
                batch.clear()
    
    except KafkaError as e:
        logger.error(f"Kafka error: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info(f"Shutting down... Total processed: {total_processed}, Failed: {total_failed}")
        consumer.close()
        trino_conn.close()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    main()
