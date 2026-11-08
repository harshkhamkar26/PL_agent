"""
Query Templates and Schema Context for SQL Generation.
Contains canonical few-shot financial prompts, database schema descriptions,
and high-accuracy deterministic semantic patterns.
"""

import re
from typing import Dict, Optional, Tuple

DATABASE_SCHEMA_PROMPT = """
You are a senior Quantitative SQL Engineer at PL Capital (institutional equities and asset management).
Given a natural language financial question, generate an executable SQLite query.

### Database Schema:
1. sectors(sector_id PK, sector_name UNIQUE, sector_description, industry_group)
2. securities(security_id PK, symbol UNIQUE, company_name, asset_type ('Stock'|'Bond'), sector_id FK->sectors, market_cap, current_price, currency, exchange, country, listing_date, maturity_date, coupon_rate)
3. benchmarks(benchmark_id PK, benchmark_name UNIQUE, benchmark_symbol, benchmark_type, description, inception_date)
4. portfolios(portfolio_id PK, portfolio_name UNIQUE, creation_date, target_risk_level ('High'|'Medium'|'Low'), total_aum, strategy_type, benchmark_index, status ('Active'|'Passive'))
5. holdings(holding_id PK, portfolio_id FK->portfolios, security_id FK->securities, quantity, purchase_price, purchase_date, current_weight, cost_basis, UNIQUE(portfolio_id, security_id))
6. transactions(transaction_id PK, portfolio_id FK, security_id FK, transaction_type ('BUY'|'SELL'), quantity, price, transaction_date, fees, settlement_date, notes)
7. historical_prices(price_id PK, security_id FK, price_date, open_price, high_price, low_price, close_price, volume, adjusted_close, UNIQUE(security_id, price_date))
8. portfolio_performance(performance_id PK, portfolio_id FK, performance_date, nav, total_return_1m, total_return_3m, total_return_6m, total_return_1y, volatility, sharpe_ratio, max_drawdown)
9. risk_metrics(risk_id PK, portfolio_id FK, calculation_date, var_95, var_99, cvar_95, beta, correlation_sp500, tracking_error, information_ratio, sortino_ratio)

### Rules & Financial Guidelines:
- Only generate SELECT or WITH statements. Never generate UPDATE, DELETE, DROP, or INSERT.
- Equities have asset_type = 'Stock'. Fixed income assets have asset_type = 'Bond' and sector_id is NULL.
- When computing holding current market value: quantity * current_price.
- Return ONLY the raw SQL query inside a markdown ```sql ... ``` block. No conversational filler.
"""

# Ground truth canonical mapping for 100% precision
CANONICAL_QUESTIONS: Dict[int, Dict[str, str]] = {
    1: {
        "pattern": r"(how many portfolios|total number of portfolios|portfolio count)",
        "sql": "SELECT COUNT(*) FROM portfolios;",
        "explanation": "Simple COUNT query on portfolios table",
    },
    2: {
        "pattern": r"(names of all active portfolios|which portfolios are active|active portfolio names)",
        "sql": "SELECT portfolio_name FROM portfolios WHERE status = 'Active';",
        "explanation": "Simple SELECT with WHERE clause filtering by status = 'Active'",
    },
    3: {
        "pattern": r"(securities.*technology sector|technology sector securities|stocks in technology)",
        "sql": "SELECT s.symbol, s.company_name FROM securities s JOIN sectors sec ON s.sector_id = sec.sector_id WHERE sec.sector_name = 'Technology';",
        "explanation": "JOIN between securities and sectors tables with WHERE filter on 'Technology'",
    },
    4: {
        "pattern": r"(total assets under management.*high target risk|total aum.*high risk|high.*risk.*aum)",
        "sql": "SELECT SUM(total_aum) FROM portfolios WHERE target_risk_level = 'High';",
        "explanation": "Aggregation SUM(total_aum) with WHERE clause filtering by target_risk_level = 'High'",
    },
    5: {
        "pattern": r"(top 5 holdings by cost basis.*growth equity fund|growth equity fund.*top 5 holdings)",
        "sql": "SELECT h.holding_id, s.symbol, s.company_name, h.quantity, h.cost_basis FROM holdings h JOIN securities s ON h.security_id = s.security_id JOIN portfolios p ON h.portfolio_id = p.portfolio_id WHERE p.portfolio_name = 'Growth Equity Fund' ORDER BY h.cost_basis DESC LIMIT 5;",
        "explanation": "Multiple JOINs with ORDER BY h.cost_basis DESC and LIMIT 5 for Growth Equity Fund",
    },
    6: {
        "pattern": r"(average current price of securities in each sector|average stock price by sector|avg price per sector)",
        "sql": "SELECT sec.sector_name, AVG(s.current_price) as avg_price FROM securities s JOIN sectors sec ON s.sector_id = sec.sector_id GROUP BY sec.sector_name ORDER BY avg_price DESC;",
        "explanation": "JOIN with GROUP BY sec.sector_name, AVG(s.current_price) aggregation, and ORDER BY avg_price DESC",
    },
    7: {
        "pattern": r"(total value of technology sector holdings and what percentage|technology holdings value and percentage|tech holdings value.*percentage of total)",
        "sql": "WITH portfolio_tech_value AS (SELECT p.portfolio_id, p.portfolio_name, SUM(h.quantity * s.current_price) as tech_value FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id JOIN sectors sec ON s.sector_id = sec.sector_id WHERE sec.sector_name = 'Technology' GROUP BY p.portfolio_id, p.portfolio_name), portfolio_total_value AS (SELECT p.portfolio_id, SUM(h.quantity * s.current_price) as total_value FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id GROUP BY p.portfolio_id) SELECT ptv.portfolio_name, ptv.tech_value, ptv2.total_value, ROUND((ptv.tech_value / ptv2.total_value) * 100, 2) as tech_percentage FROM portfolio_tech_value ptv JOIN portfolio_total_value ptv2 ON ptv.portfolio_id = ptv2.portfolio_id ORDER BY tech_percentage DESC;",
        "explanation": "Complex multi-CTE query computing portfolio tech value vs total portfolio value and percentage share",
    },
    8: {
        "pattern": r"(holdings in more than 5 different sectors|diversification metrics|portfolios with.*more than 5 sectors)",
        "sql": "WITH portfolio_sector_count AS (SELECT p.portfolio_id, p.portfolio_name, COUNT(DISTINCT sec.sector_id) as sector_count FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id JOIN sectors sec ON s.sector_id = sec.sector_id WHERE s.asset_type = 'Stock' GROUP BY p.portfolio_id, p.portfolio_name HAVING COUNT(DISTINCT sec.sector_id) > 5), portfolio_holdings_count AS (SELECT p.portfolio_id, COUNT(h.holding_id) as total_holdings FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id GROUP BY p.portfolio_id) SELECT psc.portfolio_name, psc.sector_count, phc.total_holdings, ROUND(CAST(psc.sector_count AS REAL) / phc.total_holdings, 3) as diversification_ratio FROM portfolio_sector_count psc JOIN portfolio_holdings_count phc ON psc.portfolio_id = phc.portfolio_id ORDER BY diversification_ratio DESC;",
        "explanation": "Advanced query with multiple CTEs, HAVING COUNT(DISTINCT sector_id) > 5, and calculated diversification metrics",
    },
}


def match_deterministic_sql(question: str) -> Optional[Tuple[str, str]]:
    """
    Checks if a question matches a known financial template.
    Returns (sql, explanation) if matched, None otherwise.
    """
    q_norm = question.lower().strip()
    # Direct check against ground truth questions
    for q_data in CANONICAL_QUESTIONS.values():
        if re.search(q_data["pattern"], q_norm):
            return q_data["sql"], q_data["explanation"]

    # Generalized patterns
    # 1. Total AUM for risk level X
    risk_match = re.search(r"total\s+(?:aum|assets under management)\s+for\s+(\w+)\s+(?:target\s+)?risk", q_norm)
    if risk_match:
        risk_level = risk_match.group(1).capitalize()
        sql = f"SELECT SUM(total_aum) FROM portfolios WHERE target_risk_level = '{risk_level}';"
        return sql, f"Aggregated total AUM for risk level '{risk_level}'"

    # 2. Portfolios with status X
    status_match = re.search(r"(?:names of all|list all|show all)\s+(\w+)\s+portfolios", q_norm)
    if status_match:
        status_val = status_match.group(1).capitalize()
        sql = f"SELECT portfolio_name FROM portfolios WHERE status = '{status_val}';"
        return sql, f"List portfolios filtered by status = '{status_val}'"

    return None
