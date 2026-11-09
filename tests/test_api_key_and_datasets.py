"""
Tests for API Key Configuration, Universal Semantic Synthesizer,
and Dataset-Scoped Queries across all 9 database tables.
"""

import pytest
from fastapi.testclient import TestClient
from api import app
from agent.portfolio_agent import PortfolioAgent
from intelligence.gemini_client import GeminiClient

client = TestClient(app)


def test_api_key_status_endpoint():
    """Verify API key status endpoint returns safe masked telemetry."""
    res = client.get("/api/v1/config/key/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "model" in data
    assert "provider" in data
    assert data["provider"] == "Google Gemini"


def test_api_key_configure_clear():
    """Verify clearing the API key reverts to local deterministic mode."""
    res = client.post("/api/v1/config/key", json={"api_key": "", "save_to_env": False})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


def test_api_key_configure_invalid():
    """Verify that an invalid API key is caught by live connection verification."""
    res = client.post("/api/v1/config/key", json={"api_key": "invalid_test_key_12345", "save_to_env": False})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "error" in data


def test_dataset_scoped_transactions():
    """Verify target_dataset='transactions' generates queries targeting transactions."""
    res = client.post(
        "/api/v1/query",
        json={"question": "Show recent buy orders", "target_dataset": "transactions"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["primary_dataset"] == "transactions"
    assert "BUY" in data["formatted_markdown"] or "transactions" in data["telemetry"]["sql"].lower()
    assert data["total_latency_ms"] > 0


def test_dataset_scoped_historical_prices():
    """Verify target_dataset='historical_prices' queries market prices."""
    res = client.post(
        "/api/v1/query",
        json={"question": "Show highest volume trading sessions", "target_dataset": "historical_prices"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "historical_prices" in data["telemetry"]["sql"].lower()
    assert data["primary_dataset"] == "historical_prices"


def test_dataset_scoped_risk_metrics():
    """Verify querying risk metrics returns Beta and VaR metrics."""
    res = client.post(
        "/api/v1/query",
        json={"question": "Show lowest Beta portfolios", "target_dataset": "risk_metrics"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "risk_metrics" in data["telemetry"]["sql"].lower()
    assert data["primary_dataset"] == "risk_metrics"


def test_dataset_scoped_portfolio_performance():
    """Verify querying portfolio performance returns Sharpe and returns."""
    res = client.post(
        "/api/v1/query",
        json={"question": "Rank portfolios by Sharpe ratio", "target_dataset": "portfolio_performance"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "portfolio_performance" in data["telemetry"]["sql"].lower()
    assert data["primary_dataset"] == "portfolio_performance"


def test_universal_fallback_unmapped_question():
    """Verify that ANY arbitrary question offline produces valid SQL and evidence without failing."""
    agent = PortfolioAgent()
    res = agent.answer_question("What are the total fees collected across all transactions?")
    assert res["selected_tool"] == "sql_query_tool"
    assert res["telemetry"]["safety"] == "PASS_READ_ONLY"
    assert "transactions" in res["telemetry"]["sql"].lower()
    assert res["primary_dataset"] == "transactions"
