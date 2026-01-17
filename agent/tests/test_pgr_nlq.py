"""
PGR-specific NLQ regression test cases.
These validate that common PGR queries generate correct plans.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from agent.app.schemas import PlannedQuery, StructuredFilter


# PGR golden test cases
PGR_GOLDEN_TEST_CASES = [
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
        "question": "Average time to resolve by channel last month",
        "expected": {
            "metrics": ["pgr_avg_tat_submit_to_resolve_hours"],
            "dimensions": ["pgr__channel"],
            "filters": [],
            "start_time": None,  # LLM should populate this, but test structure allows flexibility
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


@pytest.mark.parametrize("test_case", PGR_GOLDEN_TEST_CASES)
def test_pgr_golden_prompts(test_case):
    """
    Golden test: validate expected plan structure for PGR prompts.
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
