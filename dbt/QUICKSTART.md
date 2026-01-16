# dbt Quick Start Guide

## Prerequisites

Install dbt-trino:

```bash
pip install dbt-trino
```

Or with virtual environment (recommended):

```bash
cd dbt
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install dbt-trino
```

## First Run

1. **Verify connection**:
   ```bash
   cd dbt
   dbt debug
   ```
   
   Should show:
   - Connection test: OK
   - Catalog: iceberg
   - Schemas: bronze, silver, gold

2. **Install packages** (optional):
   ```bash
   dbt deps
   ```

3. **Build Silver layer**:
   ```bash
   dbt run --select silver
   ```

4. **Build Gold layer**:
   ```bash
   dbt run --select gold
   ```

5. **Run all transformations**:
   ```bash
   dbt run
   ```

6. **Run tests**:
   ```bash
   dbt test
   ```

## Verify in Trino

```sql
-- Check Silver
SELECT COUNT(*) FROM iceberg.silver.silver_sales;

-- Check Gold
SELECT * FROM iceberg.gold.gold_sales_monthly;

-- Check certified view
SELECT * FROM iceberg.gold.v_sales_monthly;
```

## Troubleshooting

If `dbt debug` fails:
- Verify Trino is running: `curl http://localhost:8090/v1/info`
- Check `profiles.yml` port matches Trino (8090)
- Ensure `.env` credentials are correct

If models fail:
- Check Trino logs: `docker logs dap-trino --tail 50`
- Verify Bronze table exists: `SELECT * FROM iceberg.bronze.sample_sales LIMIT 1;`
