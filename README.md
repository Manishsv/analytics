# Data Analytics Platform

A modern, open-source analytics stack built on MinIO (S3) + Iceberg (Nessie catalog) + Trino + dbt + MetricFlow + AI-powered natural language queries.

## ✨ Key Features

- **🏗️ Bronze/Silver/Gold Architecture**: Layered data lakehouse with Iceberg tables
- **🤖 AI-Powered NLQ**: Natural language queries with LLM planning and MetricFlow execution
- **📊 PGR Demo Mode**: Automated demo showcasing complaint analytics capabilities
- **🔍 Semantic Layer**: MetricFlow-powered metrics and dimensions abstraction
- **⚡ Real-time Queries**: Trino SQL engine with native S3 filesystem
- **📈 BI Integration**: Apache Superset for dashboards and visualizations

## 🚀 Quick Start (10 minutes)

### Prerequisites

- **Docker Desktop** (or Docker Engine) + Docker Compose v2
- **Python 3.10** with virtual environment support
- **Ollama** installed and running (for AI agent)

### Step 1: Start Infrastructure

```bash
# Clone the repository
git clone <repository-url>
cd analytics

# Start all services (MinIO, Nessie, Trino, Superset)
docker compose up -d

# Wait for services to be healthy (about 30 seconds)
docker compose ps
```

### Step 2: Setup Python Environment

```bash
# Create and activate Python 3.10 virtual environment
python3.10 -m venv .venv310
source .venv310/bin/activate  # On Windows: .venv310\Scripts\activate

# Install dependencies (dbt + MetricFlow)
pip install dbt-trino metricflow[trino]
```

### Step 3: Setup Ollama (for AI Agent)

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

# Note: You can try other models by setting OLLAMA_MODEL environment variable
# Example: export OLLAMA_MODEL=llama3.2  (ensure it's compatible)
```

### Step 4: Setup Sample PGR Data

```bash
# Ensure you're in the virtual environment
source .venv310/bin/activate

# Install additional dependencies if needed
pip install pandas  # Required for data generation scripts

# Create Bronze table if it doesn't exist (one-time setup)
docker exec -it dap-trino trino --server http://trino:8080 << 'EOF'
CREATE SCHEMA IF NOT EXISTS iceberg.bronze;

CREATE TABLE IF NOT EXISTS iceberg.bronze.service_events_raw (
    event_date DATE,
    event_time TIMESTAMP,
    tenant_id VARCHAR,
    service VARCHAR,
    entity_type VARCHAR,
    entity_id VARCHAR,
    event_type VARCHAR,
    status VARCHAR,
    actor_type VARCHAR,
    actor_id VARCHAR,
    channel VARCHAR,
    ward_id VARCHAR,
    locality_id VARCHAR,
    attributes_json VARCHAR,
    raw_payload VARCHAR
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['event_date', 'service']
);
EOF

# Generate historical PGR data (100,000+ records spanning 2 years)
cd scripts
python3 generate_pgr_historical.py

# This creates: /tmp/pgr_events_historical_2yr.csv
# Verify with: ls -lh /tmp/pgr_events_historical_2yr.csv

# Copy/rename file to match batch_insert_pgr.py expectation, or update script
# Option 1: Update batch_insert_pgr.py to use the correct filename
# Option 2: Copy the file:
cp /tmp/pgr_events_historical_2yr.csv /tmp/pgr_events_100k.csv

# Generate batch insert SQL from CSV (reads /tmp/pgr_events_100k.csv)
python3 batch_insert_pgr.py

# This creates: /tmp/batch_insert_pgr.sql
# Verify with: ls -lh /tmp/batch_insert_pgr.sql

# Execute batch inserts via Trino
docker exec -i dap-trino trino --server http://trino:8080 < /tmp/batch_insert_pgr.sql

# Verify data was loaded (should show ~100,000 rows)
docker exec -it dap-trino trino --server http://trino:8080 -e "SELECT COUNT(*) FROM iceberg.bronze.service_events_raw WHERE service = 'PGR';"
```

### Step 5: Run dbt Models

```bash
# Ensure you're in the virtual environment
source .venv310/bin/activate

# Run dbt models to create Silver and Gold layers from Bronze data
cd dbt
dbt run

# Build semantic models for MetricFlow
dbt parse
```

### Step 6: Start AI Agent Service

```bash
# Install FastAPI dependencies
pip install -r agent/requirements.txt

# Start the agent service
cd agent
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Loaded allowlist: X metrics, Y dimensions
```

### Step 7: Launch Web UI & Run PGR Demo

```bash
# Option 1: Open directly in browser
open agent/web/index.html  # macOS
# Or navigate to: file:///path/to/analytics/agent/web/index.html

# Option 2: Serve via HTTP server (recommended)
cd agent/web
python3 -m http.server 8080
# Navigate to: http://localhost:8080
```

**🎬 Try the PGR Demo:**
1. Click the **"🎬 Run PGR Demo"** button in the web UI header
2. Watch as 10 pre-configured PGR queries execute automatically
3. Explore complaint analytics capabilities including:
   - Total complaints and trends
   - Complaints by ward/channel
   - Top wards with open complaints
   - Resolution rates and SLA breaches
   - Average time to resolve

### Step 7: Access Services

- **Web UI**: http://localhost:8080 (after starting HTTP server)
- **Agent API**: http://localhost:8000
- **MinIO Console**: http://localhost:9001 (login with `.env` credentials)
- **Trino UI**: http://localhost:8090
- **Superset**: http://localhost:8088 (optional)

## Smoke Test

Connect to Trino and create a test table:

```bash
docker exec -it dap-trino trino
```

Then run:

```sql
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;

-- Creates schema with default warehouse location (s3://warehouse/)
CREATE SCHEMA IF NOT EXISTS iceberg.bronze;

CREATE TABLE iceberg.bronze.sample_sales (
  period_yyyymm varchar,
  pack_id varchar,
  geo_id varchar,
  channel_id varchar,
  units bigint,
  standard_units bigint,
  value_lc double
)
WITH (
  format = 'PARQUET',
  partitioning = ARRAY['period_yyyymm']
);

INSERT INTO iceberg.bronze.sample_sales VALUES
('202412', 'PCK_001', 'GEO_345', 'RET', 12450, 62250, 1845000.0);

SELECT * FROM iceberg.bronze.sample_sales;
```

**Note**: Bronze/Silver/Gold schemas are pre-created. All tables use Nessie catalog and MinIO (native S3) storage.

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture and design (v1.1)
- **[INGESTION.md](INGESTION.md)** - Data ingestion workflows and examples
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Roadmap and future enhancements
- **[dbt/models/pgr_README.md](dbt/models/pgr_README.md)** - PGR reference implementation guide
- **[agent/README.md](agent/README.md)** - AI Agent service documentation with Getting Started guide

## 🎯 Example Queries

Try these natural language queries in the web UI:

- **"total complaints by ward"** - Complaints grouped by ward
- **"which ward has the most complaints that are not closed"** - Top ward with open complaints
- **"total complaints by days"** - Daily complaint trends
- **"total complaints by month wise trend for last 2 years"** - Monthly trends over 2 years
- **"what is the resolution rate by ward"** - Resolution rate analysis
- **"SLA breach rate by ward for high priority complaints"** - SLA breach analysis

Or use the **🎬 Run PGR Demo** button to see all queries in action!

## 🏗️ Architecture

- **Nessie**: Git-like Iceberg catalog (replaces Hive Metastore)
- **MinIO**: S3-compatible object storage
- **Trino**: Distributed SQL query engine with native S3 filesystem
- **Iceberg**: Open table format with schema evolution and time travel
- **dbt**: Data transformations (Bronze → Silver → Gold)
- **MetricFlow**: Semantic layer for metrics and dimensions
- **AI Agent**: FastAPI + Ollama LLM for natural language queries
- **Superset**: BI dashboard tool (optional)

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Object Storage | MinIO | S3-compatible storage for Iceberg data |
| Table Format | Apache Iceberg | Open table format with schema evolution |
| Catalog | Project Nessie | Git-like catalog for Iceberg tables |
| Query Engine | Trino 455 | Distributed SQL query engine |
| Transformations | dbt Core 1.11.2 | Data build tool for transformations |
| Semantic Layer | MetricFlow 0.11.0 | Metrics and dimensions abstraction |
| AI Agent | FastAPI + Python 3.10 | NLQ planning and execution |
| LLM | Ollama (gpt-oss:120b-cloud) | Natural language understanding |
| BI Tool | Apache Superset | Dashboards and visualizations |

## 🔧 Configuration Files

- `.env` - Environment variables (MinIO credentials, etc.)
- `docker-compose.yml` - Service definitions (Nessie, MinIO, Trino, Superset)
- `trino/etc/catalog/iceberg.properties` - Trino Iceberg catalog (Nessie + native S3)
- `dbt/profiles.yml` - dbt connection to Trino
- `dbt/dbt_project.yml` - dbt project configuration
- `agent/requirements.txt` - Python dependencies for AI agent

## 📊 Data Schemas

- `iceberg.bronze` - Raw ingested tables (events, raw data)
- `iceberg.silver` - Conformed/typed tables (validated, normalized)
- `iceberg.gold` - Business marts (aggregated, certified)

## 🧪 Testing

### Run Comprehensive Test Suite

```bash
cd agent
source ../.venv310/bin/activate
pytest tests/test_ai_comprehensive.py -v
```

See [agent/tests/README.md](agent/tests/README.md) for detailed test documentation.

## 🐛 Troubleshooting

### Services won't start
```bash
# Check service status
docker compose ps

# View logs
docker compose logs trino
docker compose logs nessie
docker compose logs minio
```

### Agent service issues
- Ensure Ollama is running: `curl http://localhost:11434/api/tags`
- Verify dbt project path is correct
- Check Python environment has MetricFlow: `mf --version`

### Web UI can't connect
- Verify agent service is running: `curl http://localhost:8000/health`
- Check browser console for CORS errors
- Try hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

**Built with ❤️ using open-source technologies**