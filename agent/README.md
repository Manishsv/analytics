# MetricFlow Agent Service

FastAPI service that wraps MetricFlow CLI for natural language to SQL queries via semantic layer.

## Features

- **Natural Language Queries**: Convert questions to SQL via LLM planning
- **Discoverability**: List available metrics and dimensions via `/catalog`
- **Query Execution**: Execute MetricFlow queries with guardrails via `/query`
- **PGR Demo Mode**: Automated demo that runs 10 PGR queries sequentially
- **Guardrails**: Timeouts, row limits, input validation, allowlist enforcement

---

## Getting Started

### Prerequisites

1. **Docker Compose stack running** (MinIO, Nessie, Trino):
   ```bash
   cd /path/to/analytics
   docker-compose up -d
   ```

2. **dbt project configured** with semantic models and metrics

3. **Ollama installed and running** with `gpt-oss:120b-cloud` model:
   ```bash
   # Install Ollama (if not already installed)
   # macOS: brew install ollama
   # Linux: curl -fsSL https://ollama.com/install.sh | sh
   
   # Start Ollama service (keep this running)
   ollama serve
   
   # In another terminal, pull the required model
   ollama pull gpt-oss:120b-cloud
   
   # Verify model is installed
   ollama list
   # You should see: gpt-oss:120b-cloud
   
   # Note: You can use other models by setting OLLAMA_MODEL environment variable
   # Example: export OLLAMA_MODEL=llama3.2
   ```

4. **Python 3.10** with MetricFlow installed (see Setup section below)

### Quick Start (5 minutes)

1. **Activate Python environment**:
   ```bash
   cd /path/to/analytics
   source .venv310/bin/activate
   ```

2. **Install FastAPI dependencies**:
   ```bash
   pip install -r agent/requirements.txt
   ```

3. **Start the agent service**:
   ```bash
   cd agent
   uvicorn app.main:app --reload --port 8000
   ```
   
   You should see:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000
   INFO:     Loaded allowlist: X metrics, Y dimensions
   ```

4. **Open the web UI**:
   - Open `agent/web/index.html` in your browser
   - Or serve it via a simple HTTP server:
     ```bash
     cd agent/web
     python3 -m http.server 8080
     ```
   - Navigate to `http://localhost:8080`

5. **Run the PGR Demo**:
   - Click the **"🎬 Run PGR Demo"** button in the web UI header
   - Watch as 10 PGR queries execute automatically:
     - Total complaints
     - Complaints by ward
     - Complaints for specific ward
     - Top ward with open complaints
     - Daily/monthly trends
     - Resolution rates
     - SLA breach analysis
     - And more!

### Verify Installation

1. **Health check**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok"}
   ```

2. **Catalog check**:
   ```bash
   curl http://localhost:8000/catalog | python -m json.tool
   # Should return metrics and dimensions
   ```

3. **Test NLQ query**:
   ```bash
   curl -X POST http://localhost:8000/nlq \
     -H "Content-Type: application/json" \
     -d '{"question":"total complaints","limit":10}'
   ```

---

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

## Web UI

The web UI provides a chat-like interface for natural language queries with:
- **PGR Demo Mode**: One-click automated demo
- **Persistent Catalog Sidebar**: Always-accessible metrics and dimensions
- **Smart Formatting**: Automatic number and date formatting
- **Top N Query Support**: Automatic aggregation for "which X has the most Y" queries

### Running the Web UI

**Option 1: Direct file open** (simplest):
```bash
# Open in browser
open agent/web/index.html  # macOS
xdg-open agent/web/index.html  # Linux
```

**Option 2: HTTP server** (recommended for CORS):
```bash
cd agent/web
python3 -m http.server 8080
# Navigate to http://localhost:8080
```

**Option 3: Serve from agent directory**:
```bash
cd agent
python3 -m http.server 8080
# Navigate to http://localhost:8080/web/index.html
```

The web UI connects to the agent service at `http://localhost:8000` by default.

## Environment Variables

- `DBT_PROJECT_DIR`: Path to dbt project (default: `../dbt`)
- `DBT_PROFILES_DIR`: Path to dbt profiles (default: `../dbt`)
- `OLLAMA_BASE_URL`: Ollama API base URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Ollama model name (default: `gpt-oss:120b-cloud`)
- `API_KEY`: API key for Bearer token authentication (optional, disables auth if not set)
  
  **Important**: The default model `gpt-oss:120b-cloud` is **required** for the PGR demo and tested workflows. You can try other models, but ensure they support JSON mode and structured output:
  
  ```bash
  # Pull another model (optional, not required for PGR demo)
  ollama pull llama3.2
  ollama pull mistral
  
  # Set environment variable before starting agent
  export OLLAMA_MODEL=llama3.2
  uvicorn app.main:app --reload --port 8000
  ```
  
  **Note**: Different models may produce different query plans. For production use, test thoroughly with your chosen model.

## Advanced Features

- **Natural Language Queries**: `/nlq` endpoint uses LLM to plan queries from natural language
- **Allowlist Enforcement**: Metrics and dimensions validated against catalog at startup
- **Safe Filter Compilation**: Structured filters compiled to safe WHERE clauses (no SQL injection)
- **Time Granularity Support**: Automatic detection and aggregation for day/week/month/year
- **Top N Query Handling**: Client-side aggregation for "which X has the most Y" queries
- **Case Sensitivity**: Automatic normalization for status filters (e.g., "Closed" → "CLOSED")
- **Query Explanation**: Returns metric definitions, dimensions, and filters for audit
- **Query Caching**: LRU cache with TTL (5 minutes) for `/nlq` and `/query` endpoints
- **API Key Authentication**: Bearer token authentication for API endpoints (optional)

## Guardrails

- Query timeout: 60 seconds (configurable)
- Row limit: 1-1000 (default: 200)
- Input validation via Pydantic schemas
- MetricFlow CLI execution isolation
- Allowlist enforcement for metrics and dimensions
- Safe filter compilation (no SQL injection)

## Testing

### Agent Service Tests

See [tests/README.md](tests/README.md) for comprehensive test suite documentation.

### Platform Testing

For testing other platform components, see:
- **[TESTING_REALTIME.md](../TESTING_REALTIME.md)** - Real-time ingestion pipeline testing (Kafka/RedPanda consumer)
- **[TESTING_MULTITENANCY.md](../TESTING_MULTITENANCY.md)** - Multi-tenant data isolation testing
- **[SUPERSET_SETUP.md](../SUPERSET_SETUP.md)** - Apache Superset configuration and dashboard setup

### Quick Test Commands

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Catalog
curl http://localhost:8000/catalog | python -m json.tool

# 3. Structured query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"metrics":["pgr_complaints"],"dimensions":["complaint__ward_id"],"limit":50}'

# 4. Natural language query (PGR)
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{"question":"total complaints by ward","limit":50}'

# 5. Top N query
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{"question":"which ward has the most complaints that are not closed","limit":1}'
```

### Running the Test Suite

```bash
# Run comprehensive test suite (34+ test cases)
cd agent
pytest tests/test_ai_comprehensive.py -v

# Run specific test category
pytest tests/test_ai_comprehensive.py::test_basic_queries -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Troubleshooting

### Service won't start
- Check that Ollama is running: `curl http://localhost:11434/api/tags`
- Verify dbt project path is correct
- Check Python environment has MetricFlow installed: `mf --version`

### Web UI can't connect
- Verify agent service is running on port 8000
- Check browser console for CORS errors
- Try hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

### Queries failing
- Check MetricFlow config: `mf validate-configs`
- Verify semantic models are defined in dbt
- Check Trino connection: `docker-compose ps trino`
- Review agent logs for detailed error messages

## Related Documentation

- **[README.md](../README.md)** - Platform overview and quick start guide
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - Detailed architecture documentation
- **[SUPERSET_SETUP.md](../SUPERSET_SETUP.md)** - Apache Superset configuration guide
- **[TESTING_REALTIME.md](../TESTING_REALTIME.md)** - Real-time ingestion testing guide
- **[TESTING_MULTITENANCY.md](../TESTING_MULTITENANCY.md)** - Multi-tenant testing guide
- **[ENHANCEMENTS_V1.2.md](../ENHANCEMENTS_V1.2.md)** - Short-term enhancements (PostgreSQL, caching, auth)
- **[ENHANCEMENTS_V1.3.md](../ENHANCEMENTS_V1.3.md)** - Medium-term enhancements (dbt tests, materialized views, multi-tenancy)