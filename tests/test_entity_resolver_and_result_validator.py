"""
Unit tests for EntityResolver, AST SQLValidator, and ResultValidator.
"""

import pytest
from agent.entity_resolver import default_entity_resolver
from validation.result_validator import ResultValidator
from validation.sql_validator import SQLValidator


def test_entity_resolver_securities():
    # Test ticker resolution
    aapl = default_entity_resolver.resolve_security("AAPL")
    assert aapl is not None
    assert aapl.symbol == "AAPL"
    assert aapl.company_name == "Apple Inc."

    # Test company name resolution
    apple = default_entity_resolver.resolve_security("Which portfolios hold Apple?")
    assert apple is not None
    assert apple.symbol == "AAPL"

    # Test Microsoft
    msft = default_entity_resolver.resolve_security("Microsoft Corporation")
    assert msft is not None
    assert msft.symbol == "MSFT"

    # Test NVIDIA alias
    nvda = default_entity_resolver.resolve_security("Show NVIDIA holdings")
    assert nvda is not None
    assert nvda.symbol == "NVDA"

    # Test bond
    bond = default_entity_resolver.resolve_security("10Y Treasury")
    assert bond is not None
    assert bond.symbol == "UST-10Y"
    assert bond.asset_type == "Bond"


def test_entity_resolver_portfolios():
    # Exact portfolio name
    p = default_entity_resolver.resolve_portfolio("Growth Equity Fund")
    assert p is not None
    assert p.portfolio_id == 1

    # Fuzzy/alias portfolio match
    p2 = default_entity_resolver.resolve_portfolio("tech innovation")
    assert p2 is not None
    assert p2.portfolio_name == "Tech Innovation Fund"


def test_entity_resolver_sectors():
    # Sector alias
    s = default_entity_resolver.resolve_sector("Tech")
    assert s is not None
    assert s.sector_name == "Technology"

    s2 = default_entity_resolver.resolve_sector("Financials")
    assert s2 is not None
    assert s2.sector_id == 4


def test_ast_sql_validator_complex_cte():
    cte_query = """
    WITH high_perf AS (
        SELECT portfolio_id, AVG(total_return_1y) as avg_ret
        FROM portfolio_performance
        GROUP BY portfolio_id
    )
    SELECT p.portfolio_name, hp.avg_ret
    FROM high_perf hp
    JOIN portfolios p ON hp.portfolio_id = p.portfolio_id;
    """
    valid, err, sanitized = SQLValidator.validate_query(cte_query)
    assert valid is True
    assert err is None
    tables = SQLValidator.extract_tables(cte_query)
    assert "portfolio_performance" in tables
    assert "portfolios" in tables
    assert "high_perf" not in tables  # CTE alias excluded from physical tables


def test_ast_sql_validator_rejection():
    # Reject INSERT
    valid, err, _ = SQLValidator.validate_query("INSERT INTO portfolios (portfolio_name) VALUES ('Hacked Fund');")
    assert valid is False
    assert "Disallowed" in err

    # Reject PRAGMA
    valid, err, _ = SQLValidator.validate_query("PRAGMA table_info(portfolios);")
    assert valid is False

    # Reject comment injection
    valid, err, _ = SQLValidator.validate_query("SELECT * FROM portfolios -- malicious comment")
    assert valid is False


def test_result_validator_total_aum_shape():
    # Valid scalar AUM
    valid, err = ResultValidator.validate_sql_result(
        question="What is the total AUM across all portfolios?",
        generated_sql="SELECT SUM(total_aum) AS total_aum FROM portfolios;",
        rows=[{"total_aum": 323500000.0}],
        columns=["total_aum"],
    )
    assert valid is True

    # Multi-row raw dump when scalar expected
    invalid, err = ResultValidator.validate_sql_result(
        question="What is the total AUM across all portfolios?",
        generated_sql="SELECT portfolio_name, total_aum FROM portfolios;",
        rows=[{"total_aum": 100000.0}, {"total_aum": 200000.0}],
        columns=["portfolio_name", "total_aum"],
    )
    assert invalid is False
    assert "Aggregate intent mismatch" in err


def test_result_validator_financial_sanity():
    # Negative AUM
    invalid, err = ResultValidator.validate_sql_result(
        question="Show portfolio AUM",
        generated_sql="SELECT total_aum FROM portfolios;",
        rows=[{"total_aum": -5000.0}],
        columns=["total_aum"],
    )
    assert invalid is False
    assert "Negative AUM" in err

    # Exposure percentage outside [0, 100]
    invalid_exp, err = ResultValidator.validate_exposure_result(
        exposure_data={"portfolio_name": "Test Fund", "sector_exposures": {"Technology": 150.0}}
    )
    assert invalid_exp is False
    assert "invalid percentage" in err
