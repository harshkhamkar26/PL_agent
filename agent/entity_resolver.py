"""
Financial Entity Resolver for PL Capital Portfolio Analytics Agent.
Resolves natural-language mentions of companies, ticker symbols, aliases,
portfolio names, sectors, and asset classes to grounded database entities.
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class SecurityEntity:
    security_id: int
    symbol: str
    company_name: str
    asset_type: str
    sector_id: Optional[int]
    sector_name: Optional[str] = None
    market_cap: Optional[float] = None
    current_price: Optional[float] = None


@dataclass
class PortfolioEntity:
    portfolio_id: int
    portfolio_name: str
    target_risk_level: str
    total_aum: float
    strategy_type: str
    status: str


@dataclass
class SectorEntity:
    sector_id: int
    sector_name: str
    industry_group: Optional[str] = None


class EntityResolver:
    """
    Robust Financial Entity Resolution Engine.
    Grounds user natural language tokens against SQLite master tables:
    - Resolves company names to ticker symbols (e.g. "Apple" -> AAPL, "Microsoft" -> MSFT).
    - Resolves ticker symbols to company names (e.g. "AAPL" -> Apple Inc.).
    - Resolves common aliases (e.g. "Google" -> GOOGL, "Nvidia" -> NVDA, "Amazon" -> AMZN).
    - Resolves portfolio names, sectors, benchmarks, and asset types.
    - Resolves with case-insensitivity and unambiguous prefix/substring matching.
    """

    # Static synonym / alias dictionary grounded in securities master list
    COMPANY_ALIASES: Dict[str, str] = {
        "apple": "AAPL",
        "apple inc": "AAPL",
        "apple computer": "AAPL",
        "microsoft": "MSFT",
        "microsoft corp": "MSFT",
        "microsoft corporation": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "alphabet inc": "GOOGL",
        "amazon": "AMZN",
        "amazon.com": "AMZN",
        "tesla": "TSLA",
        "tesla motors": "TSLA",
        "meta": "META",
        "meta platforms": "META",
        "facebook": "META",
        "nvidia": "NVDA",
        "nvidia corp": "NVDA",
        "nvidia corporation": "NVDA",
        "jpmorgan": "JPM",
        "jp morgan": "JPM",
        "jpmorgan chase": "JPM",
        "chase": "JPM",
        "johnson & johnson": "JNJ",
        "johnson and johnson": "JNJ",
        "j&j": "JNJ",
        "visa": "V",
        "visa inc": "V",
        "procter & gamble": "PG",
        "procter and gamble": "PG",
        "p&g": "PG",
        "unitedhealth": "UNH",
        "unitedhealth group": "UNH",
        "united health": "UNH",
        "home depot": "HD",
        "the home depot": "HD",
        "mastercard": "MA",
        "pfizer": "PFE",
        "coca-cola": "KO",
        "coca cola": "KO",
        "coke": "KO",
        "abbvie": "ABBV",
        "broadcom": "AVGO",
        "salesforce": "CRM",
        "salesforce inc": "CRM",
        "exxon": "XOM",
        "exxonmobil": "XOM",
        "exxon mobil": "XOM",
        "walmart": "WMT",
        "wal-mart": "WMT",
        "eli lilly": "LLY",
        "lilly": "LLY",
        "bank of america": "BAC",
        "bofa": "BAC",
        "oracle": "ORCL",
        "oracle corp": "ORCL",
        "chevron": "CVX",
        "chevron corp": "CVX",
        # Bond aliases
        "10y treasury": "UST-10Y",
        "10-year treasury": "UST-10Y",
        "10 year treasury": "UST-10Y",
        "ust 10y": "UST-10Y",
        "5y treasury": "UST-5Y",
        "5-year treasury": "UST-5Y",
        "2y treasury": "UST-2Y",
        "2-year treasury": "UST-2Y",
        "aaa bond": "CORP-AAA-5Y",
        "aaa corporate": "CORP-AAA-5Y",
        "corporate bond 5y": "CORP-AAA-5Y",
        "a-rated bond": "CORP-A-10Y",
        "a rated corporate": "CORP-A-10Y",
        "corporate bond 10y": "CORP-A-10Y",
    }

    SECTOR_ALIASES: Dict[str, str] = {
        "tech": "Technology",
        "technology": "Technology",
        "information technology": "Technology",
        "it": "Technology",
        "healthcare": "Healthcare",
        "health care": "Healthcare",
        "health": "Healthcare",
        "pharma": "Healthcare",
        "financials": "Financials",
        "financial": "Financials",
        "finance": "Financials",
        "banks": "Financials",
        "banking": "Financials",
        "consumer discretionary": "Consumer Discretionary",
        "discretionary": "Consumer Discretionary",
        "consumer staples": "Consumer Staples",
        "staples": "Consumer Staples",
        "energy": "Energy",
        "oil": "Energy",
        "oil & gas": "Energy",
        "automotive": "Automotive",
        "auto": "Automotive",
        "industrials": "Industrials",
        "industrial": "Industrials",
        "real estate": "Real Estate",
        "reit": "Real Estate",
        "utilities": "Utilities",
        "utility": "Utilities",
    }

    PORTFOLIO_ALIASES: Dict[str, str] = {
        "growth equity": "Growth Equity Fund",
        "growth equity fund": "Growth Equity Fund",
        "conservative income": "Conservative Income Fund",
        "conservative income fund": "Conservative Income Fund",
        "tech innovation": "Tech Innovation Fund",
        "tech innovation fund": "Tech Innovation Fund",
        "balanced": "Balanced Portfolio",
        "balanced portfolio": "Balanced Portfolio",
        "esg": "ESG Sustainable Fund",
        "esg sustainable": "ESG Sustainable Fund",
        "esg sustainable fund": "ESG Sustainable Fund",
        "small cap": "Small Cap Value Fund",
        "small cap value": "Small Cap Value Fund",
        "small cap value fund": "Small Cap Value Fund",
        "international equity": "International Equity Fund",
        "international equity fund": "International Equity Fund",
        "fixed income plus": "Fixed Income Plus",
        "fixed income": "Fixed Income Plus",
        "dividend aristocrats": "Dividend Aristocrats Fund",
        "dividend aristocrats fund": "Dividend Aristocrats Fund",
        "emerging markets": "Emerging Markets Fund",
        "emerging markets fund": "Emerging Markets Fund",
        "total stock market": "Total Stock Market Index Fund",
        "total stock market index fund": "Total Stock Market Index Fund",
        "total stock market fund": "Total Stock Market Index Fund",
        "total bond market": "Total Bond Market Index Fund",
        "total bond market index fund": "Total Bond Market Index Fund",
        "total international": "Total International Index Fund",
        "total international index fund": "Total International Index Fund",
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(BASE_DIR / "portfolio_database.db")
        self.securities_by_symbol: Dict[str, SecurityEntity] = {}
        self.securities_by_id: Dict[int, SecurityEntity] = {}
        self.portfolios_by_id: Dict[int, PortfolioEntity] = {}
        self.portfolios_by_name: Dict[str, PortfolioEntity] = {}
        self.sectors_by_id: Dict[int, SectorEntity] = {}
        self.sectors_by_name: Dict[str, SectorEntity] = {}
        self._load_master_data()

    def _load_master_data(self):
        """Loads master reference data from SQLite database into memory caches."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 1. Sectors
            cur.execute("SELECT sector_id, sector_name, industry_group FROM sectors")
            for r in cur.fetchall():
                sec = SectorEntity(
                    sector_id=r["sector_id"],
                    sector_name=r["sector_name"],
                    industry_group=r["industry_group"],
                )
                self.sectors_by_id[sec.sector_id] = sec
                self.sectors_by_name[sec.sector_name.lower()] = sec

            # 2. Securities
            cur.execute("""
                SELECT s.security_id, s.symbol, s.company_name, s.asset_type, 
                       s.sector_id, sec.sector_name, s.market_cap, s.current_price
                FROM securities s
                LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
            """)
            for r in cur.fetchall():
                sec = SecurityEntity(
                    security_id=r["security_id"],
                    symbol=r["symbol"],
                    company_name=r["company_name"],
                    asset_type=r["asset_type"],
                    sector_id=r["sector_id"],
                    sector_name=r["sector_name"],
                    market_cap=r["market_cap"],
                    current_price=r["current_price"],
                )
                self.securities_by_symbol[sec.symbol.upper()] = sec
                self.securities_by_id[sec.security_id] = sec

            # 3. Portfolios
            cur.execute("SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, status FROM portfolios")
            for r in cur.fetchall():
                port = PortfolioEntity(
                    portfolio_id=r["portfolio_id"],
                    portfolio_name=r["portfolio_name"],
                    target_risk_level=r["target_risk_level"],
                    total_aum=r["total_aum"],
                    strategy_type=r["strategy_type"],
                    status=r["status"],
                )
                self.portfolios_by_id[port.portfolio_id] = port
                self.portfolios_by_name[port.portfolio_name.lower()] = port

            conn.close()
        except Exception:
            # Fallback if DB not loaded yet
            pass

    def resolve_security(self, text: str) -> Optional[SecurityEntity]:
        """
        Resolves a security entity from a natural language text or symbol.
        Checks:
        1. Exact ticker match (e.g. 'AAPL', 'MSFT', 'UST-10Y')
        2. Known company alias dictionary (e.g. 'Apple' -> AAPL)
        3. Company name exact/prefix/substring match in database
        """
        if not text:
            return None

        clean = text.strip()
        upper = clean.upper()
        lower = clean.lower()

        # 1. Exact ticker match
        if upper in self.securities_by_symbol:
            return self.securities_by_symbol[upper]

        # 2. Check alias dictionary
        if lower in self.COMPANY_ALIASES:
            target_symbol = self.COMPANY_ALIASES[lower]
            if target_symbol in self.securities_by_symbol:
                return self.securities_by_symbol[target_symbol]

        # Check multi-word phrase inside text against alias dictionary
        for alias_key, target_symbol in sorted(self.COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
            pattern = rf"\b{re.escape(alias_key)}\b"
            if re.search(pattern, lower):
                if target_symbol in self.securities_by_symbol:
                    return self.securities_by_symbol[target_symbol]

        # 3. Search securities database by company_name
        # Exact lowercase match
        for sec in self.securities_by_symbol.values():
            if sec.company_name.lower() == lower:
                return sec

        # Word boundary match on company name (e.g. "Apple" inside "Apple Inc.")
        for sec in self.securities_by_symbol.values():
            # Extract first word or core stem of company name
            core_name = sec.company_name.split()[0].lower()
            if len(core_name) >= 4 and re.search(rf"\b{re.escape(core_name)}\b", lower):
                return sec

        # Ticker word boundary match inside question
        for symbol, sec in self.securities_by_symbol.items():
            if re.search(rf"\b{re.escape(symbol.lower())}\b", lower):
                return sec

        return None

    def resolve_portfolio(self, text: str) -> Optional[PortfolioEntity]:
        """
        Resolves a portfolio entity from a question or name string.
        """
        if not text:
            return None

        lower = text.strip().lower()

        # 1. Exact name match
        if lower in self.portfolios_by_name:
            return self.portfolios_by_name[lower]

        # 2. Alias match
        for alias_key, canonical_name in sorted(self.PORTFOLIO_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias_key in lower:
                canonical_lower = canonical_name.lower()
                if canonical_lower in self.portfolios_by_name:
                    return self.portfolios_by_name[canonical_lower]

        # 3. Word boundary substring match on database portfolio names
        for name_lower, port in self.portfolios_by_name.items():
            if name_lower in lower:
                return port

        return None

    def resolve_sector(self, text: str) -> Optional[SectorEntity]:
        """
        Resolves a sector entity from text.
        """
        if not text:
            return None

        lower = text.strip().lower()

        # 1. Exact match
        if lower in self.sectors_by_name:
            return self.sectors_by_name[lower]

        # 2. Alias match
        for alias_key, canonical_name in sorted(self.SECTOR_ALIASES.items(), key=lambda x: -len(x[0])):
            pattern = rf"\b{re.escape(alias_key)}\b"
            if re.search(pattern, lower):
                canonical_lower = canonical_name.lower()
                if canonical_lower in self.sectors_by_name:
                    return self.sectors_by_name[canonical_lower]

        return None

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extracts all recognized financial entities from a user question.
        Returns a dictionary with resolved securities, portfolios, sectors, and asset classes.
        """
        res_security = self.resolve_security(text)
        res_portfolio = self.resolve_portfolio(text)
        res_sector = self.resolve_sector(text)

        # Asset class inference
        lower = text.lower()
        asset_class = None
        if re.search(r"\b(bond|bonds|fixed income|treasury|debt)\b", lower):
            asset_class = "Bond"
        elif re.search(r"\b(stock|stocks|equity|equities|shares)\b", lower):
            asset_class = "Stock"

        return {
            "security": res_security,
            "portfolio": res_portfolio,
            "sector": res_sector,
            "asset_class": asset_class,
        }


# Global singleton instance
default_entity_resolver = EntityResolver()
