# Agent Service Tests

## Test Structure

- `test_nlq_planning.py` - Unit tests for NLQ planning logic (golden prompts, validation, filter compilation)
- `test_integration.py` - Integration tests that make HTTP requests to the running service
- `test_pgr_nlq.py` - PGR-specific golden test cases
- `test_ai_comprehensive.py` - **Comprehensive end-to-end tests for AI NLQ agent** (NEW)

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

### Comprehensive AI Tests (NEW)
```bash
# Terminal 1: Start the service
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
uvicorn agent.app.main:app --reload --port 8000

# Terminal 2: Run comprehensive tests
cd /Users/manishsv/Documents/Projects/analytics
source .venv310/bin/activate
pytest agent/tests/test_ai_comprehensive.py -v --tb=short

# Or use the test runner script
./agent/tests/test_ai_runner.sh
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

## Comprehensive AI Test Suite

The `test_ai_comprehensive.py` file contains **28+ end-to-end test cases** that validate:

### Test Categories:

1. **Basic Metric Queries** (3 tests)
   - Total complaints, sales, resolution rate
   - Validates metric selection

2. **Queries with Dimensions** (3 tests)
   - Complaints by ward, sales by geo/channel
   - Validates dimension grouping

3. **Queries with Filters** (3 tests)
   - Complaints for specific ward/geo, not closed status
   - Validates filter generation and case sensitivity

4. **"Which X has the most Y" Queries** (3 tests)
   - Ward with most complaints, not closed, geo with most sales
   - Validates top N aggregation and client-side aggregation

5. **Time-Based Queries** (5 tests)
   - By days, weeks, months, years, last 2 years
   - Validates time granularity detection and aggregation

6. **PGR-Specific Queries** (4 tests)
   - Funnel, SLA breach, TAT, priority filters
   - Validates domain-specific metrics and dimensions

7. **Sales-Specific Queries** (3 tests)
   - Period filters, avg price, volume by geo
   - Validates sales domain metrics and filters

8. **Edge Cases & Error Handling** (4 tests)
   - Empty questions, invalid metrics, vague queries
   - Validates error handling and graceful failures

### Additional Validation Tests:

- Response structure validation
- Explanation accuracy
- Case sensitivity for status filters
- Aggregation for top N queries

### Running the Comprehensive Tests:

```bash
# Ensure service is running
uvicorn agent.app.main:app --reload --port 8000

# Run all comprehensive tests
pytest agent/tests/test_ai_comprehensive.py -v --tb=short

# Run specific test category
pytest agent/tests/test_ai_comprehensive.py::test_basic_queries -v

# Run with detailed output
pytest agent/tests/test_ai_comprehensive.py -v -s
```

### Test Coverage:

✅ Natural language interpretation  
✅ Query plan generation  
✅ Filter handling (including case sensitivity)  
✅ Time granularity detection  
✅ Top N aggregation  
✅ Error handling  
✅ Response formatting  
✅ Explanation accuracy  
✅ Client-side aggregation for "which X has the most Y" queries

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
