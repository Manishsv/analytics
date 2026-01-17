#!/usr/bin/env python3
"""Convert CSV to Parquet for Iceberg ingestion."""
import pandas as pd
import sys

csv_file = '/tmp/pgr_events_100k.csv'
parquet_file = '/tmp/pgr_events_100k.parquet'

print(f"Reading CSV: {csv_file}")
df = pd.read_csv(csv_file)

print(f"Converting to Parquet: {parquet_file}")
df.to_parquet(parquet_file, index=False, engine='pyarrow')

print(f"✅ Converted {len(df)} rows to Parquet")
print(f"   Parquet size: {pd.io.common.file_size(parquet_file) / 1024 / 1024:.2f} MB")
