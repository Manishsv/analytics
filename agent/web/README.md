# MetricFlow NLQ Agent - Web Chat UI

A simple, modern web chat interface for interacting with the MetricFlow NLQ Agent API.

## Features

- 💬 Chat-like interface for natural language queries
- 📊 Displays query plans (metrics, dimensions, filters)
- 📈 Shows query results in formatted tables
- 🎨 Modern, responsive design
- ⚡ Real-time responses
- 📋 Example queries for quick testing

## Quick Start

### Option 1: Open Directly in Browser

1. Make sure the agent service is running:
   ```bash
   cd /Users/manishsv/Documents/Projects/analytics
   source .venv310/bin/activate
   uvicorn agent.app.main:app --reload --port 8000
   ```

2. Open `agent/web/index.html` in your browser:
   ```bash
   open agent/web/index.html
   # Or navigate to file:///Users/manishsv/Documents/Projects/analytics/agent/web/index.html
   ```

### Option 2: Serve with Python HTTP Server

```bash
cd agent/web
python3 -m http.server 8080
# Then open http://localhost:8080 in your browser
```

### Option 3: Serve with Node.js (if installed)

```bash
cd agent/web
npx http-server -p 8080
# Then open http://localhost:8080 in your browser
```

## Usage

1. **Type your question** in the input field at the bottom
2. **Press Enter** or click "Send" to submit
3. **View results** - The agent will show:
   - The query plan (metrics, dimensions, filters)
   - The execution results in a formatted table

## Example Queries

- "Sales value by geo and channel"
- "Average price per standard unit by channel"
- "Sales volume in standard units by geo"
- "Sales value for period 202412 by geo"

## Configuration

To change the API endpoint, edit the `API_BASE_URL` constant in `index.html`:

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

For production, you may want to:
- Use a relative URL if serving from the same domain
- Add CORS headers to the FastAPI service if serving from a different origin
- Add authentication/authorization

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console, add CORS middleware to the FastAPI service:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### API Not Found

- Ensure the agent service is running on `http://localhost:8000`
- Check the browser console for connection errors
- Verify the `API_BASE_URL` in `index.html` matches your service URL

## Next Steps

- Add query history/session management
- Add export functionality for results
- Add query syntax highlighting
- Add support for filtering by time ranges
- Add visualizations/charts for results
