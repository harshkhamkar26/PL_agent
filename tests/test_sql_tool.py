"""Unit tests for SQL Query Tool & AST Safety Guardrails."""
import pytest
from tools.sql_tool import SQLQueryTool
from validation.sql_validator import SQLValidator

@pytest.fixture
def sql_tool():
    return SQLQueryTool()

def test_sql_validator_safety():
    # Safe
    valid, _, _ = SQLValidator.validate_query("SELECT COUNT(*) FROM portfolios;")
    assert valid is True

    # Mutation disallowed
    valid, err, _ = SQLValidator.validate_query("DROP TABLE portfolios;")
    assert valid is False
    assert "Disallowed query type" in err

    # Injection disallowed
    valid, err, _ = SQLValidator.validate_query("SELECT * FROM portfolios; DELETE FROM holdings;")
    assert valid is False

def test_ground_truth_sql_queries(sql_tool):
    test_queries = [
        "How many portfolios do we have in total?",
        "What are the names of all active portfolios?",
        "Which securities are in the Technology sector?",
        "What is the total Assets Under Management (AUM) for portfolios with high target risk level?",
    ]
    for q in test_queries:
        res = sql_tool.execute_text2sql(q)
        assert res["success"] is True
        assert res["row_count"] > 0
