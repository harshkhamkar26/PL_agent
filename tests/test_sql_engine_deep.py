"""
Deep Unit & Security Test Suite for Explainable SQL Query Engine (Phase 2).
Validates all 8 SQL evaluation questions, AST security enforcement,
index utilization, and aggregation evidence breakdown.
"""

import pytest
from tools.sql_tool import SQLQueryTool
from validation.sql_validator import SQLValidator
from database.db_manager import DatabaseManager


@pytest.fixture
def db_mgr():
    return DatabaseManager()


@pytest.fixture
def sql_tool(db_mgr):
    return SQLQueryTool(db_manager=db_mgr)


# --- 1. All 8 Ground Truth SQL Questions ---

def test_q1_count_portfolios(sql_tool):
    res = sql_tool.execute_text2sql("How many portfolios do we have in total?")
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0]["COUNT(*)"] == 13
    assert "portfolios" in res["tables_used"]
    # Check aggregation breakdown
    assert res["aggregation_breakdown"] is not None
    assert res["aggregation_breakdown"]["type"] == "count_breakdown"


def test_q2_active_portfolios(sql_tool):
    res = sql_tool.execute_text2sql("What are the names of all active portfolios?")
    assert res["success"] is True
    assert res["row_count"] == 10
    names = [r["portfolio_name"] for r in res["rows"]]
    assert "Growth Equity Fund" in names
    assert "Conservative Income Fund" in names


def test_q3_tech_securities(sql_tool):
    res = sql_tool.execute_text2sql("Which securities are in the Technology sector?")
    assert res["success"] is True
    assert res["row_count"] == 8
    symbols = [r["symbol"] for r in res["rows"]]
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "NVDA" in symbols
    assert "idx_securities_sector" in res["indexes_used"] or "sqlite_autoindex_sectors_1" in res["indexes_used"]


def test_q4_high_risk_aum(sql_tool):
    res = sql_tool.execute_text2sql("What is the total Assets Under Management (AUM) for portfolios with high target risk level?")
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0]["SUM(total_aum)"] == 85000000.0
    # Check breakdown proof
    breakdown = res["aggregation_breakdown"]
    assert breakdown is not None
    assert breakdown["type"] == "sum_breakdown"
    assert len(breakdown["items"]) == 4
    sum_items = sum(i["total_aum"] for i in breakdown["items"])
    assert sum_items == 85000000.0


def test_q5_growth_equity_top5(sql_tool):
    res = sql_tool.execute_text2sql("Show me the top 5 holdings by cost basis in the Growth Equity Fund")
    assert res["success"] is True
    assert res["row_count"] == 5
    top1 = res["rows"][0]
    assert top1["symbol"] == "AAPL"
    assert top1["cost_basis"] == 438000.0
    # Check indexes utilized for 3-table join
    assert len(res["indexes_used"]) > 0


def test_q6_avg_price_by_sector(sql_tool):
    res = sql_tool.execute_text2sql("What is the average current price of securities in each sector?")
    assert res["success"] is True
    assert res["row_count"] == 7
    top_sec = res["rows"][0]
    assert top_sec["sector_name"] == "Consumer Discretionary"
    assert top_sec["avg_price"] == 3380.0


def test_q7_tech_holdings_percentage_ctes(sql_tool):
    res = sql_tool.execute_text2sql("For each portfolio, show the total value of Technology sector holdings and what percentage it represents of the total portfolio value")
    assert res["success"] is True
    assert res["row_count"] == 8
    top = res["rows"][0]
    assert top["portfolio_name"] == "Tech Innovation Fund"
    assert top["tech_percentage"] == 100.0


def test_q8_sector_diversification_metrics(sql_tool):
    res = sql_tool.execute_text2sql("Find portfolios that have holdings in more than 5 different sectors and show their diversification metrics")
    assert res["success"] is True
    assert res["row_count"] == 1
    r = res["rows"][0]
    assert r["portfolio_name"] == "Total Stock Market Index Fund"
    assert r["sector_count"] == 6
    assert r["total_holdings"] == 12
    assert r["diversification_ratio"] == 0.5


# --- 2. Security Sandbox & Injection Defense ---

@pytest.mark.parametrize("malicious_sql", [
    "DROP TABLE portfolios;",
    "DELETE FROM holdings WHERE holding_id = 1;",
    "UPDATE portfolios SET total_aum = 999999;",
    "INSERT INTO portfolios (portfolio_name) VALUES ('Hacked Fund');",
    "ALTER TABLE securities ADD COLUMN secret TEXT;",
    "PRAGMA database_list;",
    "SELECT * FROM non_existent_secret_table;",
    "SELECT * FROM portfolios; DROP TABLE holdings;",
])
def test_sql_validator_rejects_malicious_queries(db_mgr, malicious_sql):
    conn = db_mgr.get_connection()
    is_safe, error, clean_sql = SQLValidator.validate_query(malicious_sql, db_conn=conn)
    conn.close()
    assert is_safe is False
    assert error is not None


def test_sql_validator_extract_tables():
    sql = "SELECT p.portfolio_name, s.symbol FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id WHERE s.asset_type = 'Stock';"
    tables = SQLValidator.extract_tables(sql)
    assert set(tables) == {"portfolios", "holdings", "securities"}
