"""Unit tests for Database Manager and Schema integrity."""
import pytest
from database.db_manager import DatabaseManager, TABLE_DEPENDENCY_ORDER, EXPECTED_ROW_COUNTS

def test_database_initialization():
    manager = DatabaseManager()
    summary = manager.verify_database()
    assert summary["total_tables"] == 9
    assert summary["fk_violations"] == 0
    assert summary["all_counts_match"] is True

def test_table_row_counts():
    manager = DatabaseManager()
    conn = manager.get_connection()
    cursor = conn.cursor()
    for table, expected in EXPECTED_ROW_COUNTS.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        assert count == expected, f"Table {table} row count {count} != expected {expected}"
    conn.close()
