#!/usr/bin/env python3
"""
Generate historical PGR data for 2-year trend analysis.
Extends data back to 2023-01-01 for comprehensive trend queries.
"""
import csv
import random
from datetime import datetime, timedelta
import json

# Configuration - generate data for last 2 years
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)
NUM_CASES_PER_MONTH = 500  # Cases per month for trend analysis

# Sample data pools (same as generate_pgr_data.py)
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
ACTOR_IDS = [f'CIT_{i:05d}' for i in range(1, 1001)] + [f'EMP_{i:05d}' for i in range(1, 501)]

SLA_HOURS_MAP = {
    'CRITICAL': 4,
    'HIGH': 24,
    'MEDIUM': 72,
    'LOW': 168
}

def generate_case_events_for_month(complaint_id_prefix, tenant_id, base_month_date):
    """Generate cases for a specific month."""
    events = []
    days_in_month = (base_month_date.replace(month=base_month_date.month % 12 + 1, day=1) - timedelta(days=1)).day
    
    for day in range(1, days_in_month + 1, max(1, days_in_month // NUM_CASES_PER_MONTH)):
        complaint_id = f'{complaint_id_prefix}_{day:03d}'
        
        # Random case attributes
        ward_id = random.choice(WARDS)
        locality_id = random.choice(LOCALITIES)
        channel = random.choice(CHANNELS)
        complaint_type = random.choice(COMPLAINT_TYPES)
        priority = random.choice(PRIORITIES)
        sla_hours = SLA_HOURS_MAP[priority]
        
        # Event timestamps within the month
        event_time = base_month_date.replace(day=min(day, days_in_month)) + timedelta(
            hours=random.randint(8, 20),
            minutes=random.randint(0, 59)
        )
        
        # CaseSubmitted
        submitted_time = event_time
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
        
        # CaseAssigned
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
        
        # Resolve? (80% resolution rate)
        if random.random() < 0.8:
            resolve_hours = sla_hours + random.randint(-sla_hours // 4, sla_hours // 2)
            resolve_hours = max(1, resolve_hours)
            resolved_time = submitted_time + timedelta(hours=resolve_hours)
            
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
            
            # CaseClosed
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
    
    return events

def main():
    output_file = '/tmp/pgr_events_historical_2yr.csv'
    print(f"Generating historical PGR events from {START_DATE.date()} to {END_DATE.date()}...")
    
    all_events = []
    current_date = START_DATE
    complaint_counter = 1
    
    while current_date <= END_DATE:
        # Generate cases for this month
        month_prefix = f'CMP_{complaint_counter:06d}'
        tenant_id = random.choice(TENANTS)
        month_events = generate_case_events_for_month(month_prefix, tenant_id, current_date)
        all_events.extend(month_events)
        complaint_counter += NUM_CASES_PER_MONTH
        
        if current_date.month % 3 == 0:  # Print every quarter
            print(f"  Generated data through {current_date.strftime('%Y-%m')} ({len(all_events)} events so far)...")
        
        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1, day=1)
    
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
    
    return output_file

if __name__ == '__main__':
    output_file = main()
    print(f"\nNext step: Ingest using batch_insert_pgr.py or Method 2 from INGESTION.md")
