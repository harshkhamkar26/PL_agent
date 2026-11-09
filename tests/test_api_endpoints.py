"""
Integration Test Suite for FastAPI REST Endpoints (Phase 6).
Verifies HTTP status codes, JSON response schemas, CSV exports,
and quantitative error handling using FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["database"]["tables"] == 9
    assert data["database"]["records"] == 603


def test_api_query_sql(client):
    r = client.post("/api/v1/query", json={"question": "How many portfolios do we have in total?"})
    assert r.status_code == 200
    data = r.json()
    assert data["selected_tool"] == "sql_query_tool"
    assert "13" in data["direct_answer"]
    assert "telemetry" in data


def test_api_query_exposure(client):
    r = client.post("/api/v1/query", json={"question": "What are the sector exposures for the Tech Innovation Fund?"})
    assert r.status_code == 200
    data = r.json()
    assert data["selected_tool"] == "exposure_calculator"
    assert "Technology: 100.0%" in data["direct_answer"]


def test_api_get_exposure_direct(client):
    r = client.get("/api/v1/exposure/Tech%20Innovation%20Fund")
    assert r.status_code == 200
    data = r.json()
    assert data["sector_exposures"] == {"Technology": 100.0}
    assert data["hhi_concentration"] == 1.0


def test_api_compare_portfolios(client):
    r = client.get("/api/v1/compare/Tech%20Innovation%20Fund/International%20Equity%20Fund")
    assert r.status_code == 200
    data = r.json()
    assert data["sectors_compared"] == 4
    assert len(data["comparison_matrix"]) == 4


def test_api_list_portfolios(client):
    r = client.get("/api/v1/portfolios")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 13
    assert len(data["portfolios"]) == 13


def test_api_portfolio_performance(client):
    r = client.get("/api/v1/portfolio/1/performance")
    assert r.status_code == 200
    data = r.json()
    assert data["portfolio_id"] == 1
    assert len(data["performance_records"]) > 0
    assert len(data["risk_records"]) > 0


def test_api_reconcile_portfolio(client):
    r = client.get("/api/v1/reconcile/11")
    assert r.status_code == 200
    data = r.json()
    assert data["unallocated_weight_pct"] == 2.0


def test_api_export_audit_csv(client):
    r = client.get("/api/v1/export/audit-csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "Portfolio ID,Portfolio Name" in r.text
    assert "Total Stock Market Index Fund" in r.text


def test_api_metrics_glossary(client):
    r = client.get("/api/v1/metrics/glossary")
    assert r.status_code == 200
    data = r.json()
    assert "Sharpe Ratio" in data
    assert "VaR 95%" in str(data)
    assert "Herfindahl-Hirschman Index (HHI)" in data


def test_api_query_history(client):
    r = client.get("/api/v1/history")
    assert r.status_code == 200
    data = r.json()
    assert "total_queries" in data


def test_api_evaluate_endpoint(client):
    r = client.get("/api/v1/evaluate")
    assert r.status_code == 200
    data = r.json()
    assert data["total_questions"] == 10
    assert data["accuracy_pct"] == 100.0


def test_api_dashboard_html_serving(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "PL CAPITAL" in r.text
    assert "FINANCE INTELLIGENCE AGENT" in r.text

    r2 = client.get("/dashboard")
    assert r2.status_code == 200
    assert "text/html" in r2.headers["content-type"]
    assert "PL CAPITAL" in r2.text


def test_api_dataset_tables(client):
    r = client.get("/api/v1/dataset/tables")
    assert r.status_code == 200
    data = r.json()
    assert data["total_tables"] == 9
    assert data["total_records"] == 603
    assert len(data["tables"]) == 9


def test_api_dataset_table_data(client):
    r = client.get("/api/v1/dataset/table/portfolios?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert data["table_name"] == "portfolios"
    assert data["total_rows"] == 13
    assert len(data["rows"]) == 5
    assert len(data["columns"]) == 8


def test_api_dataset_custom_sql(client):
    r = client.post("/api/v1/dataset/sql", json={"sql": "SELECT COUNT(*) as count FROM securities WHERE asset_type = 'Stock';"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["rows"][0]["count"] == 25


def test_api_dataset_custom_sql_rejected(client):
    r = client.post("/api/v1/dataset/sql", json={"sql": "DROP TABLE holdings;"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "Disallowed query type" in data["error"]


def test_api_dataset_table_csv(client):
    r = client.get("/api/v1/dataset/table/sectors/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "sector_id,sector_name" in r.text



