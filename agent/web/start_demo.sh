#!/bin/bash
# Quick script to start the demo UI

echo "🚀 Starting MetricFlow NLQ Agent Demo..."
echo ""
echo "Step 1: Ensure the agent service is running:"
echo "  cd $(dirname $(dirname $(pwd)))"
echo "  source .venv310/bin/activate"
echo "  uvicorn agent.app.main:app --reload --port 8000"
echo ""
echo "Step 2: Opening the web UI..."
echo ""

# Try to open in default browser
if command -v open &> /dev/null; then
    # macOS
    open agent/web/index.html
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open agent/web/index.html
elif command -v start &> /dev/null; then
    # Windows
    start agent/web/index.html
else
    echo "Please open agent/web/index.html in your browser"
fi

echo ""
echo "Or serve with: python3 -m http.server 8080 (then open http://localhost:8080)"
