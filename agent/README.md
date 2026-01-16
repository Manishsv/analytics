# MetricFlow Agent Service

FastAPI service that wraps MetricFlow CLI for natural language to SQL queries via semantic layer.

## Features

- **Discoverability**: List available metrics and dimensions via `/catalog`
- **Query Execution**: Execute MetricFlow queries with guardrails via `/query`
- **Guardrails**: Timeouts, row limits, input validation

## Setup

### Local Development (Recommended)

1. **Activate Python 3.10 environment** (with MetricFlow installed):
   ```bash
   source ../.venv310/bin/activate
   ```

2. **Install FastAPI dependencies**:
   ```bash
   pip install -r agent/requirements.txt
   ```

3. **Run the service**:
   ```bash
   uvicorn agent.app.main:app --reload --port 8000
   ```

### Docker (Self-contained)

Build and run:
```bash
docker build -t metricflow-agent .
docker run -p 8000:8000 metricflow-agent
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Catalog (List Metrics & Dimensions)
```bash
curl http://localhost:8000/catalog
```

### Query (Structured)
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["sales_value_lc"],
    "dimensions": ["sales__geo_id", "sales__channel_id"],
    "limit": 50
  }'
```

### Natural Language Query (NLQ)
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Sales value by geo and channel",
    "limit": 50
  }'
```

Returns both the LLM-generated plan and execution results.

## Environment Variables

- `DBT_PROJECT_DIR`: Path to dbt project (default: `../dbt`)
- `DBT_PROFILES_DIR`: Path to dbt profiles (default: `../dbt`)
- `OLLAMA_BASE_URL`: Ollama API base URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Ollama model name (default: `gpt-oss:120b-cloud`)

## Features

- **Natural Language Queries**: `/nlq` endpoint uses LLM to plan queries from natural language
- **Allowlist Enforcement**: Metrics and dimensions validated against catalog at startup
- **Safe Filter Compilation**: Structured filters compiled to safe WHERE clauses (no SQL injection)
- **Guardrails**: Timeouts, row limits, input validation

## Guardrails

- Query timeout: 60 seconds (configurable)
- Row limit: 1-1000 (default: 200)
- Input validation via Pydantic schemas
- MetricFlow CLI execution isolation
- Allowlist enforcement for metrics and dimensions
- Safe filter compilation (no SQL injection)

## Testing

See [TESTING.md](TESTING.md) for detailed test cases and troubleshooting.

### Quick Test Commands

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Catalog
curl http://localhost:8000/catalog | python -m json.tool

# 3. Structured query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"metrics":["sales_value_lc"],"dimensions":["sales__geo_id","sales__channel_id"],"limit":50}'

# 4. Natural language query
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{"question":"Sales value by geo and channel","limit":50}'
```