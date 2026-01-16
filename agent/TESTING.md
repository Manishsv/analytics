# Agent Service Testing Guide

## Quick Start

1. **Start the service:**
   ```bash
   cd /Users/manishsv/Documents/Projects/analytics
   source .venv310/bin/activate
   export OLLAMA_BASE_URL="http://localhost:11434"
   export OLLAMA_MODEL="gpt-oss:120b-cloud"
   uvicorn agent.app.main:app --reload --port 8000
   ```

2. **In another terminal, run tests:**
   ```bash
   cd /Users/manishsv/Documents/Projects/analytics
   # Test commands below
   ```

## Test Endpoints

### 1. Health Check
```bash
curl http://localhost:8000/health
```
**Expected:** `{"status":"ok"}`

### 2. Catalog (List Metrics & Dimensions)
```bash
curl http://localhost:8000/catalog | python -m json.tool
```
**Expected:** JSON with `metrics_raw` and `dimensions_raw` fields showing available metrics and dimensions.

### 3. Structured Query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["sales_value_lc"],
    "dimensions": ["sales__geo_id", "sales__channel_id"],
    "limit": 50
  }' | python -m json.tool
```
**Expected:** Query results with `returncode: 0` and `stdout` containing data table.

### 4. Natural Language Query (NLQ)
```bash
# Simple query
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Sales value by geo and channel",
    "limit": 50
  }' | python -m json.tool
```

**Expected:** JSON with:
- `plan`: LLM-generated query plan
- `execution`: Query results

## Test Cases

### Test Case 1: Basic Sales Query
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Sales value by geo and channel",
    "limit": 50
  }' | python -m json.tool
```

**Expected Plan:**
- `metrics`: `["sales_value_lc"]`
- `dimensions`: `["sales__geo_id", "sales__channel_id"]`
- `returncode: 0` in execution

### Test Case 2: Average Price Query
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Average price per SU by channel",
    "limit": 50
  }' | python -m json.tool
```

**Expected Plan:**
- `metrics`: `["avg_price_lc_per_su"]`
- `dimensions`: `["sales__channel_id"]`

### Test Case 3: Volume Query
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Sales volume in SU by geo",
    "limit": 50
  }' | python -m json.tool
```

**Expected Plan:**
- `metrics`: `["sales_volume_su"]`
- `dimensions`: `["sales__geo_id"]`

### Test Case 4: With Period Filter
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Sales value by geo for period 202412",
    "limit": 50
  }' | python -m json.tool
```

**Expected Plan:**
- `metrics`: `["sales_value_lc"]`
- `dimensions`: `["sales__geo_id"]`
- `filters`: `[{"dimension": "sales__period_yyyymm", "op": "=", "value": "202412"}]`

## Verify Allowlist Loading

Check service logs at startup - should see allowlist loaded:
```bash
# Look for startup messages when service starts
# Should show metrics and dimensions parsed from catalog
```

## Troubleshooting

### Service won't start
- Check Python 3.10 venv is activated: `python --version`
- Check MetricFlow is installed: `mf --version`
- Check dbt project exists: `ls -la dbt/`

### NLQ returns errors
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Check model is available: `ollama list | grep gpt-oss`
- Check service logs for detailed error messages

### Query execution fails
- Verify Trino is running: `docker ps | grep trino`
- Check dbt connection: `cd dbt && source ../.venv310/bin/activate && dbt debug`
- Verify Gold tables exist: `docker exec dap-trino trino --server http://localhost:8080 --execute "SHOW TABLES FROM iceberg.gold;"`

### Allowlist is empty
- Check `/catalog` endpoint returns data
- Check service startup logs for parsing errors
- Verify `mf list metrics` works: `cd dbt && source ../.venv310/bin/activate && mf list metrics`
