# Quick Start - Testing the Agent Service

## Step 1: Ensure Services are Running

```bash
# Check Trino is running
docker ps | grep trino

# Check Ollama is running
curl http://localhost:11434/api/tags
```

## Step 2: Start the Agent Service

```bash
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="gpt-oss:120b-cloud"
uvicorn agent.app.main:app --reload --port 8000
```

**Keep this terminal open** - the service needs to stay running.

## Step 3: Test in Another Terminal

Open a new terminal and run:

```bash
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate

# Test 1: Health check
curl http://localhost:8000/health

# Test 2: Catalog
curl http://localhost:8000/catalog | python -m json.tool

# Test 3: Structured query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"metrics":["sales_value_lc"],"dimensions":["sales__geo_id","sales__channel_id"],"limit":50}' | python -m json.tool

# Test 4: Natural language query
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{"question":"Sales value by geo and channel","limit":50}' | python -m json.tool
```

## Expected Results

- **Health**: `{"status":"ok"}`
- **Catalog**: Shows 4 metrics and dimensions
- **Structured Query**: Returns query results with `returncode: 0`
- **NLQ**: Returns plan + execution results

## Troubleshooting

If you see `[Errno 2] No such file or directory: 'mf'`:
- Make sure you activated `.venv310` (not `.venv`)
- Verify: `which mf` shows `/Users/manishsv/Documents/Projects/analytics/.venv/bin/mf`
- Restart the service after activating the correct venv
