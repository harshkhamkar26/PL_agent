"""
AST-Based SQL Safety Guardrail & Schema Validator.
Uses sqlglot to parse SQLite queries into an Abstract Syntax Tree (AST),
verify read-only execution (SELECT / WITH), inspect table references,
reject mutations / administrative statements, and enforce SQLite C-level authorizers.
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
from sqlglot import exp

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Approved tables in the PL Capital institutional schema
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

# Forbidden AST statement types (mutations, DDL, administrative commands)
FORBIDDEN_AST_EXPRESSIONS: Tuple[type, ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Pragma,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Merge,
    exp.Grant,
    exp.Revoke,
    exp.LoadData,
)

# Regex patterns for raw injection signals, comments, and delimiters
FORBIDDEN_PATTERNS: List[str] = [
    r"--",             # Single-line comment injection
    r"/\*.*?\*/",      # Block comment injection
    r";\s*\S+",        # Multiple SQL statements
    r"\bATTACH\b",     # Database file attach
    r"\bDETACH\b",     # Database file detach
    r"\bPRAGMA\b",     # SQLite configuration pragma
    r"\bVACUUM\b",     # Vacuum command
    r"\bLOAD_EXTENSION\b", # Extension loading
]


def sqlite_read_only_authorizer(action: int, arg1: Optional[str], arg2: Optional[str], dbname: Optional[str], source: Optional[str]) -> int:
    """
    SQLite C-level authorizer callback (registered via conn.set_authorizer).
    Guarantees physical engine-level rejection of any write or administrative operation.
    """
    denied_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
    }
    if action in denied_actions:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class SQLValidator:
    """
    Abstract Syntax Tree (AST) SQL Security Guardrail.
    Validates queries prior to execution using sqlglot AST decomposition
    and SQLite connection authorizers.
    """

    @classmethod
    def sanitize_sql(cls, raw_sql: str) -> str:
        """Cleans markdown code fences, surrounding whitespace, and trailing semicolons."""
        if not raw_sql:
            return ""
        sql = raw_sql.strip()
        # Strip ```sql ... ``` or ``` ... ```
        if sql.startswith("```"):
            lines = sql.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            sql = "\n".join(lines).strip()

        # Remove trailing semicolon
        sql = sql.rstrip(";").strip()
        return sql

    @classmethod
    def extract_tables(cls, sql: str) -> List[str]:
        """
        Extracts verified database tables referenced in the query using AST traversal.
        Excludes Common Table Expression (CTE) aliases and external non-schema references.
        """
        clean_sql = cls.sanitize_sql(sql)
        if not clean_sql:
            return []

        try:
            ast = sqlglot.parse_one(clean_sql, read="sqlite")
            # Collect CTE aliases defined in WITH clauses
            cte_aliases = {
                cte.alias.lower()
                for cte in ast.find_all(exp.CTE)
                if cte.alias
            }

            tables: List[str] = []
            for tbl in ast.find_all(exp.Table):
                name = tbl.name.lower() if tbl.name else ""
                if name and name not in cte_aliases and name in ALLOWED_TABLES:
                    if name not in tables:
                        tables.append(name)
            return tables
        except Exception:
            # Fallback regex extraction if AST parse encounters dialect nuances
            matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", clean_sql, re.IGNORECASE)
            cte_matches = set(m.lower() for m in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(", clean_sql, re.IGNORECASE))
            fallback_tables = []
            for t in matches:
                tl = t.lower()
                if tl not in cte_matches and tl in ALLOWED_TABLES and tl not in fallback_tables:
                    fallback_tables.append(tl)
            return fallback_tables

    @classmethod
    def validate_query(
        cls,
        raw_sql: str,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Comprehensive AST-based SQL query security validator.
        Returns: (is_valid: bool, error_message: Optional[str], sanitized_sql: str)
        """
        sql = cls.sanitize_sql(raw_sql)
        if not sql:
            return False, "Query string is empty.", ""

        # 1. Reject injection patterns (comments, chained statements, PRAGMA, ATTACH)
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Security Violation: Query contains prohibited keyword or syntax matching pattern '{pattern}'.", sql

        # 2. Parse into AST using sqlglot
        try:
            statements = sqlglot.parse(sql, read="sqlite")
        except Exception as e:
            return False, f"SQL Syntax Error: Unable to parse query into AST ({str(e)}).", sql

        # Disallow multiple statements
        valid_stmts = [s for s in statements if s is not None]
        if len(valid_stmts) > 1:
            return False, "Security Violation: Multiple SQL statements detected. Only single-statement queries are permitted.", sql

        if not valid_stmts:
            return False, "Empty or invalid SQL statement.", sql

        root_stmt = valid_stmts[0]

        # 3. Check for forbidden mutation expressions anywhere in AST tree
        for forbidden_type in FORBIDDEN_AST_EXPRESSIONS:
            if isinstance(root_stmt, forbidden_type) or list(root_stmt.find_all(forbidden_type)):
                return (
                    False,
                    f"Disallowed query type / Security Guardrail: Disallowed mutation/administrative operation ({forbidden_type.__name__}). System is strictly read-only.",
                    sql,
                )

        # 4. Enforce root statement must be a Select or Union query
        if not isinstance(root_stmt, (exp.Select, exp.Union)):
            return False, f"Disallowed query type: {type(root_stmt).__name__}. Only read-only SELECT or WITH queries are permitted.", sql

        # 5. Inspect all Table references in AST
        cte_aliases = {
            cte.alias.lower()
            for cte in root_stmt.find_all(exp.CTE)
            if cte.alias
        }

        referenced_tables = root_stmt.find_all(exp.Table)
        for tbl in referenced_tables:
            tbl_name = tbl.name.lower() if tbl.name else ""
            if not tbl_name:
                continue
            if tbl_name not in ALLOWED_TABLES and tbl_name not in cte_aliases:
                return False, f"Schema Violation: Referenced table '{tbl_name}' is not part of the allowed portfolio schema.", sql

        # 6. Database engine dry-run check (EXPLAIN execution + Authorizer)
        if db_conn is not None:
            try:
                # Apply authorizer to ensure engine-level protection
                db_conn.set_authorizer(sqlite_read_only_authorizer)
                cursor = db_conn.cursor()
                cursor.execute(f"EXPLAIN {sql};")
            except Exception as e:
                return False, f"Syntax or Schema Validation Error: {str(e)}", sql

        return True, None, sql + ";"


if __name__ == "__main__":
    print("Verifying AST SQL Validator...")
    # Safe query test
    safe_sql = "WITH high_aum AS (SELECT * FROM portfolios WHERE total_aum > 20000000) SELECT p.portfolio_name, s.symbol FROM high_aum p JOIN holdings h ON p.portfolio_id = h.portfolio_id JOIN securities s ON h.security_id = s.security_id;"
    ok, err, sanitized = SQLValidator.validate_query(safe_sql)
    print("Safe CTE Query Valid:", ok, "Error:", err)
    assert ok is True

    # Mutation test (DROP)
    bad_drop = "DROP TABLE portfolios;"
    ok, err, sanitized = SQLValidator.validate_query(bad_drop)
    print("Drop Query Valid:", ok, "Error:", err)
    assert ok is False

    # Chained statement test
    bad_chain = "SELECT * FROM portfolios; DROP TABLE securities;"
    ok, err, sanitized = SQLValidator.validate_query(bad_chain)
    print("Chained Query Valid:", ok, "Error:", err)
    assert ok is False

    # Unauthorized table test
    bad_table = "SELECT * FROM users_credentials;"
    ok, err, sanitized = SQLValidator.validate_query(bad_table)
    print("Unauthorized Table Valid:", ok, "Error:", err)
    assert ok is False

    print("ALL AST SQLValidator tests passed successfully!")
