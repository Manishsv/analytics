#!/usr/bin/env python3
"""
Batch insert PGR events from CSV into Bronze table via Trino.
Reads CSV and performs INSERT in batches.
"""
import csv
import sys
import time

csv_file = '/tmp/pgr_events_100k.csv'
batch_size = 1000

print(f"Reading {csv_file}...")

# Read all rows from CSV
rows = []
with open(csv_file, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Format values for SQL INSERT
        values = (
            f"DATE '{row['event_date']}'",
            f"TIMESTAMP '{row['event_time']}'",
            f"'{row['tenant_id']}'",
            f"'{row['service']}'",
            f"'{row['entity_type']}'",
            f"'{row['entity_id']}'",
            f"'{row['event_type']}'",
            f"'{row['status']}'",
            f"'{row['actor_type']}'",
            f"'{row['actor_id']}'" if row['actor_id'] else 'NULL',
            f"'{row['channel']}'",
            f"'{row['ward_id']}'",
            f"'{row['locality_id']}'",
            f"'{row['attributes_json'].replace(chr(39), chr(39)+chr(39))}'",  # Escape single quotes
            'NULL' if not row['raw_payload'] or row['raw_payload'].upper() == 'NULL' else f"'{row['raw_payload']}'"
        )
        rows.append(f"({', '.join(values)})")

print(f"Total rows: {len(rows)}")
print(f"Inserting in batches of {batch_size}...")

# Generate SQL batches
sql_file = '/tmp/batch_insert_pgr.sql'
with open(sql_file, 'w') as f:
    f.write("-- Batch insert PGR events\n")
    f.write("-- This will be executed via Trino\n\n")
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        insert_sql = f"INSERT INTO iceberg.bronze.service_events_raw VALUES\n"
        insert_sql += ",\n".join(batch) + ";\n\n"
        f.write(insert_sql)
        
        if (i + batch_size) % 10000 == 0:
            print(f"  Generated SQL for {i + batch_size}/{len(rows)} rows...")

print(f"✅ SQL file generated: {sql_file}")
print(f"   Batches: {(len(rows) + batch_size - 1) // batch_size}")
print(f"\nTo execute:")
print(f"  docker exec -i dap-trino trino --server http://trino:8080 < {sql_file}")
