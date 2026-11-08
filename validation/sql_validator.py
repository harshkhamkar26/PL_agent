"""
Advanced SQL Safety Guardrail & Schema Validator.
Ensures queries are strictly read-only, injection-free, and validated
against table and column definitions in the SQLite schema.
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Approved tables in the PL Capital database
ALLOWED_TABLES: Set[str] = {
    "sectors",
    "securities",
    "benchmarks",
    "portfolios",
    "holdings",
    "transactions",
    "historical_prices",
    "portfolio_performance",
    "risk_metrics",
}

# Forbidden keywords indicating mutation, DDL, or administrative commands
FORBIDDEN_KEYWORDS: List[str] = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bTRUNCATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
    r"\bVACUUM\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"--",               # Single-line comment injection
    r"/\*.*?\*/",        # Block comments
    r";\s*\S+",          # Multiple statements
]


class SQLValidator:
    """Validates SQL safety, structure, and schema compliance."""

    @classmethod
    def sanitize_sql(cls, raw_sql: str) -> str:
        """Cleans markdown backticks, surrounding whitespace, and trailing semicolons."""
        sql = raw_sql.strip()
        # Strip ```sql ... ``` or ``` ... ```
        if sql.startswith("```"):
            lines = sql.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            sql = "\n".join(lines).strip()

        # Remove trailing semicolon for uniform handling
        sql = sql.rstrip(";").strip()
        return sql

    @classmethod
    def extract_tables(cls, sql: str) -> List[str]:
        """Extracts referenced tables from FROM and JOIN clauses."""
        # Find all table references
        matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
        # Find CTE names defined in WITH ... AS (
        cte_matches = set(m.lower() for m in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(", sql, re.IGNORECASE))
        tables = []
        for tbl in matches:
            tbl_clean = tbl.lower()
            if tbl_clean not in cte_matches and tbl_clean in ALLOWED_TABLES:
                if tbl_clean not in tables:
                    tables.append(tbl_clean)
        return tables

    @classmethod
    def validate_query(cls, raw_sql: str, db_conn: Optional[sqlite3.Connection] = None) -> Tuple[bool, Optional[str], str]:
        """
        Validates whether a SQL query is safe and compliant to execute.
        Returns: (is_valid: bool, error_message: Optional[str], sanitized_sql: str)
        """
        sql = cls.sanitize_sql(raw_sql)
        if not sql:
            return False, "Query string is empty.", ""

        upper_sql = sql.upper()

        # 1. Must start with SELECT or WITH
        if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
            return False, "Disallowed query type: Query must start with SELECT or WITH (read-only enforcement).", sql

        # 2. Check forbidden mutation patterns
        for pattern in FORBIDDEN_KEYWORDS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Security Violation: Query contains prohibited keyword or syntax matching pattern '{pattern}'.", sql

        # 3. Check table references: ensure no unrecognized external tables are referenced
        raw_tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
        cte_names = set(m.lower() for m in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(", sql, re.IGNORECASE))

        for tbl in raw_tables:
            tbl_lower = tbl.lower()
            if tbl_lower not in ALLOWED_TABLES and tbl_lower not in cte_names:
                return False, f"Schema Violation: Referenced table '{tbl}' is not part of the allowed portfolio schema.", sql

        # 4. Optional: Dry-run EXPLAIN check on SQLite connection to catch syntax errors
        if db_conn is not None:
            try:
                cursor = db_conn.cursor()
                cursor.execute(f"EXPLAIN {sql};")
            except Exception as e:
                return False, f"Syntax or Schema Validation Error: {str(e)}", sql

        return True, None, sql + ";"


if __name__ == "__main__":
    print("Testing Enhanced SQLValidator...")
    safe_q = "SELECT portfolio_name FROM portfolios WHERE status = 'Active';"
    valid, err, s = SQLValidator.validate_query(safe_q)
    print("Safe query valid:", valid, "SQL:", s)
    assert valid is True

    unsafe_q = "DROP TABLE portfolios;"
    valid, err, s = SQLValidator.validate_query(unsafe_q)
    print("Drop table valid:", valid, "Error:", err)
    assert valid is False

    tables = SQLValidator.extract_tables("SELECT p.portfolio_name, s.symbol FROM portfolios p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id")
    print("Tables extracted:", tables)
    assert "portfolios" in tables and "holdings" in tables and "securities" in tables

    print("All enhanced SQLValidator checks passed!")
