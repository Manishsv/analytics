# Agent Service Tests

## Test Structure

- `test_nlq_planning.py` - Unit tests for NLQ planning logic (golden prompts, validation, filter compilation)
- `test_integration.py` - Integration tests that make HTTP requests to the running service

## Running Tests

### Unit Tests (No service required)
```bash
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
pytest agent/tests/test_nlq_planning.py -v
```

### Integration Tests (Service must be running)
```bash
# Terminal 1: Start the service
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
uvicorn agent.app.main:app --reload --port 8000

# Terminal 2: Run integration tests
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
pytest agent/tests/test_integration.py -v
```

### Run All Tests
```bash
pytest agent/tests/ -v
```

## Golden Test Cases

The `test_nlq_planning.py` file contains golden test cases that validate expected query plans for common prompts:

- "Sales value by geo and channel" → `sales_value_lc` with `sales__geo_id`, `sales__channel_id`
- "Average price per standard unit by channel" → `avg_price_lc_per_su` with `sales__channel_id`
- "Sales for GEO_345" → `sales_value_lc` with filter on `sales__geo_id = 'GEO_345'`
- "Sales value for period 202412 by geo" → `sales_value_lc` with period filter

These tests ensure the planner generates consistent, correct plans for common queries.

## Adding New Test Cases

To add a new golden test case, add an entry to `GOLDEN_TEST_CASES` in `test_nlq_planning.py`:

```python
{
    "question": "Your test question",
    "expected": {
        "metrics": ["metric_name"],
        "dimensions": ["dimension_name"],
        "filters": [...],
        "start_time": None,
        "end_time": None,
    }
}
```
