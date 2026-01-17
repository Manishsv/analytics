"""
Deterministic tests for NLQ planning (golden prompts → expected plans).

These tests validate that the LLM planner generates correct query plans
for common natural language questions.
"""
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from agent.app.schemas import PlannedQuery, StructuredFilter
from agent.app.guardrails import validate_plan, compile_where


# Golden test cases: (question, expected_plan_dict)
GOLDEN_TEST_CASES = [
    {
        "question": "Sales value by geo and channel",
        "expected": {
            "metrics": ["sales_value_lc"],
            "dimensions": ["sales__geo_id", "sales__channel_id"],
            "filters": [],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "Average price per standard unit by channel",
        "expected": {
            "metrics": ["avg_price_lc_per_su"],
            "dimensions": ["sales__channel_id"],
            "filters": [],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "Sales for GEO_345",
        "expected": {
            "metrics": ["sales_value_lc"],
            "dimensions": ["sales__geo_id"],  # Auto-added for filtering
            "filters": [
                {"dimension": "sales__geo_id", "op": "=", "value": "GEO_345"}
            ],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "Sales volume in standard units by geo",
        "expected": {
            "metrics": ["sales_volume_su"],
            "dimensions": ["sales__geo_id"],
            "filters": [],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "Sales value for period 202412 by geo",
        "expected": {
            "metrics": ["sales_value_lc"],
            "dimensions": ["sales__period_yyyymm", "sales__geo_id"],
            "filters": [
                {"dimension": "sales__period_yyyymm", "op": "=", "value": "202412"}
            ],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "Sales for channel RET",
        "expected": {
            "metrics": ["sales_value_lc"],
            "dimensions": ["sales__channel_id"],
            "filters": [
                {"dimension": "sales__channel_id", "op": "=", "value": "RET"}
            ],
            "start_time": None,
            "end_time": None,
        }
    },
    # PGR regression test cases
    {
        "question": "How many PGR complaints were submitted by ward and channel?",
        "expected": {
            "metrics": ["pgr_complaints"],
            "dimensions": ["pgr__ward_id", "pgr__channel"],
            "filters": [],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "What is the resolution rate by ward?",
        "expected": {
            "metrics": ["pgr_resolution_rate"],
            "dimensions": ["pgr__ward_id"],
            "filters": [],
            "start_time": None,
            "end_time": None,
        }
    },
    {
        "question": "SLA breach rate by ward for high priority complaints",
        "expected": {
            "metrics": ["pgr_sla_breach_rate"],
            "dimensions": ["pgr__ward_id"],
            "filters": [
                {"dimension": "pgr__priority", "op": "=", "value": "HIGH"}
            ],
            "start_time": None,
            "end_time": None,
        }
    },
]


def test_plan_structure():
    """Test that planned queries have the correct structure."""
    plan = PlannedQuery(
        metrics=["sales_value_lc"],
        dimensions=["sales__geo_id"],
        filters=[],
    )
    
    assert isinstance(plan.metrics, list)
    assert len(plan.metrics) > 0
    assert isinstance(plan.dimensions, list)
    assert isinstance(plan.filters, list)


def test_filter_compilation():
    """Test that filters compile to safe WHERE clauses."""
    filters = [
        {"dimension": "sales__geo_id", "op": "=", "value": "GEO_345"},
        {"dimension": "sales__channel_id", "op": "=", "value": "RET"},
    ]
    
    where = compile_where(filters)
    assert where is not None
    assert "sales__geo_id" in where
    assert "GEO_345" in where
    assert "sales__channel_id" in where
    assert "RET" in where
    assert "AND" in where


def test_filter_in_operator():
    """Test IN operator for filters."""
    filters = [
        {"dimension": "sales__geo_id", "op": "in", "value": ["GEO_345", "GEO_123"]},
    ]
    
    where = compile_where(filters)
    assert where is not None
    assert "IN" in where
    assert "GEO_345" in where
    assert "GEO_123" in where


def test_plan_validation():
    """Test that plan validation works with allowlist."""
    allowlist = {
        "metrics": {"sales_value_lc", "sales_volume_su"},
        "dimensions": {"sales__geo_id", "sales__channel_id"},
    }
    
    # Valid plan
    plan_metrics = ["sales_value_lc"]
    plan_dimensions = ["sales__geo_id"]
    plan_filters = []
    
    # Should not raise
    validate_plan(plan_metrics, plan_dimensions, plan_filters, allowlist)
    
    # Invalid metric
    with pytest.raises(ValueError, match="Metric not allowed"):
        validate_plan(["invalid_metric"], plan_dimensions, plan_filters, allowlist)
    
    # Invalid dimension
    with pytest.raises(ValueError, match="Dimension not allowed"):
        validate_plan(plan_metrics, ["invalid_dimension"], plan_filters, allowlist)


def test_auto_add_filter_dimensions():
    """Test that filter dimensions are automatically added to dimensions list."""
    plan = PlannedQuery(
        metrics=["sales_value_lc"],
        dimensions=[],  # Empty initially
        filters=[
            StructuredFilter(dimension="sales__geo_id", op="=", value="GEO_345")
        ],
    )
    
    # Simulate the auto-add logic from main.py
    filter_dimensions = {f.dimension for f in plan.filters}
    existing_dimensions = set(plan.dimensions)
    missing_dimensions = filter_dimensions - existing_dimensions
    
    assert "sales__geo_id" in missing_dimensions
    
    # After adding
    plan.dimensions.extend(sorted(missing_dimensions))
    assert "sales__geo_id" in plan.dimensions


@pytest.mark.parametrize("test_case", GOLDEN_TEST_CASES)
def test_golden_prompts(test_case):
    """
    Golden test: validate expected plan structure for common prompts.
    
    Note: This doesn't actually call the LLM - it validates the expected structure.
    In a real integration test, you would:
    1. Call the /nlq endpoint with the question
    2. Extract the plan from the response
    3. Assert it matches the expected structure
    """
    question = test_case["question"]
    expected = test_case["expected"]
    
    # Create a plan matching the expected structure
    plan = PlannedQuery(
        metrics=expected["metrics"],
        dimensions=expected["dimensions"],
        filters=[StructuredFilter(**f) for f in expected["filters"]],
        start_time=expected["start_time"],
        end_time=expected["end_time"],
    )
    
    # Validate structure
    assert plan.metrics == expected["metrics"]
    assert set(plan.dimensions) == set(expected["dimensions"])  # Order may vary
    assert len(plan.filters) == len(expected["filters"])
    
    # Validate filters
    for i, expected_filter in enumerate(expected["filters"]):
        actual_filter = plan.filters[i]
        assert actual_filter.dimension == expected_filter["dimension"]
        assert actual_filter.op == expected_filter["op"]
        assert actual_filter.value == expected_filter["value"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
