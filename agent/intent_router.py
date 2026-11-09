"""
Advanced Intent Router and Entity Extractor for Portfolio Analytics Agent.
Classifies incoming questions to select the optimal analytical tool:
SQL Query Tool, Exposure Calculator, Hybrid Analytics Engine, or Portfolio Comparison.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Tool Constants
TOOL_SQL = "sql_query_tool"
TOOL_EXPOSURE = "exposure_calculator"
TOOL_HYBRID = "hybrid_analytics"
TOOL_COMPARE = "portfolio_comparison"
TOOL_CHAT = "conversational_assistant"


class IntentRouter:
    """Routes user queries to the appropriate analytical tool."""

    @classmethod
    def route_query(cls, question: str) -> Tuple[str, Dict[str, Any], str]:
        """
        Determines tool and parameters.
        Returns: (tool_name, parameters, routing_rationale)
        """
        q_norm = question.strip().lower()

        # 0. Check for Conversational / Agent Identity / Wellbeing / Explanations
        chat_triggers = [
            r"\b(who\s+are\s+you|what\s+are\s+you|what\s+is\s+your\s+name|tell\s+me\s+about\s+yourself|introduce\s+yourself)\b",
            r"\b(wellbeing|well-being|how\s+are\s+you|how\s+is\s+your|how\s+do\s+you\s+feel|are\s+you\s+okay|system\s+status|health\s+check|how\s+are\s+things)\b",
            r"\b(what\s+can\s+you\s+do|capabilities|what\s+tools\s+do\s+you\s+have|how\s+do\s+you\s+work|what\s+are\s+your\s+features)\b",
            r"\b(why\s+exclude\s+bonds|how\s+do\s+you\s+handle\s+bonds|how\s+do\s+you\s+partition\s+debt|how\s+does\s+ast\s+work|what\s+is\s+ast)\b",
            r"\b(what\s+is\s+hhi|what\s+is\s+sharpe|what\s+is\s+sortino|what\s+is\s+beta|what\s+is\s+var|explain\s+hhi)\b",
            r"\b(what\s+is\s+pl\s+capital|about\s+pl\s+capital|tell\s+me\s+about\s+pl\s+capital|who\s+is\s+prabhudas)\b",
            r"^(hi|hello|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening|help|help\s+me|whoami)$",
        ]
        if any(re.search(pat, q_norm) for pat in chat_triggers):
            return (
                TOOL_CHAT,
                {"question": question},
                "Conversational inquiry regarding agent identity, system wellbeing, architecture, or financial definitions.",
            )

        # 1. Check for Portfolio Comparison Intent
        # Triggers: "compare ... and ...", "comparison between ... and ..."
        if "compare" in q_norm or "comparison" in q_norm:
            p1, p2 = cls._extract_comparison_targets(question)
            if p1 and p2:
                return (
                    TOOL_COMPARE,
                    {"portfolio_1": p1, "portfolio_2": p2},
                    f"Side-by-side quantitative sector exposure and active spread comparison between '{p1}' and '{p2}'.",
                )

        # 2. Check for Hybrid Intent: Cohort / risk filter combined with exposure across portfolios
        has_risk_cohort = bool(re.search(r"(high|medium|low)[-\s]+risk", q_norm) or "target risk" in q_norm)
        has_status_cohort = bool("active" in q_norm or "passive" in q_norm)
        has_top_aum = bool("top" in q_norm and "aum" in q_norm)
        has_exposure_or_sec = bool(re.search(r"(sector|exposure)", q_norm))
        has_multi = bool(re.search(r"\b(all|each|every|both|portfolios)\b", q_norm))

        if (has_risk_cohort or has_status_cohort or has_top_aum) and has_exposure_or_sec and has_multi:
            if has_risk_cohort:
                risk_match = re.search(r"(high|medium|low)", q_norm)
                risk = risk_match.group(1).capitalize() if risk_match else "High"
                return (
                    TOOL_HYBRID,
                    {"workflow_type": "risk", "risk_level": risk},
                    f"Multi-step analysis combining portfolio risk cohort ('{risk}') with sector exposure aggregations.",
                )
            elif has_top_aum:
                limit_match = re.search(r"top\s+(\d+)", q_norm)
                limit = int(limit_match.group(1)) if limit_match else 5
                return (
                    TOOL_HYBRID,
                    {"workflow_type": "top_aum", "limit": limit},
                    f"Multi-step analysis querying top {limit} portfolios by total AUM and aggregating sector exposures.",
                )
            elif has_status_cohort:
                status = "Active" if "active" in q_norm else "Passive"
                return (
                    TOOL_HYBRID,
                    {"workflow_type": "status", "status": status},
                    f"Multi-step analysis combining status cohort ('{status}') with sector exposure aggregations.",
                )

        # 3. Check for Exposure Calculator Intent
        exposure_triggers = [
            r"sector exposure",
            r"exposure breakdown",
            r"calculate.*exposure",
            r"exposure for",
            r"sector breakdown",
            r"exposures for",
        ]
        is_exposure = any(re.search(pat, q_norm) for pat in exposure_triggers)

        # Distinguish cross-table SQL aggregation from single-portfolio exposure
        if is_exposure and not re.search(r"(average.*price|securities in the technology sector)", q_norm):
            portfolio_target = cls._extract_portfolio_target(question)
            return (
                TOOL_EXPOSURE,
                {"portfolio_name": portfolio_target},
                f"Dedicated equity sector exposure calculation for '{portfolio_target}', excluding fixed-income holdings.",
            )

        # 4. Default to SQL Query Tool (Relational questions, rankings, aggregations, counts)
        return (
            TOOL_SQL,
            {"question": question},
            "Relational database query involving counts, filters, joins, or multi-table aggregations.",
        )

    @classmethod
    def _extract_portfolio_target(cls, question: str) -> str:
        """Extracts the portfolio name target from an exposure question."""
        q_clean = question.strip()

        # Check known portfolio names explicitly
        known = [
            "Tech Innovation Fund",
            "International Equity Fund",
            "Growth Equity Fund",
            "Conservative Income Fund",
            "Balanced Portfolio",
            "Total Stock Market Index Fund",
            "Emerging Markets Fund",
            "Small Cap Value Fund",
            "Dividend Aristocrats Fund",
            "ESG Sustainable Fund",
            "Fixed Income Plus",
            "Total Bond Market Index Fund",
            "Total International Index Fund",
        ]
        for name in known:
            if name.lower() in q_clean.lower():
                return name

        # Patterns like: "exposures for the <Target>?" or "breakdown for <Target>"
        match = re.search(r"(?:for|of)\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?:\?|$|\.|\bsector\b|\bexposure\b)", q_clean, re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            target = re.sub(r"\b(sector|exposures|exposure|breakdown)\b", "", target, flags=re.IGNORECASE).strip()
            if target:
                return target

        if "tech" in q_clean.lower():
            return "Tech Innovation Fund"
        if "international" in q_clean.lower():
            return "International Equity Fund"

        return q_clean

    @classmethod
    def _extract_comparison_targets(cls, question: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts two portfolio names from comparison queries."""
        # Pattern: compare <Target 1> and <Target 2>
        match = re.search(r"compare\s+(?:the\s+)?(?:sector\s+exposures\s+of\s+)?([A-Za-z0-9\s\-]+?)\s+(?:and|with|to)\s+([A-Za-z0-9\s\-]+?)(?:\?|$|\.)", question, re.IGNORECASE)
        if match:
            p1 = match.group(1).strip()
            p2 = match.group(2).strip()
            # Clean common words
            p1 = re.sub(r"\b(sector|exposures|breakdown|the)\b", "", p1, flags=re.IGNORECASE).strip()
            p2 = re.sub(r"\b(sector|exposures|breakdown|the)\b", "", p2, flags=re.IGNORECASE).strip()
            return p1, p2
        return None, None


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Testing Enhanced IntentRouter...")
    test_suite = [
        ("How many portfolios do we have in total?", TOOL_SQL),
        ("What are the sector exposures for the Tech Innovation Fund?", TOOL_EXPOSURE),
        ("Calculate the sector exposure breakdown for international equity", TOOL_EXPOSURE),
        ("Show sector exposure and total AUM for all high-risk portfolios", TOOL_HYBRID),
        ("Compare the sector exposures of Tech Innovation Fund and International Equity Fund", TOOL_COMPARE),
    ]

    for q, expected in test_suite:
        tool, params, rat = IntentRouter.route_query(q)
        print(f"Query: '{q}'\n  -> Tool: {tool} [{params}]")
        assert tool == expected, f"Routing failed for {q}: expected {expected}, got {tool}"

    print("\nPASS: All IntentRouter tests verified successfully!")
