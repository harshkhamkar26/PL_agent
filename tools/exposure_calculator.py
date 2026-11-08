"""
Advanced Quantitative Exposure Calculator Tool for Portfolio Analytics Agent.
Calculates equity sector exposures, computes quantitative concentration indices (HHI, Neff),
enforces strict fixed-income (bond) exclusion, provides side-by-side portfolio comparisons,
and audits weight allocations with transparent reconciliation.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager, default_db_manager
from validation.data_reconciler import DataReconciler


class ExposureCalculator:
    """
    Quantitative Exposure Calculator Engine for PL Capital.
    Strictly isolates equities from fixed-income debt, measures sector concentration,
    and performs cross-portfolio allocation comparisons.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or default_db_manager
        self.reconciler = DataReconciler(self.db)

    def resolve_portfolio(self, identifier: Union[str, int]) -> Tuple[int, str]:
        """
        Resolves a portfolio ID or natural language name to (portfolio_id, portfolio_name).
        Supports exact match, case-insensitive match, and fuzzy substring matching.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 1. Numeric ID check
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
            pid = int(identifier)
            cursor.execute("SELECT portfolio_id, portfolio_name FROM portfolios WHERE portfolio_id = ?", (pid,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row["portfolio_id"], row["portfolio_name"]
            raise ValueError(f"Portfolio with ID {pid} not found in database.")

        # 2. String search
        name_clean = str(identifier).strip()
        cursor.execute("SELECT portfolio_id, portfolio_name FROM portfolios")
        all_portfolios = [(r["portfolio_id"], r["portfolio_name"]) for r in cursor.fetchall()]
        conn.close()

        # Exact match (case-insensitive)
        for pid, pname in all_portfolios:
            if pname.lower() == name_clean.lower():
                return pid, pname

        # Substring / contains match
        for pid, pname in all_portfolios:
            if name_clean.lower() in pname.lower() or pname.lower() in name_clean.lower():
                return pid, pname

        # Fuzzy word overlap match
        query_words = set(re.findall(r"\w+", name_clean.lower()))
        filtered_words = [w for w in query_words if w not in {"the", "fund", "portfolio", "for", "in", "of", "and", "sector", "exposure", "breakdown"}]

        best_match = None
        best_score = 0

        for pid, pname in all_portfolios:
            pname_lower = pname.lower()
            matched_words = sum(1 for w in filtered_words if w in pname_lower)
            if matched_words > best_score:
                best_score = matched_words
                best_match = (pid, pname)

        if best_match and best_score >= 1:
            return best_match

        available = ", ".join([f"'{p[1]}' (ID: {p[0]})" for p in all_portfolios])
        raise ValueError(f"Could not resolve portfolio '{identifier}'. Available portfolios: {available}")

    def calculate_exposure(self, identifier: Union[str, int]) -> Dict[str, Any]:
        """
        Calculates equity sector exposures, concentration indices (HHI, Neff),
        and weight reconciliation metrics.
        """
        portfolio_id, portfolio_name = self.resolve_portfolio(identifier)

        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Query sector aggregations for equities only (asset_type = 'Stock')
        cursor.execute(
            """
            SELECT 
                sec.sector_name,
                SUM(h.current_weight) as total_weight,
                COUNT(h.holding_id) as holding_count,
                SUM(h.cost_basis) as sector_cost_basis,
                SUM(h.quantity * s.current_price) as sector_market_value,
                GROUP_CONCAT(s.symbol || ' (' || ROUND(h.current_weight * 100, 1) || '%)', ', ') as constituent_symbols
            FROM holdings h
            JOIN securities s ON h.security_id = s.security_id
            JOIN sectors sec ON s.sector_id = sec.sector_id
            WHERE h.portfolio_id = ? AND s.asset_type = 'Stock'
            GROUP BY sec.sector_name
            ORDER BY total_weight DESC
            """,
            (portfolio_id,),
        )
        sector_rows = cursor.fetchall()

        sector_exposures: Dict[str, float] = {}
        sector_details: List[Dict[str, Any]] = []
        total_equity_pct = 0.0
        total_equity_mkt_val = 0.0

        for row in sector_rows:
            pct = round(row["total_weight"] * 100, 2)
            sector_name = row["sector_name"]
            mkt_val = row["sector_market_value"] or 0.0
            sector_exposures[sector_name] = pct
            total_equity_pct += pct
            total_equity_mkt_val += mkt_val

            sector_details.append({
                "sector_name": sector_name,
                "exposure_pct": pct,
                "holdings_count": row["holding_count"],
                "cost_basis": row["sector_cost_basis"],
                "market_value": round(mkt_val, 2),
                "constituents": row["constituent_symbols"],
            })

        # Query excluded fixed income (bonds: asset_type = 'Bond')
        cursor.execute(
            """
            SELECT 
                s.symbol,
                s.company_name,
                h.current_weight,
                h.cost_basis,
                (h.quantity * s.current_price) as market_value
            FROM holdings h
            JOIN securities s ON h.security_id = s.security_id
            WHERE h.portfolio_id = ? AND s.asset_type = 'Bond'
            ORDER BY h.current_weight DESC
            """,
            (portfolio_id,),
        )
        excluded_bonds = [
            {
                "symbol": r["symbol"],
                "name": r["company_name"],
                "weight_pct": round(r["current_weight"] * 100, 2),
                "cost_basis": r["cost_basis"],
                "market_value": round(r["market_value"] or 0.0, 2),
            }
            for r in cursor.fetchall()
        ]
        conn.close()

        bond_weight_pct = round(sum(b["weight_pct"] for b in excluded_bonds), 2)
        total_allocated_pct = round(total_equity_pct + bond_weight_pct, 2)
        unallocated_pct = round(max(0.0, 100.0 - total_allocated_pct), 2)

        # Quantitative concentration indices: Herfindahl-Hirschman Index (HHI)
        # HHI = sum((weight / total_equity_weight)^2)
        if total_equity_pct > 0:
            hhi = sum((sec["exposure_pct"] / total_equity_pct) ** 2 for sec in sector_details)
            n_eff = round(1.0 / hhi, 2) if hhi > 0 else 0.0
            if hhi > 0.50:
                concentration_class = "Highly Concentrated"
            elif hhi >= 0.25:
                concentration_class = "Moderately Concentrated"
            else:
                concentration_class = "Well Diversified"
        else:
            hhi = 0.0
            n_eff = 0.0
            concentration_class = "Pure Fixed-Income (Zero Equity)"

        # Construct institutional audit trail
        audit_notes: List[str] = [
            f"Calculated across {len(sector_details)} equity sector(s) using fractional weight summation.",
            "Bonds excluded from equity sector exposure per institutional asset allocation guidelines.",
        ]

        if excluded_bonds:
            audit_notes.append(
                f"Multi-Asset Allocation: {len(excluded_bonds)} fixed-income holding(s) excluded totaling {bond_weight_pct:.2f}% portfolio weight."
            )

        if unallocated_pct > 0.01:
            audit_notes.append(
                f"Cash Buffer Audit: Total recorded allocation is {total_allocated_pct:.2f}%. Remaining {unallocated_pct:.2f}% represents cash buffer or tracking reserve (preserved without artificial normalization)."
            )

        if total_equity_pct == 0.0:
            audit_notes.append(
                "Notice: 100% Fixed-Income portfolio. Equity sector exposure is 0.00%."
            )

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "sector_exposures": sector_exposures,
            "sector_details": sector_details,
            "total_equity_exposure_pct": round(total_equity_pct, 2),
            "excluded_bond_weight_pct": bond_weight_pct,
            "unallocated_cash_pct": unallocated_pct,
            "total_equity_market_value": round(total_equity_mkt_val, 2),
            "hhi_concentration": round(hhi, 4),
            "effective_sectors_count": n_eff,
            "concentration_profile": concentration_class,
            "excluded_bonds": excluded_bonds,
            "audit_notes": audit_notes,
        }

    def compare_portfolios(self, id1: Union[str, int], id2: Union[str, int]) -> Dict[str, Any]:
        """
        Performs side-by-side quantitative sector exposure comparison between two portfolios.
        Calculates active spread / overweight / underweight deltas.
        """
        res1 = self.calculate_exposure(id1)
        res2 = self.calculate_exposure(id2)

        all_sectors = sorted(list(set(res1["sector_exposures"].keys()).union(set(res2["sector_exposures"].keys()))))

        comparison_matrix = []
        for sec in all_sectors:
            w1 = res1["sector_exposures"].get(sec, 0.0)
            w2 = res2["sector_exposures"].get(sec, 0.0)
            delta = round(w1 - w2, 2)
            comparison_matrix.append({
                "sector": sec,
                "portfolio_1_pct": w1,
                "portfolio_2_pct": w2,
                "active_delta_pct": delta,
                "spread_status": f"{res1['portfolio_name']} Overweight (+{delta:.1f}%)" if delta > 0 else (f"{res2['portfolio_name']} Overweight (+{-delta:.1f}%)" if delta < 0 else "Equal Weight"),
            })

        return {
            "portfolio_1": {"id": res1["portfolio_id"], "name": res1["portfolio_name"], "equity_pct": res1["total_equity_exposure_pct"], "hhi": res1["hhi_concentration"]},
            "portfolio_2": {"id": res2["portfolio_id"], "name": res2["portfolio_name"], "equity_pct": res2["total_equity_exposure_pct"], "hhi": res2["hhi_concentration"]},
            "sectors_compared": len(all_sectors),
            "comparison_matrix": comparison_matrix,
        }

    def format_exposure_markdown(self, result: Dict[str, Any]) -> str:
        """Renders an institutional financial markdown audit card for exposure results."""
        pname = result["portfolio_name"]
        pid = result["portfolio_id"]
        exposures = result["sector_exposures"]
        equity_pct = result["total_equity_exposure_pct"]
        bond_pct = result["excluded_bond_weight_pct"]
        cash_pct = result["unallocated_cash_pct"]
        hhi = result.get("hhi_concentration", 0.0)
        n_eff = result.get("effective_sectors_count", 0.0)
        profile = result.get("concentration_profile", "N/A")

        lines = [
            f"### [Portfolio Exposure Analysis: {pname}]",
            f"**Direct Answer:** {pname} Equity Sector Exposure: {', '.join(f'{k}: {v:.1f}%' for k, v in exposures.items()) if exposures else '0.00% (Pure Fixed Income)'}",
            "",
            "#### Equity Sector Allocations",
            "| Sector | Weight (%) | Constituent Securities | Market Value ($) |",
            "| :--- | :--- | :--- | :--- |",
        ]

        if result["sector_details"]:
            for sec in result["sector_details"]:
                mkt = f"${sec['market_value']:,.2f}" if "market_value" in sec else "N/A"
                lines.append(f"| **{sec['sector_name']}** | {sec['exposure_pct']:.2f}% | {sec['constituents']} | {mkt} |")
        else:
            lines.append("| _No Equity Holdings_ | 0.00% | None | $0.00 |")

        lines.extend([
            "",
            "#### Financial Allocation Reconciliation",
            f"- **Total Equity Exposure:** `{equity_pct:.2f}%`",
            f"- **Excluded Fixed Income (Bonds):** `{bond_pct:.2f}%`",
            f"- **Unallocated Margin / Cash Buffer:** `{cash_pct:.2f}%`",
            f"- **Concentration Profile:** `{profile}` (HHI: `{hhi:.4f}`, Effective Sectors $N_{{eff}}$: `{n_eff}`)",
            "",
            "#### Methodology & Reconciliation Trail",
        ])

        for note in result["audit_notes"]:
            lines.append(f"- {note}")

        lines.extend([
            "",
            "#### Tool Telemetry",
            "- **Tool:** `Exposure Calculator Engine`",
            f"- **Target Portfolio:** `{pname}` (ID: `{pid}`)",
            f"- **Equity Holdings Aggregated:** `{len(result['sector_details'])} sectors`",
            f"- **Fixed Income Holdings Excluded:** `{len(result['excluded_bonds'])}`",
        ])

        return "\n".join(lines)


# Singleton instance
default_exposure_calculator = ExposureCalculator()

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Testing Advanced Exposure Calculator...")
    calc = ExposureCalculator()

    # Test Q9
    res9 = calc.calculate_exposure("Tech Innovation Fund")
    print("\n--- Q9 (Tech Innovation Fund) ---")
    print("Exposures:", res9["sector_exposures"])
    print(f"HHI: {res9['hhi_concentration']} | Neff: {res9['effective_sectors_count']} | Profile: {res9['concentration_profile']}")
    assert res9["sector_exposures"] == {"Technology": 100.0}

    # Test Q10
    res10 = calc.calculate_exposure("international equity")
    print("\n--- Q10 (International Equity Fund via fuzzy match) ---")
    print("Exposures:", res10["sector_exposures"])
    print(f"HHI: {res10['hhi_concentration']} | Neff: {res10['effective_sectors_count']} | Profile: {res10['concentration_profile']}")
    expected10 = {"Energy": 38.0, "Technology": 36.0, "Automotive": 15.0, "Consumer Staples": 11.0}
    assert res10["sector_exposures"] == expected10

    # Test Portfolio Comparison
    comp = calc.compare_portfolios("Tech Innovation Fund", "International Equity Fund")
    print("\n--- Portfolio Side-by-Side Comparison ---")
    for r in comp["comparison_matrix"]:
        print(f"  {r['sector']:22s}: {r['portfolio_1_pct']:5.1f}% vs {r['portfolio_2_pct']:5.1f}% (Delta: {r['active_delta_pct']:+5.1f}%) -> {r['spread_status']}")

    print("\nPASS: Advanced Exposure Calculator verified successfully!")
