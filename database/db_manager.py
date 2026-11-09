"""
Database Manager for Portfolio Analytics Agent.
Handles schema initialization, CSV data ingestion, integrity verification,
and connection management for SQLite.
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Path definitions
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCHEMA_PATH = BASE_DIR / "database" / "database_schema.sql"
DEFAULT_DB_PATH = BASE_DIR / "portfolio_database.db"

# Ordered list of tables to respect foreign key constraints
TABLE_DEPENDENCY_ORDER = [
    "sectors",
    "benchmarks",
    "portfolios",
    "securities",
    "holdings",
    "transactions",
    "historical_prices",
    "portfolio_performance",
    "risk_metrics",
]

EXPECTED_ROW_COUNTS = {
    "sectors": 10,
    "benchmarks": 13,
    "portfolios": 13,
    "securities": 30,
    "holdings": 95,
    "transactions": 24,
    "historical_prices": 330,
    "portfolio_performance": 44,
    "risk_metrics": 44,
}


class DatabaseManager:
    """Manages SQLite database lifecycle, schema, ingestion, and querying."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path) if db_path else str(DEFAULT_DB_PATH)
        self.is_memory = self.db_path == ":memory:"

    def _create_raw_connection(self) -> sqlite3.Connection:
        """Create a raw configured SQLite connection without auto-initialization checks."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a configured SQLite connection. Auto-initializes if empty or missing."""
        conn = self._create_raw_connection()

        # Auto-initialize if database was just created or lacks the core portfolios table
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolios';")
        if cursor.fetchone() is None:
            conn.close()
            self.initialize_database()
            conn = self._create_raw_connection()
        return conn

    def initialize_database(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Initializes schema and ingests CSV data.
        Returns a summary of loaded tables and row counts.
        """
        if force_reload and not self.is_memory and os.path.exists(self.db_path):
            os.remove(self.db_path)

        conn = self._create_raw_connection()
        cursor = conn.cursor()

        # Check if already initialized
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolios';")
        already_initialized = cursor.fetchone() is not None

        if already_initialized and not force_reload:
            summary = self.verify_database(conn)
            conn.close()
            return summary

        # 1. Apply schema
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Database schema file not found at {SCHEMA_PATH}")

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
            cursor.executescript(schema_sql)

        # 2. Ingest CSV files in dependency order
        loaded_counts = {}
        for table_name in TABLE_DEPENDENCY_ORDER:
            csv_path = DATA_DIR / f"{table_name}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Data file not found for table {table_name}: {csv_path}")

            df = pd.read_csv(csv_path)

            # Convert date columns to ISO string if needed
            for col in df.columns:
                if "date" in col.lower() and df[col].dtype == "object":
                    df[col] = df[col].astype(str)

            df.to_sql(table_name, conn, if_exists="append", index=False)
            loaded_counts[table_name] = len(df)

        conn.commit()
        summary = self.verify_database(conn)
        conn.close()
        return summary

    def verify_database(self, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """
        Verifies row counts and foreign key integrity.
        """
        should_close = False
        if conn is None:
            conn = self.get_connection()
            should_close = True

        cursor = conn.cursor()
        actual_counts = {}
        all_passed = True

        for table, expected_count in EXPECTED_ROW_COUNTS.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                actual_counts[table] = {
                    "count": count,
                    "expected": expected_count,
                    "status": "PASS" if count == expected_count else "FAIL",
                }
                if count != expected_count:
                    all_passed = False
            except Exception as e:
                actual_counts[table] = {"count": 0, "expected": expected_count, "error": str(e), "status": "ERROR"}
                all_passed = False

        # Run foreign key check
        cursor.execute("PRAGMA foreign_key_check;")
        fk_violations = cursor.fetchall()

        if should_close:
            conn.close()

        return {
            "total_tables": len(actual_counts),
            "total_records": sum(v.get("count", 0) for v in actual_counts.values()),
            "all_counts_match": all_passed,
            "fk_violations": len(fk_violations),
            "table_details": actual_counts,
        }

    def execute_query(self, sql: str, params: Tuple = ()) -> Tuple[List[Dict[str, Any]], List[str], float]:
        """
        Executes a SQL query safely and returns (rows as dicts, column names, execution_time_ms).
        Enforces read-only SQLite authorizer callback at the engine level.
        """
        from validation.sql_validator import sqlite_read_only_authorizer

        start_time = time.perf_counter()
        conn = self.get_connection()
        try:
            conn.set_authorizer(sqlite_read_only_authorizer)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            raw_rows = cursor.fetchall()
            rows = [dict(row) for row in raw_rows]
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return rows, columns, round(elapsed_ms, 2)
        finally:
            conn.close()

    def get_schema_summary(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Returns a dictionary mapping each table to its list of columns and types.
        Useful for dynamic LLM context prompting.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        schema_dict = {}
        for table in TABLE_DEPENDENCY_ORDER:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [{"name": row["name"], "type": row["type"], "pk": bool(row["pk"])} for row in cursor.fetchall()]
            schema_dict[table] = columns
        conn.close()
        return schema_dict


# Convenience singleton
default_db_manager = DatabaseManager()

if __name__ == "__main__":
    print("Initializing and verifying database...")
    manager = DatabaseManager()
    summary = manager.initialize_database(force_reload=True)
    print(f"Total tables: {summary['total_tables']}")
    print(f"Total records: {summary['total_records']} (Expected: 604)")
    print(f"All counts match: {summary['all_counts_match']}")
    print(f"Foreign key violations: {summary['fk_violations']}")
    for tbl, info in summary["table_details"].items():
        print(f"  - {tbl:22s}: {info['count']:3d} rows [{info['status']}]")
