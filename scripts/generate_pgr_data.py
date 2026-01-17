#!/usr/bin/env python3
"""
Generate sample PGR event data for ingestion.
Creates CSV file with 100,000 PGR events across multiple cases.
"""
import csv
import random
from datetime import datetime, timedelta
from uuid import uuid4
import json

# Configuration
NUM_CASES = 20000  # Number of unique complaints
EVENTS_PER_CASE = 5  # Average events per case (submitted, assigned, resolved, closed, etc.)
TOTAL_EVENTS = NUM_CASES * EVENTS_PER_CASE

# Sample data pools
TENANTS = ['TENANT_001', 'TENANT_002', 'TENANT_003']
WARDS = [f'WARD_{i:03d}' for i in range(1, 51)]  # 50 wards
LOCALITIES = [f'LOC_{i:03d}' for i in range(1, 201)]  # 200 localities
CHANNELS = ['WEB', 'MOBILE', 'CSC', 'COUNTER', 'API']
COMPLAINT_TYPES = [
    'Water Supply', 'Road Repair', 'Garbage Collection', 'Electricity',
    'Sewage', 'Street Lighting', 'Drainage', 'Park Maintenance',
    'Building Permission', 'Property Tax'
]
PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
ACTOR_IDS = [f'CIT_{i:05d}' for i in range(1, 1001)] + [f'EMP_{i:05d}' for i in range(1, 501)]

# SLA hours by priority
SLA_HOURS_MAP = {
    'CRITICAL': 4,
    'HIGH': 24,
    'MEDIUM': 72,
    'LOW': 168  # 7 days
}

def generate_case_events(complaint_id, tenant_id, start_date):
    """Generate all events for a single complaint case."""
    events = []
    
    # Random case attributes
    ward_id = random.choice(WARDS)
    locality_id = random.choice(LOCALITIES)
    channel = random.choice(CHANNELS)
    complaint_type = random.choice(COMPLAINT_TYPES)
    priority = random.choice(PRIORITIES)
    sla_hours = SLA_HOURS_MAP[priority]
    
    # Event timestamps - spread over a realistic timeline
    base_time = start_date + timedelta(
        days=random.randint(0, 60),  # Cases submitted over 60 days
        hours=random.randint(8, 20),  # Business hours
        minutes=random.randint(0, 59)
    )
    
    # CaseSubmitted
    submitted_time = base_time
    events.append({
        'event_date': submitted_time.date(),
        'event_time': submitted_time,
        'tenant_id': tenant_id,
        'service': 'PGR',
        'entity_type': 'complaint',
        'entity_id': complaint_id,
        'event_type': 'CaseSubmitted',
        'status': 'OPEN',
        'actor_type': 'CITIZEN',
        'actor_id': random.choice(ACTOR_IDS),
        'channel': channel,
        'ward_id': ward_id,
        'locality_id': locality_id,
        'attributes_json': json.dumps({
            'complaint_type': complaint_type,
            'priority': priority,
            'sla_hours': sla_hours
        }),
        'raw_payload': None
    })
    
    # CaseAssigned (within 1 hour of submission)
    assigned_time = submitted_time + timedelta(minutes=random.randint(5, 60))
    events.append({
        'event_date': assigned_time.date(),
        'event_time': assigned_time,
        'tenant_id': tenant_id,
        'service': 'PGR',
        'entity_type': 'complaint',
        'entity_id': complaint_id,
        'event_type': 'CaseAssigned',
        'status': 'ASSIGNED',
        'actor_type': 'SYSTEM',
        'actor_id': None,
        'channel': channel,
        'ward_id': ward_id,
        'locality_id': locality_id,
        'attributes_json': json.dumps({
            'from_status': 'OPEN',
            'to_status': 'ASSIGNED'
        }),
        'raw_payload': None
    })
    
    # Determine if case will be resolved (80% resolution rate)
    will_resolve = random.random() < 0.8
    
    if will_resolve:
        # Calculate resolution time (may breach SLA)
        # 20% breach rate
        if random.random() < 0.2:
            # Breach: resolve after SLA + some extra time
            resolve_hours = sla_hours + random.randint(1, sla_hours // 2)
        else:
            # On time: resolve within SLA
            resolve_hours = random.randint(1, sla_hours)
        
        resolved_time = submitted_time + timedelta(hours=resolve_hours)
        
        # CaseResolved
        events.append({
            'event_date': resolved_time.date(),
            'event_time': resolved_time,
            'tenant_id': tenant_id,
            'service': 'PGR',
            'entity_type': 'complaint',
            'entity_id': complaint_id,
            'event_type': 'CaseResolved',
            'status': 'RESOLVED',
            'actor_type': 'EMPLOYEE',
            'actor_id': random.choice([a for a in ACTOR_IDS if 'EMP' in a]),
            'channel': channel,
            'ward_id': ward_id,
            'locality_id': locality_id,
            'attributes_json': json.dumps({
                'from_status': 'ASSIGNED',
                'to_status': 'RESOLVED'
            }),
            'raw_payload': None
        })
        
        # CaseClosed (within 1 day of resolution)
        closed_time = resolved_time + timedelta(hours=random.randint(1, 24))
        events.append({
            'event_date': closed_time.date(),
            'event_time': closed_time,
            'tenant_id': tenant_id,
            'service': 'PGR',
            'entity_type': 'complaint',
            'entity_id': complaint_id,
            'event_type': 'CaseClosed',
            'status': 'CLOSED',
            'actor_type': 'EMPLOYEE',
            'actor_id': random.choice([a for a in ACTOR_IDS if 'EMP' in a]),
            'channel': channel,
            'ward_id': ward_id,
            'locality_id': locality_id,
            'attributes_json': json.dumps({
                'from_status': 'RESOLVED',
                'to_status': 'CLOSED'
            }),
            'raw_payload': None
        })
    else:
        # Case remains open (no resolved/closed events)
        pass
    
    return events

def main():
    output_file = '/tmp/pgr_events_100k.csv'
    print(f"Generating {TOTAL_EVENTS} PGR events for {NUM_CASES} cases...")
    
    all_events = []
    base_date = datetime(2024, 10, 1)  # Start date
    
    for i in range(NUM_CASES):
        complaint_id = f'CMP_{i+1:06d}'
        tenant_id = random.choice(TENANTS)
        case_events = generate_case_events(complaint_id, tenant_id, base_date)
        all_events.extend(case_events)
        
        if (i + 1) % 1000 == 0:
            print(f"  Generated {i+1}/{NUM_CASES} cases ({len(all_events)} events so far)...")
    
    print(f"Total events generated: {len(all_events)}")
    print(f"Writing to {output_file}...")
    
    # Write to CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'event_date', 'event_time', 'tenant_id', 'service', 'entity_type', 'entity_id',
            'event_type', 'status', 'actor_type', 'actor_id', 'channel', 'ward_id',
            'locality_id', 'attributes_json', 'raw_payload'
        ])
        
        # Data rows
        for event in all_events:
            writer.writerow([
                event['event_date'],
                event['event_time'].strftime('%Y-%m-%d %H:%M:%S'),
                event['tenant_id'],
                event['service'],
                event['entity_type'],
                event['entity_id'],
                event['event_type'],
                event['status'],
                event['actor_type'],
                event['actor_id'],
                event['channel'],
                event['ward_id'],
                event['locality_id'],
                event['attributes_json'],
                event['raw_payload']
            ])
    
    print(f"✅ File generated: {output_file}")
    print(f"   Records: {len(all_events)}")
    print(f"   File size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    
    return output_file

if __name__ == '__main__':
    import os
    output_file = main()
    print(f"\nNext steps:")
    print(f"1. Upload to MinIO: docker exec dap-minio mc cp {output_file} local/warehouse/staging/")
    print(f"2. Insert via Trino (see INGESTION.md)")
