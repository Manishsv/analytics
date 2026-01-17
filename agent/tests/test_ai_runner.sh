#!/bin/bash
# Comprehensive test runner for AI NLQ agent

echo "🧪 AI NLQ Agent Comprehensive Test Suite"
echo "========================================"
echo ""

# Check if service is running
echo "📡 Checking if agent service is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Service is running"
else
    echo "❌ Service is not running!"
    echo ""
    echo "Please start the service first:"
    echo "  cd /Users/manishsv/Documents/Projects/analytics"
    echo "  source .venv310/bin/activate"
    echo "  uvicorn agent.app.main:app --reload --port 8000"
    exit 1
fi

echo ""
echo "🧪 Running comprehensive tests..."
echo ""

# Run tests with coverage
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate

pytest agent/tests/test_ai_comprehensive.py -v --tb=short -x

echo ""
echo "✅ Tests completed!"
