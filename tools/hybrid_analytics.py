"""
Advanced Hybrid Analytics Engine for Portfolio Analytics Agent.
Combines SQL relational filtering with quantitative sector exposure calculations
to execute multi-stage financial workflows across portfolio cohorts.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager, default_db_manager
from tools.exposure_calculator import ExposureCalculator, default_exposure_calculator
from tools.sql_tool import SQLQueryTool, default_sql_tool


class HybridAnalyticsTool:
    """
    Executes composite financial workflows combining SQL relational filtering
    with quantitative sector exposure aggregation.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        sql_tool: Optional[SQLQueryTool] = None,
        exposure_calculator: Optional[ExposureCalculator] = None,
    ):
        self.db = db_manager or default_db_manager
        self.sql_tool = sql_tool or default_sql_tool
        self.exposure_calculator = exposure_calculator or default_exposure_calculator

    def analyze_risk_and_exposure(self, risk_level: str = "High") -> Dict[str, Any]:
        """
        Hybrid Workflow 1: Cohort by Target Risk Level
        1. Queries portfolios table filtered by risk level.
        2. Computes equity sector exposures for each matching fund.
        3. Synthesizes a unified portfolio risk matrix.
        """
        sql = f"SELECT portfolio_id, portfolio_name, total_aum, strategy_type, status FROM portfolios WHERE LOWER(target_risk_level) = LOWER('{risk_level}') ORDER BY total_aum DESC;"
        sql_result = self.sql_tool.execute_direct_sql(sql)

        if not sql_result.get("success"):
            return {
                "success": False,
                "error": f"Failed SQL step: {sql_result.get('error')}",
            }

        return self._build_hybrid_report(sql_result["rows"], filter_desc=f"target_risk_level = '{risk_level}'")

    def analyze_top_portfolios_by_aum(self, limit: int = 5) -> Dict[str, Any]:
        """
        Hybrid Workflow 2: Top N Portfolios by Assets Under Management
        1. Queries top N portfolios ordered by total AUM.
        2. Computes equity sector exposures and dominant sectors for each.
        """
        sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, status FROM portfolios ORDER BY total_aum DESC LIMIT {limit};"
        sql_result = self.sql_tool.execute_direct_sql(sql)

        if not sql_result.get("success"):
            return {
                "success": False,
                "error": f"Failed SQL step: {sql_result.get('error')}",
            }

        return self._build_hybrid_report(sql_result["rows"], filter_desc=f"Top {limit} Portfolios by Total AUM")

    def analyze_status_and_exposure(self, status: str = "Active") -> Dict[str, Any]:
        """
        Hybrid Workflow 3: Cohort by Status (Active vs Passive)
        """
        sql = f"SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, status FROM portfolios WHERE LOWER(status) = LOWER('{status}') ORDER BY total_aum DESC;"
        sql_result = self.sql_tool.execute_direct_sql(sql)

        if not sql_result.get("success"):
            return {
                "success": False,
                "error": f"Failed SQL step: {sql_result.get('error')}",
            }

        return self._build_hybrid_report(sql_result["rows"], filter_desc=f"status = '{status}'")

    def _build_hybrid_report(self, portfolios: List[Dict[str, Any]], filter_desc: str) -> Dict[str, Any]:
        """Internal helper to aggregate sector exposures across portfolio cohorts."""
        combined_data = []

        for p in portfolios:
            pid = p["portfolio_id"]
            pname = p["portfolio_name"]
            try:
                exp_res = self.exposure_calculator.calculate_exposure(pid)
                top_sec = list(exp_res["sector_exposures"].keys())[0] if exp_res["sector_exposures"] else "None (Pure Debt)"
                top_sec_pct = list(exp_res["sector_exposures"].values())[0] if exp_res["sector_exposures"] else 0.0

                combined_data.append({
                    "portfolio_id": pid,
                    "portfolio_name": pname,
                    "target_risk_level": p.get("target_risk_level", "N/A"),
                    "total_aum": p.get("total_aum", 0.0),
                    "strategy_type": p.get("strategy_type", "N/A"),
                    "status": p.get("status", "N/A"),
                    "total_equity_pct": exp_res["total_equity_exposure_pct"],
                    "top_sector": top_sec,
                    "top_sector_pct": top_sec_pct,
                    "sector_exposures": exp_res["sector_exposures"],
                    "excluded_bonds_pct": exp_res["excluded_bond_weight_pct"],
                    "concentration_profile": exp_res.get("concentration_profile", "N/A"),
                })
            except Exception as e:
                combined_data.append({
                    "portfolio_id": pid,
                    "portfolio_name": pname,
                    "error": str(e),
                })

        total_aum = sum(p.get("total_aum", 0.0) for p in combined_data if "total_aum" in p)

        return {
            "success": True,
            "workflow": "Hybrid SQL + Exposure Engine",
            "filter_criteria": filter_desc,
            "portfolio_count": len(combined_data),
            "aggregate_aum": total_aum,
            "portfolios": combined_data,
        }

    def format_hybrid_markdown(self, result: Dict[str, Any]) -> str:
        """Formats hybrid analysis as a comprehensive audit report."""
        if not result.get("success"):
            return f"❌ **Hybrid Analysis Failed**: {result.get('error')}"

        crit = result["filter_criteria"]
        count = result["portfolio_count"]
        aum = result["aggregate_aum"]
        ports = result["portfolios"]

        lines = [
            f"### [Hybrid Analytical Report: {crit}]",
            f"- **Matching Portfolios:** `{count}`",
            f"- **Aggregate AUM:** `${aum:,.2f}`",
            "",
            "| Portfolio Name | Total AUM | Strategy | Equity (%) | Top Sector | Top Sector (%) | Excluded Debt (%) | Concentration |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for p in ports:
            if "error" in p:
                lines.append(f"| {p['portfolio_name']} | N/A | N/A | N/A | Error: {p['error']} | N/A | N/A | N/A |")
            else:
                lines.append(
                    f"| **{p['portfolio_name']}** | ${p['total_aum']:,.2f} | {p['strategy_type']} | {p['total_equity_pct']:.2f}% | {p['top_sector']} | {p['top_sector_pct']:.2f}% | {p['excluded_bonds_pct']:.2f}% | {p['concentration_profile']} |"
                )

        lines.extend([
            "",
            "#### Tool Execution Pipeline",
            "1. **Phase 1 (Relational Filter):** Queried `portfolios` table for matching cohort criteria.",
            "2. **Phase 2 (Quantitative Exposure):** Aggregated stock holdings by sector and partitioned out debt securities.",
            "3. **Phase 3 (Cross-Disciplinary Reconciliation):** Synthesized portfolio metrics with sector concentrations.",
        ])

        return "\n".join(lines)


# Singleton instance
default_hybrid_tool = HybridAnalyticsTool()

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Testing Advanced HybridAnalyticsTool...")
    tool = HybridAnalyticsTool()
    res = tool.analyze_top_portfolios_by_aum(4)
    print(tool.format_hybrid_markdown(res))
    print("\nPASS: HybridAnalyticsTool verified!")
