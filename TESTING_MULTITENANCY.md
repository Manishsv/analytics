# Testing Multi-Tenancy

This guide explains how to test multi-tenant data isolation in the analytics platform.

## Architecture

Multi-tenancy is implemented using dbt's `var()` function and the `tenant_filter()` macro:

- **Tenant Filter Macro**: `dbt/macros/tenant_filter.sql` - Filters data by `tenant_id`
- **Tenant Variable**: Passed via `--vars '{"tenant_id": "TENANT_001"}'` to dbt commands
- **Example Model**: `mv_pgr_ward_summary_tenant` - Materialized view with tenant isolation

## Quick Test

### Step 1: Check Available Tenants

```bash
# List all tenants and their event counts
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT DISTINCT tenant_id, COUNT(*) as event_count FROM iceberg.bronze.service_events_raw GROUP BY tenant_id ORDER BY tenant_id;"
```

### Step 2: Test Tenant Isolation in dbt Models

```bash
cd dbt

# Build tenant-specific materialized view for TENANT_001
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --profiles-dir .

# Query the tenant-isolated view (should only show TENANT_001 data)
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as ward_count, SUM(total_complaints) as total FROM iceberg.gold.mv_pgr_ward_summary_tenant GROUP BY tenant_id;"
```

### Step 3: Compare Results Across Tenants

```bash
# Build for TENANT_002
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_002"}' \
  --profiles-dir .

# Build for TENANT_003
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_003"}' \
  --profiles-dir .

# Compare totals
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as wards, SUM(total_complaints) as complaints FROM iceberg.gold.mv_pgr_ward_summary_tenant GROUP BY tenant_id ORDER BY tenant_id;"
```

### Step 4: Verify Isolation

```bash
# IMPORTANT: Check tenant isolation IMMEDIATELY after building with a specific tenant
# The table gets rebuilt each time, so previous builds may have left data from other tenants

# First, rebuild with TENANT_001 filter
cd dbt
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --profiles-dir .

# Now verify ONLY TENANT_001 data exists
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT DISTINCT tenant_id FROM iceberg.gold.mv_pgr_ward_summary_tenant;"
# Should show only TENANT_001

# Verify total rows match TENANT_001's data
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as wards FROM iceberg.gold.mv_pgr_ward_summary_tenant GROUP BY tenant_id;"
# Should show only TENANT_001 with ~50 wards

# Compare: Query without filter should show same count as with tenant filter
# (This verifies the filter worked during build)
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT COUNT(*) FROM iceberg.gold.gold_pgr_case_lifecycle WHERE tenant_id = 'TENANT_001' AND ward_id IS NOT NULL;"
# This count should be approximately equal to the sum of total_complaints in mv_pgr_ward_summary_tenant
```

## Detailed Testing Steps

### Test 1: Base Data Check

```bash
# Check total events per tenant in Bronze
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as events FROM iceberg.bronze.service_events_raw GROUP BY tenant_id ORDER BY tenant_id;"

# Check total events per tenant in Gold (no filter)
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as cases FROM iceberg.gold.pgr.gold_pgr_case_lifecycle GROUP BY tenant_id ORDER BY tenant_id;"
```

### Test 2: Tenant-Isolated Materialized View

```bash
cd dbt

# Build view with TENANT_001 filter
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --profiles-dir .

# Query the view - should only contain TENANT_001 data
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT DISTINCT tenant_id FROM iceberg.gold.mv_pgr_ward_summary_tenant;"
# Should show only TENANT_001

# Count records per tenant (should only be TENANT_001)
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as wards FROM iceberg.gold.mv_pgr_ward_summary_tenant GROUP BY tenant_id;"
```

### Test 3: Verify Tenant Filter Macro Logic

The `tenant_filter()` macro:
- Returns `tenant_id = 'TENANT_001'` when `--vars '{"tenant_id": "TENANT_001"}'` is set
- Returns `true` (no filter) when `tenant_id` variable is not set

```bash
# Build WITHOUT tenant filter (should include all tenants)
dbt run --select mv_pgr_ward_summary_tenant --profiles-dir .

# Verify all tenants are present
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT DISTINCT tenant_id FROM iceberg.gold.mv_pgr_ward_summary_tenant ORDER BY tenant_id;"
# Should show all tenants: TENANT_001, TENANT_002, TENANT_003

# Build WITH tenant filter (should only include TENANT_001)
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --profiles-dir .

# Verify only TENANT_001 is present
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT DISTINCT tenant_id FROM iceberg.gold.mv_pgr_ward_summary_tenant ORDER BY tenant_id;"
# Should show only TENANT_001
```

### Test 4: Query-Level Testing

You can also test tenant filtering in direct SQL queries:

```bash
# Query Gold table with tenant filter (application-level)
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as cases FROM iceberg.gold.pgr.gold_pgr_case_lifecycle WHERE tenant_id = 'TENANT_001' GROUP BY tenant_id;"

# Compare with other tenants
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT tenant_id, COUNT(*) as cases FROM iceberg.gold.pgr.gold_pgr_case_lifecycle WHERE tenant_id = 'TENANT_002' GROUP BY tenant_id;"
```

## Production Considerations

### Current Implementation (Application-Level Filtering)

- **How it works**: dbt `var()` + `tenant_filter()` macro
- **Scope**: Model-level (materialized views)
- **Enforcement**: Application must pass `tenant_id` variable
- **Limitation**: No database-level enforcement

### Production Recommendations

1. **Session Variables**: Set `tenant_id` per user session in Trino
2. **View per Tenant**: Create tenant-specific views (e.g., `gold.mv_pgr_ward_summary_TENANT_001`)
3. **Row-Level Security**: For PostgreSQL-backed systems, use native RLS
4. **API Layer**: Enforce tenant context in application API before querying

### Example: Tenant-Specific View Pattern

```sql
-- Create tenant-specific view (could be automated)
CREATE VIEW iceberg.gold.mv_pgr_ward_summary_TENANT_001 AS
SELECT *
FROM iceberg.gold.mv_pgr_ward_summary_tenant
WHERE tenant_id = 'TENANT_001';
```

## Troubleshooting

### Issue: All Tenants Visible When Filter Should Be Applied

**Check**: Verify the dbt variable is being passed correctly
```bash
# Debug: Check compiled SQL
dbt compile --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --profiles-dir .

# Check target/compiled/... for the generated SQL
cat target/compiled/dap/models/gold/mv_pgr_ward_summary_tenant.sql | grep -i tenant
```

### Issue: No Data in Tenant-Isolated View

**Check**: Verify tenant has data in source tables
```bash
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT COUNT(*) FROM iceberg.bronze.service_events_raw WHERE tenant_id = 'TENANT_001';"
```

### Issue: Materialized View Not Refreshing

**Solution**: Rebuild the materialized view
```bash
dbt run --select mv_pgr_ward_summary_tenant \
  --vars '{"tenant_id": "TENANT_001"}' \
  --full-refresh \
  --profiles-dir .
```

## Summary

**Multi-tenancy testing checklist:**

1. ✅ Verify tenants exist in Bronze table
2. ✅ Build tenant-isolated model with `--vars '{"tenant_id": "TENANT_XXX"}'`
3. ✅ Query tenant-isolated view and verify only that tenant's data appears
4. ✅ Compare results across multiple tenants
5. ✅ Test without filter (should show all tenants)

**Key commands:**

```bash
# Build with tenant filter
dbt run --select mv_pgr_ward_summary_tenant --vars '{"tenant_id": "TENANT_001"}' --profiles-dir .

# Query tenant data
docker exec dap-trino trino --server http://trino:8080 \
  --execute "SELECT * FROM iceberg.gold.mv_pgr_ward_summary_tenant WHERE tenant_id = 'TENANT_001' LIMIT 10;"
```
