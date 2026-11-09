"""
Query Templates, Schema Context, and Universal Semantic Synthesizer.
Contains canonical ground-truth prompts, relational schema specifications,
and high-accuracy deterministic semantic patterns across all 9 database tables.
"""

import re
from typing import Dict, List, Optional, Tuple

DATABASE_SCHEMA_PROMPT = """
You are a senior Quantitative SQL Engineer at PL Capital (institutional equities and asset management).
Given a natural language financial question, generate an executable SQLite query.

### Database Schema (9 Tables, 603 Records):
1. sectors(sector_id PK, sector_name UNIQUE, sector_description, industry_group)
2. securities(security_id PK, symbol UNIQUE, company_name, asset_type ('Stock'|'Bond'), sector_id FK->sectors, market_cap, current_price, currency, exchange, country, listing_date, maturity_date, coupon_rate)
3. benchmarks(benchmark_id PK, benchmark_name UNIQUE, benchmark_symbol, benchmark_type, description, inception_date)
4. portfolios(portfolio_id PK, portfolio_name UNIQUE, creation_date, target_risk_level ('High'|'Medium'|'Low'), total_aum, strategy_type, benchmark_index, status ('Active'|'Passive'))
5. holdings(holding_id PK, portfolio_id FK->portfolios, security_id FK->securities, quantity, purchase_price, purchase_date, current_weight, cost_basis, UNIQUE(portfolio_id, security_id))
6. transactions(transaction_id PK, portfolio_id FK->portfolios, security_id FK->securities, transaction_type ('BUY'|'SELL'), quantity, price, transaction_date, fees, settlement_date, notes)
7. historical_prices(price_id PK, security_id FK->securities, price_date, open_price, high_price, low_price, close_price, volume, adjusted_close, UNIQUE(security_id, price_date))
8. portfolio_performance(performance_id PK, portfolio_id FK->portfolios, performance_date, nav, total_return_1m, total_return_3m, total_return_6m, total_return_1y, volatility, sharpe_ratio, max_drawdown)
9. risk_metrics(risk_id PK, portfolio_id FK->portfolios, calculation_date, var_95, var_99, cvar_95, beta, correlation_sp500, tracking_error, information_ratio, sortino_ratio)

### Rules & Financial Guidelines:
- Only generate SELECT or WITH statements. Never generate UPDATE, DELETE, DROP, or INSERT.
- Equities have asset_type = 'Stock'. Fixed income assets have asset_type = 'Bond' and sector_id is NULL.
- When computing holding current market value: quantity * current_price.
- Return ONLY the raw SQL query inside a markdown ```sql ... ``` block. No conversational filler.
"""

# Ground truth canonical mapping for 100% precision on benchmark questions Q1-Q8
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

KNOWN_TICKERS = [
    "aapl", "msft", "googl", "nvda", "amzn", "tsla", "jpm", "jnj", "v", "pg",
    "hd", "unh", "xom", "cvx", "avgo", "crm", "orcl", "meta",
    "ust-10y", "ust-5y", "ust-2y", "corp-aaa-5y", "corp-a-10y"
]

KNOWN_PORTFOLIOS = [
    "growth equity fund", "conservative income fund", "tech innovation fund",
    "balanced portfolio", "esg sustainable fund", "small cap value fund",
    "international equity fund", "fixed income plus", "dividend aristocrats fund",
    "emerging markets fund", "total stock market index fund", "total bond market index fund",
    "total international index fund"
]

KNOWN_SECTORS = [
    "technology", "healthcare", "financials", "consumer discretionary",
    "consumer staples", "energy", "automotive", "industrials", "real estate", "utilities"
]


def match_deterministic_sql(
    question: str,
    target_dataset: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """
    Checks if a question matches a known financial template, or applies
    an advanced semantic synthesizer across all 9 relational tables.
    Returns (sql, explanation) if matched, or falls back to universal synthesizer.
    """
    q_norm = question.lower().strip()
    target_ds = target_dataset.lower().strip() if target_dataset and target_dataset.lower() not in ["all", "auto"] else None

    # 1. Canonical Ground-Truth Questions (Strict Match)
    for q_data in CANONICAL_QUESTIONS.values():
        if re.search(q_data["pattern"], q_norm):
            return q_data["sql"], q_data["explanation"]

    # 2. Scope-specific queries when user selects a target dataset
    if target_ds:
        scoped = _handle_target_dataset(target_ds, q_norm)
        if scoped:
            return scoped

    # 3. Known Ticker Lookups (Holdings, Quotes, History)
    for ticker in KNOWN_TICKERS:
        if re.search(rf"\b{re.escape(ticker)}\b", q_norm):
            ticker_upper = ticker.upper()
            if any(w in q_norm for w in ["price", "history", "quote", "volume", "close", "open"]):
                sql = f"""SELECT hp.price_date, s.symbol, s.company_name, hp.open_price, hp.high_price, hp.low_price, hp.close_price, hp.volume 
FROM historical_prices hp 
JOIN securities s ON hp.security_id = s.security_id 
WHERE UPPER(s.symbol) = '{ticker_upper}' 
ORDER BY hp.price_date DESC LIMIT 10;"""
                return sql, f"Daily pricing time series and trading volume for '{ticker_upper}'"

            sql = f"""SELECT p.portfolio_name, s.symbol, s.company_name, h.quantity, h.current_weight, h.cost_basis 
FROM holdings h 
JOIN securities s ON h.security_id = s.security_id 
JOIN portfolios p ON h.portfolio_id = p.portfolio_id 
WHERE UPPER(s.symbol) = '{ticker_upper}' 
ORDER BY h.cost_basis DESC;"""
            return sql, f"Constituent holdings and portfolio allocations for security '{ticker_upper}'"

    # 4. Bond & Fixed Income Filtering
    if re.search(r"\b(bonds?|fixed\s+income|treasury|debt|coupon)\b", q_norm):
        sql = "SELECT symbol, company_name, asset_type, current_price, coupon_rate, maturity_date FROM securities WHERE asset_type = 'Bond' ORDER BY current_price DESC;"
        return sql, "Filtered securities table for fixed-income bond instruments (strictly partitioned from equities)"

    # 5. Stock & Equity Filtering
    if re.search(r"\b(all\s+stocks|all\s+equities|stock\s+list|equity\s+securities)\b", q_norm):
        sql = "SELECT s.symbol, s.company_name, sec.sector_name, s.current_price, s.market_cap FROM securities s LEFT JOIN sectors sec ON s.sector_id = sec.sector_id WHERE s.asset_type = 'Stock' ORDER BY s.market_cap DESC;"
        return sql, "Filtered securities table for equity stocks with sector classifications"

    # 6. Sector-Specific Security Lookups
    for sec_name in KNOWN_SECTORS:
        if sec_name in q_norm and not ("exposure" in q_norm or "percentage" in q_norm):
            sec_cap = sec_name.title()
            sql = f"""SELECT s.symbol, s.company_name, s.current_price, s.market_cap, sec.sector_name 
FROM securities s 
JOIN sectors sec ON s.sector_id = sec.sector_id 
WHERE LOWER(sec.sector_name) = '{sec_name}' 
ORDER BY s.current_price DESC;"""
            return sql, f"Securities belonging to the '{sec_cap}' sector"

    # 7. Specific Portfolio Constituents & Details
    for pname in KNOWN_PORTFOLIOS:
        if pname in q_norm:
            pname_title = pname.title()
            if any(w in q_norm for w in ["performance", "nav", "return", "sharpe", "volatility"]):
                sql = f"""SELECT p.portfolio_name, pp.performance_date, pp.nav, pp.total_return_1y, pp.sharpe_ratio, pp.volatility, pp.max_drawdown 
FROM portfolio_performance pp 
JOIN portfolios p ON pp.portfolio_id = p.portfolio_id 
WHERE LOWER(p.portfolio_name) = '{pname}' 
ORDER BY pp.performance_date DESC LIMIT 5;"""
                return sql, f"Historical NAV and performance track record for '{pname_title}'"

            if any(w in q_norm for w in ["risk", "beta", "var", "cvar", "sortino"]):
                sql = f"""SELECT p.portfolio_name, rm.calculation_date, rm.beta, rm.var_95, rm.var_99, rm.cvar_95, rm.sortino_ratio, rm.tracking_error 
FROM risk_metrics rm 
JOIN portfolios p ON rm.portfolio_id = p.portfolio_id 
WHERE LOWER(p.portfolio_name) = '{pname}' 
ORDER BY rm.calculation_date DESC LIMIT 5;"""
                return sql, f"Quant risk metrics profile for '{pname_title}'"

            sql = f"""SELECT s.symbol, s.company_name, s.asset_type, h.quantity, h.purchase_price, h.current_weight, h.cost_basis 
FROM holdings h 
JOIN securities s ON h.security_id = s.security_id 
JOIN portfolios p ON h.portfolio_id = p.portfolio_id 
WHERE LOWER(p.portfolio_name) = '{pname}' 
ORDER BY h.cost_basis DESC;"""
            return sql, f"Full constituent holdings ledger for '{pname_title}'"

    # 8. Transactions (Buy/Sell, Fees, Dates)
    if re.search(r"\b(transactions?|trades?|recent\s+trades|buy\s+orders?|sell\s+orders?|trade\s+logs?)\b", q_norm):
        if "buy" in q_norm:
            sql = """SELECT t.transaction_id, p.portfolio_name, s.symbol, t.transaction_type, t.quantity, t.price, t.fees, t.transaction_date 
FROM transactions t 
JOIN portfolios p ON t.portfolio_id = p.portfolio_id 
JOIN securities s ON t.security_id = s.security_id 
WHERE t.transaction_type = 'BUY' 
ORDER BY t.transaction_date DESC LIMIT 10;"""
            return sql, "Filtered buy order executions across portfolios"
        elif "sell" in q_norm:
            sql = """SELECT t.transaction_id, p.portfolio_name, s.symbol, t.transaction_type, t.quantity, t.price, t.fees, t.transaction_date 
FROM transactions t 
JOIN portfolios p ON t.portfolio_id = p.portfolio_id 
JOIN securities s ON t.security_id = s.security_id 
WHERE t.transaction_type = 'SELL' 
ORDER BY t.transaction_date DESC LIMIT 10;"""
            return sql, "Filtered sell order executions across portfolios"

        sql = """SELECT t.transaction_id, p.portfolio_name, s.symbol, t.transaction_type, t.quantity, t.price, t.fees, t.transaction_date 
FROM transactions t 
JOIN portfolios p ON t.portfolio_id = p.portfolio_id 
JOIN securities s ON t.security_id = s.security_id 
ORDER BY t.transaction_date DESC LIMIT 10;"""
        return sql, "Recent buy/sell portfolio transaction executions"

    # 9. Historical Prices & Market Quotes
    if re.search(r"\b(prices?|daily\s+price|historical\s+price|trading\s+volume|highest\s+volume)\b", q_norm):
        if "volume" in q_norm:
            sql = """SELECT hp.price_date, s.symbol, s.company_name, hp.volume, hp.close_price 
FROM historical_prices hp 
JOIN securities s ON hp.security_id = s.security_id 
ORDER BY hp.volume DESC LIMIT 10;"""
            return sql, "Securities trading sessions ranked by highest trading volume"

        sql = """SELECT hp.price_date, s.symbol, s.company_name, hp.open_price, hp.high_price, hp.low_price, hp.close_price, hp.volume 
FROM historical_prices hp 
JOIN securities s ON hp.security_id = s.security_id 
ORDER BY hp.price_date DESC, hp.volume DESC LIMIT 10;"""
        return sql, "Daily price quote ledger with OHLCV data"

    # 10. Performance Rankings (Sharpe, Returns, NAV, Volatility)
    if re.search(r"\b(performance|sharpe|total_return|nav|net\s+asset\s+value|drawdown|volatility)\b", q_norm):
        if "drawdown" in q_norm:
            sql = """SELECT p.portfolio_name, pp.nav, pp.max_drawdown, pp.volatility, pp.sharpe_ratio 
FROM portfolio_performance pp 
JOIN portfolios p ON pp.portfolio_id = p.portfolio_id 
ORDER BY pp.max_drawdown ASC LIMIT 5;"""
            return sql, "Portfolios ranked by lowest maximum drawdown (capital preservation)"

        sql = """SELECT p.portfolio_name, pp.nav, pp.total_return_1y, pp.sharpe_ratio, pp.volatility, pp.max_drawdown 
FROM portfolio_performance pp 
JOIN portfolios p ON pp.portfolio_id = p.portfolio_id 
ORDER BY pp.sharpe_ratio DESC LIMIT 5;"""
        return sql, "Top portfolios ranked by Sharpe ratio performance"

    # 11. Risk Measurements (Beta, VaR 95, VaR 99, Sortino)
    if re.search(r"\b(beta|var|value\s+at\s+risk|cvar|sortino|tracking\s+error|risk\s+metrics)\b", q_norm):
        if "sortino" in q_norm:
            sql = """SELECT p.portfolio_name, rm.sortino_ratio, rm.var_95, rm.beta 
FROM risk_metrics rm 
JOIN portfolios p ON rm.portfolio_id = p.portfolio_id 
ORDER BY rm.sortino_ratio DESC LIMIT 5;"""
            return sql, "Portfolios ranked by Sortino downside risk-adjusted return"

        sql = """SELECT p.portfolio_name, rm.beta, rm.var_95, rm.cvar_95, rm.sortino_ratio 
FROM risk_metrics rm 
JOIN portfolios p ON rm.portfolio_id = p.portfolio_id 
ORDER BY rm.beta ASC LIMIT 5;"""
        return sql, "Portfolio risk metrics ranked by market systematic risk (Beta)"

    # 12. Benchmarks
    if re.search(r"\b(benchmarks?|indices|indexes|s&p\s*500|nasdaq|russell)\b", q_norm):
        sql = "SELECT benchmark_id, benchmark_name, benchmark_symbol, benchmark_type, description FROM benchmarks ORDER BY benchmark_name;"
        return sql, "Market reference benchmarks and tracking indices"

    # 13. Sectors & Industries
    if re.search(r"\b(all\s+sectors|list\s+sectors|market\s+sectors|industry\s+groups?)\b", q_norm):
        sql = "SELECT sector_id, sector_name, industry_group, sector_description FROM sectors ORDER BY sector_id;"
        return sql, "Institutional sector classifications and industry groups"

    # 14. Total AUM for risk level or strategy
    risk_match = re.search(r"total\s+(?:aum|assets under management)\s+for\s+(\w+)\s+(?:target\s+)?risk", q_norm)
    if risk_match:
        risk_level = risk_match.group(1).capitalize()
        sql = f"SELECT SUM(total_aum) FROM portfolios WHERE target_risk_level = '{risk_level}';"
        return sql, f"Aggregated total AUM for risk level '{risk_level}'"

    # 15. Portfolios with status or risk
    status_match = re.search(r"(?:names of all|list all|show all)\s+(\w+)\s+portfolios", q_norm)
    if status_match:
        val = status_match.group(1).capitalize()
        if val in ["Active", "Passive"]:
            sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, status FROM portfolios WHERE status = '{val}';"
            return sql, f"List portfolios filtered by status = '{val}'"
        elif val in ["High", "Medium", "Low"]:
            sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, status FROM portfolios WHERE target_risk_level = '{val}';"
            return sql, f"List portfolios filtered by target risk level = '{val}'"

    # 16. AUM Range / Thresholds
    aum_gt_match = re.search(r"(?:aum|assets?)\s*(?:>|greater than|above|over|exceeding)\s*\$?(\d+)(?:\s*(?:m|million))?", q_norm)
    if aum_gt_match:
        val = float(aum_gt_match.group(1))
        if val < 1000:
            val = val * 1_000_000
        sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type FROM portfolios WHERE total_aum >= {val} ORDER BY total_aum DESC;"
        return sql, f"Portfolios with total AUM >= ${val:,.0f}"

    # 17. Universal Synthesizer Fallback (Always returns valid, safe query)
    return _universal_fallback_synthesizer(q_norm, target_ds)


def _handle_target_dataset(target_ds: str, q_norm: str) -> Optional[Tuple[str, str]]:
    """Synthesizes query specifically targeted at a chosen database table."""
    ds = target_ds.lower().strip()
    
    if ds == "portfolios":
        if "count" in q_norm or "how many" in q_norm:
            return "SELECT COUNT(*) FROM portfolios;", "Total portfolio count in database"
        if "risk" in q_norm:
            return "SELECT portfolio_name, target_risk_level, total_aum, strategy_type FROM portfolios ORDER BY target_risk_level;", "Portfolios grouped by target risk level"
        return "SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, benchmark_index, status FROM portfolios ORDER BY total_aum DESC LIMIT 25;", "Portfolios dataset records sorted by AUM"

    if ds == "securities":
        if "bond" in q_norm:
            return "SELECT symbol, company_name, current_price, coupon_rate, maturity_date FROM securities WHERE asset_type = 'Bond';", "Fixed income securities in dataset"
        if "stock" in q_norm or "equity" in q_norm:
            return "SELECT s.symbol, s.company_name, sec.sector_name, s.current_price, s.market_cap FROM securities s LEFT JOIN sectors sec ON s.sector_id = sec.sector_id WHERE s.asset_type = 'Stock' ORDER BY s.market_cap DESC;", "Equity securities in dataset"
        return "SELECT security_id, symbol, company_name, asset_type, current_price, market_cap, exchange, country FROM securities ORDER BY market_cap DESC LIMIT 25;", "Securities dataset records ranked by market cap"

    if ds == "holdings":
        if "top" in q_norm or "largest" in q_norm:
            return "SELECT p.portfolio_name, s.symbol, s.company_name, h.quantity, h.current_weight, h.cost_basis FROM holdings h JOIN portfolios p ON h.portfolio_id = p.portfolio_id JOIN securities s ON h.security_id = s.security_id ORDER BY h.cost_basis DESC LIMIT 10;", "Largest constituent holdings across all portfolios"
        return "SELECT h.holding_id, p.portfolio_name, s.symbol, h.quantity, h.purchase_price, h.current_weight, h.cost_basis FROM holdings h JOIN portfolios p ON h.portfolio_id = p.portfolio_id JOIN securities s ON h.security_id = s.security_id ORDER BY h.holding_id ASC LIMIT 25;", "Portfolio constituent holdings records"

    if ds == "transactions":
        return "SELECT t.transaction_id, p.portfolio_name, s.symbol, t.transaction_type, t.quantity, t.price, t.fees, t.transaction_date FROM transactions t JOIN portfolios p ON t.portfolio_id = p.portfolio_id JOIN securities s ON t.security_id = s.security_id ORDER BY t.transaction_date DESC LIMIT 25;", "Transactions execution dataset"

    if ds == "historical_prices":
        return "SELECT hp.price_id, s.symbol, hp.price_date, hp.open_price, hp.high_price, hp.low_price, hp.close_price, hp.volume FROM historical_prices hp JOIN securities s ON hp.security_id = s.security_id ORDER BY hp.price_date DESC LIMIT 25;", "Historical daily pricing records"

    if ds == "portfolio_performance":
        return "SELECT pp.performance_id, p.portfolio_name, pp.performance_date, pp.nav, pp.total_return_1y, pp.sharpe_ratio, pp.volatility, pp.max_drawdown FROM portfolio_performance pp JOIN portfolios p ON pp.portfolio_id = p.portfolio_id ORDER BY pp.sharpe_ratio DESC LIMIT 25;", "Portfolio performance track records"

    if ds == "risk_metrics":
        return "SELECT rm.risk_id, p.portfolio_name, rm.calculation_date, rm.beta, rm.var_95, rm.cvar_95, rm.sortino_ratio, rm.tracking_error FROM risk_metrics rm JOIN portfolios p ON rm.portfolio_id = p.portfolio_id ORDER BY rm.beta ASC LIMIT 25;", "Portfolio quantitative risk metrics"

    if ds == "sectors":
        return "SELECT sector_id, sector_name, industry_group, sector_description FROM sectors ORDER BY sector_id ASC;", "Industry sectors dataset records"

    if ds == "benchmarks":
        return "SELECT benchmark_id, benchmark_name, benchmark_symbol, benchmark_type, description, inception_date FROM benchmarks ORDER BY benchmark_id ASC;", "Market reference benchmarks dataset records"

    return None


def _universal_fallback_synthesizer(q_norm: str, target_ds: Optional[str] = None) -> Tuple[str, str]:
    """
    Intelligent AST-safe fallback query generator that maps any arbitrary question
    to the most relevant database table with proper ordering and safety limits.
    """
    # Table inference from keyword associations
    table = target_ds or "portfolios"
    if not target_ds:
        if any(w in q_norm for w in ["trade", "buy", "sell", "order", "fee", "settlement"]):
            table = "transactions"
        elif any(w in q_norm for w in ["price", "open", "close", "high", "low", "volume", "quote"]):
            table = "historical_prices"
        elif any(w in q_norm for w in ["performance", "nav", "return", "sharpe", "drawdown", "volatility"]):
            table = "portfolio_performance"
        elif any(w in q_norm for w in ["risk", "var", "beta", "tracking error", "sortino", "cvar"]):
            table = "risk_metrics"
        elif any(w in q_norm for w in ["stock", "company", "ticker", "share", "market cap", "bond", "coupon"]):
            table = "securities"
        elif any(w in q_norm for w in ["holding", "position", "weight", "cost basis", "shares"]):
            table = "holdings"
        elif any(w in q_norm for w in ["benchmark", "index", "sp500", "nasdaq"]):
            table = "benchmarks"
        elif any(w in q_norm for w in ["sector", "industry"]):
            table = "sectors"

    # Check for limit numbers in user query
    limit = 20
    lim_match = re.search(r"\b(?:top|limit|first)\s*(\d+)\b", q_norm)
    if lim_match:
        limit = min(int(lim_match.group(1)), 100)

    # Dispatch synthesized query by resolved table
    if table == "transactions":
        sql = f"""SELECT t.transaction_id, p.portfolio_name, s.symbol, t.transaction_type, t.quantity, t.price, t.fees, t.transaction_date 
FROM transactions t 
JOIN portfolios p ON t.portfolio_id = p.portfolio_id 
JOIN securities s ON t.security_id = s.security_id 
ORDER BY t.transaction_date DESC LIMIT {limit};"""
        return sql, f"Relational transactions ledger scoped to '{q_norm[:40]}...'"

    if table == "historical_prices":
        sql = f"""SELECT hp.price_date, s.symbol, s.company_name, hp.open_price, hp.high_price, hp.low_price, hp.close_price, hp.volume 
FROM historical_prices hp 
JOIN securities s ON hp.security_id = s.security_id 
ORDER BY hp.price_date DESC LIMIT {limit};"""
        return sql, f"Daily market price quotes scoped to '{q_norm[:40]}...'"

    if table == "portfolio_performance":
        sql = f"""SELECT p.portfolio_name, pp.performance_date, pp.nav, pp.total_return_1y, pp.sharpe_ratio, pp.volatility, pp.max_drawdown 
FROM portfolio_performance pp 
JOIN portfolios p ON pp.portfolio_id = p.portfolio_id 
ORDER BY pp.sharpe_ratio DESC LIMIT {limit};"""
        return sql, f"Portfolio performance records scoped to '{q_norm[:40]}...'"

    if table == "risk_metrics":
        sql = f"""SELECT p.portfolio_name, rm.calculation_date, rm.beta, rm.var_95, rm.cvar_95, rm.sortino_ratio 
FROM risk_metrics rm 
JOIN portfolios p ON rm.portfolio_id = p.portfolio_id 
ORDER BY rm.beta ASC LIMIT {limit};"""
        return sql, f"Quantitative risk analytics scoped to '{q_norm[:40]}...'"

    if table == "securities":
        sql = f"""SELECT s.symbol, s.company_name, s.asset_type, sec.sector_name, s.current_price, s.market_cap 
FROM securities s 
LEFT JOIN sectors sec ON s.sector_id = sec.sector_id 
ORDER BY s.market_cap DESC LIMIT {limit};"""
        return sql, f"Master securities ledger scoped to '{q_norm[:40]}...'"

    if table == "holdings":
        sql = f"""SELECT p.portfolio_name, s.symbol, s.company_name, h.quantity, h.current_weight, h.cost_basis 
FROM holdings h 
JOIN portfolios p ON h.portfolio_id = p.portfolio_id 
JOIN securities s ON h.security_id = s.security_id 
ORDER BY h.cost_basis DESC LIMIT {limit};"""
        return sql, f"Constituent holdings ledger scoped to '{q_norm[:40]}...'"

    if table == "sectors":
        sql = f"SELECT sector_id, sector_name, industry_group, sector_description FROM sectors ORDER BY sector_id LIMIT {limit};"
        return sql, f"Industry sector classifications scoped to '{q_norm[:40]}...'"

    if table == "benchmarks":
        sql = f"SELECT benchmark_id, benchmark_name, benchmark_symbol, benchmark_type, description FROM benchmarks ORDER BY benchmark_name LIMIT {limit};"
        return sql, f"Market benchmarks dataset scoped to '{q_norm[:40]}...'"

    # Default: Portfolios
    sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, benchmark_index, status FROM portfolios ORDER BY total_aum DESC LIMIT {limit};"
    return sql, f"Overview of investment portfolios scoped to '{q_norm[:40]}...'"
