#!/usr/bin/env python3
"""
Kafka producer for testing real-time ingestion.

Generates sample PGR events and publishes them to Kafka topic.
Can be used for demo/testing the real-time ingestion pipeline.
"""
import json
import random
import time
import sys
from datetime import datetime, timedelta
from uuid import uuid4
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configuration
# RedPanda is Kafka-compatible - use external port for host access
KAFKA_BOOTSTRAP_SERVERS = "localhost:19092"  # RedPanda external port
KAFKA_TOPIC = "pgr-events"

# Sample data pools
TENANTS = ['TENANT_001', 'TENANT_002', 'TENANT_003']
WARDS = [f'WARD_{i:03d}' for i in range(1, 51)]
LOCALITIES = [f'LOC_{i:03d}' for i in range(1, 201)]
CHANNELS = ['WEB', 'MOBILE', 'CSC', 'COUNTER', 'API']
COMPLAINT_TYPES = [
    'Water Supply', 'Road Repair', 'Garbage Collection', 'Electricity',
    'Sewage', 'Street Lighting', 'Drainage', 'Park Maintenance',
    'Building Permission', 'Property Tax'
]
PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
ACTOR_IDS = [f'CIT_{i:05d}' for i in range(1, 1001)]

SLA_HOURS_MAP = {
    'CRITICAL': 4,
    'HIGH': 24,
    'MEDIUM': 72,
    'LOW': 168
}

EVENT_TYPES = ['CaseSubmitted', 'CaseAssigned', 'CaseResolved', 'CaseClosed']
STATUS_MAP = {
    'CaseSubmitted': 'OPEN',
    'CaseAssigned': 'ASSIGNED',
    'CaseResolved': 'RESOLVED',
    'CaseClosed': 'CLOSED'
}


def generate_event(event_type: str = None) -> dict:
    """Generate a sample PGR event."""
    if event_type is None:
        event_type = random.choice(EVENT_TYPES)
    
    event_time = datetime.now() - timedelta(hours=random.randint(0, 168))
    event_date = event_time.date()
    
    tenant_id = random.choice(TENANTS)
    complaint_id = f"CMP_{uuid4().hex[:8].upper()}"
    priority = random.choice(PRIORITIES)
    
    event = {
        "event_date": event_date.isoformat(),
        "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
        "tenant_id": tenant_id,
        "service": "PGR",
        "entity_type": "complaint",
        "entity_id": complaint_id,
        "event_type": event_type,
        "status": STATUS_MAP.get(event_type, "OPEN"),
        "actor_type": "CITIZEN" if event_type == "CaseSubmitted" else "EMPLOYEE",
        "actor_id": random.choice(ACTOR_IDS),
        "channel": random.choice(CHANNELS),
        "ward_id": random.choice(WARDS),
        "locality_id": random.choice(LOCALITIES),
        "attributes_json": {
            "complaint_type": random.choice(COMPLAINT_TYPES),
            "priority": priority,
            "sla_hours": SLA_HOURS_MAP[priority]
        },
        "raw_payload": None
    }
    
    return event


def main():
    """Produce events to RedPanda (Kafka-compatible)."""
    print(f"Connecting to RedPanda at {KAFKA_BOOTSTRAP_SERVERS}...")
    print(f"Topic: {KAFKA_TOPIC}")
    
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",  # Wait for all replicas
        retries=3
    )
    
    print("✅ Connected to RedPanda (Kafka-compatible)")
    print("\nProducing events (Ctrl+C to stop)...")
    
    try:
        count = 0
        while True:
            event = generate_event()
            
            future = producer.send(KAFKA_TOPIC, value=event)
            
            # Block until message is sent (or timeout)
            try:
                record_metadata = future.get(timeout=10)
                count += 1
                print(f"📨 [{count}] Published event: {event['entity_id']} - {event['event_type']} "
                      f"(partition={record_metadata.partition}, offset={record_metadata.offset})")
            except KafkaError as e:
                print(f"❌ Error sending message: {e}")
            
            # Rate limit: 1 event per second (adjust for testing)
            time.sleep(1)
    
    except KeyboardInterrupt:
        print(f"\n\nStopping producer... (sent {count} events)")
    except KafkaError as e:
        print(f"❌ Kafka error: {e}")
        sys.exit(1)
    finally:
        producer.flush()
        producer.close()
        print("✅ Producer closed")


if __name__ == "__main__":
    main()
