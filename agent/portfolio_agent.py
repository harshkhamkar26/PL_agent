"""
Portfolio Analytics Agent.
Main agent class coordinating intent routing, analytical tools,
session history logging, and evidence-grounded response generation.
"""

import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.intent_router import (
    TOOL_COMPARE,
    TOOL_EXPOSURE,
    TOOL_HYBRID,
    TOOL_SQL,
    IntentRouter,
)
from agent.response_formatter import ResponseFormatter
from database.db_manager import DatabaseManager, default_db_manager
from intelligence.gemini_client import GeminiClient, default_gemini_client
from tools.exposure_calculator import ExposureCalculator
from tools.hybrid_analytics import HybridAnalyticsTool
from tools.sql_tool import SQLQueryTool


class PortfolioAgent:
    """
    Intelligent Portfolio Analytics Agent for PL Capital.
    Understands financial natural language queries and routes them
    to validated SQL, Exposure Calculator, Portfolio Comparison,
    or Hybrid Analytics engines with full auditability and session history.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.db_manager = DatabaseManager(db_path) if db_path else default_db_manager
        # Backward compatibility with assignment README template
        self.db_connection = sqlite3.connect(self.db_manager.db_path)

        self.gemini_client = GeminiClient(api_key=gemini_api_key) if gemini_api_key else default_gemini_client
        self.sql_tool = SQLQueryTool(db_manager=self.db_manager, gemini_client=self.gemini_client)
        self.exposure_calculator = ExposureCalculator(db_manager=self.db_manager)
        self.hybrid_tool = HybridAnalyticsTool(
            db_manager=self.db_manager,
            sql_tool=self.sql_tool,
            exposure_calculator=self.exposure_calculator,
        )
        self.query_history: List[Dict[str, Any]] = []

    def answer_question(self, question: str) -> Dict[str, Any]:
        """
        Processes a natural language question, selects the appropriate tool,
        and generates an evidence-grounded response.
        """
        start_time = time.perf_counter()

        # Step 1: Tool Routing & Entity Extraction
        selected_tool, params, rationale = IntentRouter.route_query(question)

        raw_output = {}
        formatted_response = {}

        # Step 2: Tool Execution
        if selected_tool == TOOL_COMPARE:
            p1 = params.get("portfolio_1")
            p2 = params.get("portfolio_2")
            try:
                raw_output = self.exposure_calculator.compare_portfolios(p1, p2)
                formatted_response = ResponseFormatter.format_comparison_response(raw_output)
            except Exception as e:
                raw_output = {"success": False, "error": str(e)}
                formatted_response = {
                    "direct_answer": f"Error comparing '{p1}' and '{p2}': {str(e)}",
                    "evidence": [],
                    "methodology": "Failed during cross-portfolio comparison.",
                    "telemetry": {"tool": TOOL_COMPARE, "status": "ERROR"},
                    "formatted_markdown": f"❌ **Error:** Could not compare portfolios: {str(e)}",
                }

        elif selected_tool == TOOL_EXPOSURE:
            pname = params.get("portfolio_name", question)
            try:
                raw_output = self.exposure_calculator.calculate_exposure(pname)
                formatted_response = ResponseFormatter.format_exposure_response(raw_output)
            except Exception as e:
                raw_output = {"success": False, "error": str(e)}
                formatted_response = {
                    "direct_answer": f"Error calculating exposure for '{pname}': {str(e)}",
                    "evidence": {},
                    "methodology": "Failed during portfolio exposure lookup.",
                    "telemetry": {"tool": TOOL_EXPOSURE, "status": "ERROR"},
                    "formatted_markdown": f"❌ **Error:** Could not calculate exposure: {str(e)}",
                }

        elif selected_tool == TOOL_HYBRID:
            wf = params.get("workflow_type", "risk")
            if wf == "top_aum":
                limit = params.get("limit", 5)
                raw_output = self.hybrid_tool.analyze_top_portfolios_by_aum(limit)
            elif wf == "status":
                status = params.get("status", "Active")
                raw_output = self.hybrid_tool.analyze_status_and_exposure(status)
            else:
                risk = params.get("risk_level", "High")
                raw_output = self.hybrid_tool.analyze_risk_and_exposure(risk)
            formatted_response = ResponseFormatter.format_hybrid_response(raw_output)

        else:  # Default: TOOL_SQL
            raw_output = self.sql_tool.execute_text2sql(question)
            formatted_response = ResponseFormatter.format_sql_response(raw_output)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        response_payload = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "selected_tool": selected_tool,
            "routing_rationale": rationale,
            "direct_answer": formatted_response.get("direct_answer", ""),
            "evidence": formatted_response.get("evidence"),
            "methodology": formatted_response.get("methodology", ""),
            "telemetry": formatted_response.get("telemetry", {}),
            "formatted_markdown": formatted_response.get("formatted_markdown", ""),
            "raw_tool_output": raw_output,
            "total_latency_ms": elapsed_ms,
        }

        # Track history
        self.query_history.append({
            "timestamp": response_payload["timestamp"],
            "question": question,
            "tool": selected_tool,
            "latency_ms": elapsed_ms,
            "direct_answer": response_payload["direct_answer"][:80],
        })

        return response_payload

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the chronological list of queries and execution telemetry."""
        return list(self.query_history)

    def clear_history(self):
        """Clears query session history."""
        self.query_history.clear()

    def close(self):
        """Close internal connections."""
        if self.db_connection:
            self.db_connection.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Testing PortfolioAgent on multi-tool workflow...")
    agent = PortfolioAgent()

    test_queries = [
        "How many portfolios do we have in total?",
        "What are the sector exposures for the Tech Innovation Fund?",
        "Show sector exposure and total AUM for all high-risk portfolios",
        "Compare the sector exposures of Tech Innovation Fund and International Equity Fund",
    ]

    for q in test_queries:
        print("\n" + "=" * 60)
        print(f"QUERY: {q}")
        res = agent.answer_question(q)
        print(f"TOOL SELECTED: {res['selected_tool']} ({res['total_latency_ms']} ms)")
        print(f"DIRECT ANSWER: {res['direct_answer']}")

    print("\n" + "=" * 60)
    print(f"Session Query History: {len(agent.get_history())} queries logged.")
    for h in agent.get_history():
        print(f"  [{h['tool']}] ({h['latency_ms']} ms): {h['question']}")

    agent.close()
    print("\nPortfolioAgent tests completed!")
