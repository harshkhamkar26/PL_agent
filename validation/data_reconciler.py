"""
Financial Data Reconciler & Integrity Engine.
Audits portfolio weights, asset classifications, and sector mappings.
Detects cash buffers, unallocated weights, and bond exclusions.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager, default_db_manager


class DataReconciler:
    """Performs financial integrity verification across portfolios and holdings."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or default_db_manager

    def reconcile_portfolio(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Reconciles a single portfolio's holdings, weights, asset distribution,
        and unallocated margin.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Fetch portfolio info
        cursor.execute(
            "SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, status FROM portfolios WHERE portfolio_id = ?",
            (portfolio_id,),
        )
        p = cursor.fetchone()
        if not p:
            conn.close()
            raise ValueError(f"Portfolio ID {portfolio_id} not found.")

        portfolio_info = dict(p)

        # Fetch holdings breakdown
        cursor.execute(
            """
            SELECT 
                h.holding_id,
                h.security_id,
                s.symbol,
                s.company_name,
                s.asset_type,
                sec.sector_name,
                h.quantity,
                h.current_weight,
                h.cost_basis
            FROM holdings h
            JOIN securities s ON h.security_id = s.security_id
            LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
            WHERE h.portfolio_id = ?
            ORDER BY h.current_weight DESC
            """,
            (portfolio_id,),
        )
        holdings = [dict(r) for r in cursor.fetchall()]
        conn.close()

        total_weight = sum(h["current_weight"] for h in holdings)
        equity_holdings = [h for h in holdings if h["asset_type"] == "Stock"]
        bond_holdings = [h for h in holdings if h["asset_type"] == "Bond"]

        equity_weight = sum(h["current_weight"] for h in equity_holdings)
        bond_weight = sum(h["current_weight"] for h in bond_holdings)
        unallocated_weight = max(0.0, 1.0 - total_weight)

        # Flag any equity holding missing sector
        equity_missing_sector = [h for h in equity_holdings if not h["sector_name"]]

        status = "HEALTHY"
        notes = []
        if round(total_weight, 4) < 1.0:
            status = "UNALLOCATED_BUFFER_DETECTED"
            notes.append(
                f"Total weight is {round(total_weight * 100, 2)}%. Remaining {round(unallocated_weight * 100, 2)}% is unallocated cash buffer."
            )
        elif round(total_weight, 4) > 1.0:
            status = "OVERALLOCATED"
            notes.append(f"Total weight exceeds 100% ({round(total_weight * 100, 2)}%).")

        if bond_holdings:
            notes.append(
                f"{len(bond_holdings)} bond holding(s) present ({round(bond_weight * 100, 2)}% weight) - excluded from equity sector exposure per guidelines."
            )

        if equity_missing_sector:
            status = "INCOMPLETE_SECTOR_MAPPING"
            notes.append(f"{len(equity_missing_sector)} stock(s) lack sector mapping.")

        return {
            "portfolio": portfolio_info,
            "total_holdings_count": len(holdings),
            "equity_holdings_count": len(equity_holdings),
            "bond_holdings_count": len(bond_holdings),
            "total_weight_pct": round(total_weight * 100, 2),
            "equity_weight_pct": round(equity_weight * 100, 2),
            "bond_weight_pct": round(bond_weight * 100, 2),
            "unallocated_weight_pct": round(unallocated_weight * 100, 2),
            "reconciliation_status": status,
            "notes": notes,
            "holdings": holdings,
        }

    def audit_all_portfolios(self) -> List[Dict[str, Any]]:
        """Run reconciliation audit across all portfolios in the database."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT portfolio_id FROM portfolios ORDER BY portfolio_id")
        pids = [r[0] for r in cursor.fetchall()]
        conn.close()

        return [self.reconcile_portfolio(pid) for pid in pids]
