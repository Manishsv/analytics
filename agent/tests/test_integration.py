"""
Integration tests for the NLQ endpoint.

These tests make actual HTTP requests to the running service.
Run with: pytest agent/tests/test_integration.py -v
"""
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
import httpx
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


@pytest.fixture
def client():
    """HTTP client for making requests."""
    return httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)


@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_catalog_endpoint(client: httpx.AsyncClient):
    """Test catalog endpoint returns metrics and dimensions."""
    response = await client.get("/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "metrics_raw" in data
    assert "dimensions_raw" in data
    assert len(data["metrics_raw"]) > 0


@pytest.mark.asyncio
async def test_nlq_basic_query(client: httpx.AsyncClient):
    """Test basic NLQ query."""
    response = await client.post(
        "/nlq",
        json={"question": "Sales value by geo", "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    
    # Validate response structure
    assert "plan" in data
    assert "execution" in data
    assert "explanation" in data
    
    # Validate plan
    plan = data["plan"]
    assert "metrics" in plan
    assert len(plan["metrics"]) > 0
    assert plan["metrics"][0] == "sales_value_lc"
    
    # Validate explanation
    explanation = data["explanation"]
    assert "metrics" in explanation
    assert "dimensions" in explanation
    assert "filters" in explanation


@pytest.mark.asyncio
async def test_nlq_with_filter(client: httpx.AsyncClient):
    """Test NLQ query with filter."""
    response = await client.post(
        "/nlq",
        json={"question": "Sales for GEO_345", "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    
    plan = data["plan"]
    assert len(plan["filters"]) > 0
    assert plan["filters"][0]["dimension"] == "sales__geo_id"
    assert plan["filters"][0]["value"] == "GEO_345"
    
    # Filter dimension should be auto-added to dimensions
    assert "sales__geo_id" in plan["dimensions"]


@pytest.mark.asyncio
async def test_nlq_explanation_structure(client: httpx.AsyncClient):
    """Test that explanation includes all required fields."""
    response = await client.post(
        "/nlq",
        json={"question": "Sales value by geo and channel", "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    
    explanation = data["explanation"]
    
    # Check explanation fields
    assert "metrics" in explanation
    assert isinstance(explanation["metrics"], list)
    assert len(explanation["metrics"]) > 0
    
    assert "dimensions" in explanation
    assert isinstance(explanation["dimensions"], list)
    
    assert "filters" in explanation
    assert isinstance(explanation["filters"], list)
    
    assert "where_clause" in explanation  # May be None if no filters
    
    # Metric definition structure
    if explanation["metrics"]:
        metric = explanation["metrics"][0]
        assert "name" in metric
        assert "description" in metric  # May be None
        assert "type" in metric  # May be None


@pytest.mark.asyncio
async def test_rate_limiting(client: httpx.AsyncClient):
    """Test that rate limiting is active (should not fail immediately)."""
    # Make a few requests quickly
    responses = []
    for _ in range(5):
        response = await client.post(
            "/nlq",
            json={"question": "Sales value", "limit": 10}
        )
        responses.append(response.status_code)
    
    # All should succeed (we're under the limit)
    assert all(status == 200 for status in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
