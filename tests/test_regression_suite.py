"""
Automated Pytest Suite for Expanded Regression Benchmark Questions.
Verifies company name resolution, ticker resolution, aggregations,
transactions filtering, sector percentage, comparisons, and risk analytics.
"""

import json
from pathlib import Path
import pytest
from agent.portfolio_agent import PortfolioAgent

BASE_DIR = Path(__file__).resolve().parent.parent
REGRESSION_PATH = BASE_DIR / "evaluation" / "regression_questions.json"


@pytest.fixture(scope="module")
def agent():
    agent_inst = PortfolioAgent()
    yield agent_inst
    agent_inst.close()


def load_regression_questions():
    with open(REGRESSION_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


@pytest.mark.parametrize("q_item", load_regression_questions(), ids=[q["id"] for q in load_regression_questions()])
def test_regression_question(agent, q_item):
    """Executes each regression question and verifies tool routing and analytical output."""
    qtext = q_item["question"]
    expected_tool = q_item.get("expected_tool")
    expected_count = q_item.get("expected_record_count")
    expected_sym = q_item.get("expected_symbol")
    expected_pct = q_item.get("expected_target_percentage")

    res = agent.answer_question(qtext)
    assert res is not None, f"Query '{qtext}' returned None"
    assert res.get("direct_answer"), f"Query '{qtext}' has empty direct_answer"

    # 1. Routing check
    if expected_tool:
        assert res["selected_tool"] == expected_tool, (
            f"Query '{qtext}': expected tool '{expected_tool}', got '{res['selected_tool']}'"
        )

    # 2. Record count check
    if expected_count is not None:
        evidence = res.get("evidence")
        if isinstance(evidence, list):
            assert len(evidence) == expected_count, (
                f"Query '{qtext}': expected {expected_count} records, got {len(evidence)}"
            )

    # 3. Symbol fidelity check
    if expected_sym:
        raw_sql = res.get("generated_sql", "")
        evidence = res.get("evidence", [])
        # Symbol should either be in SQL or in evidence rows
        sym_found = (
            expected_sym in raw_sql
            or any(r.get("symbol") == expected_sym for r in evidence if isinstance(r, dict))
        )
        assert sym_found, f"Query '{qtext}': expected symbol '{expected_sym}' in output or SQL"

    # 4. Target percentage check
    if expected_pct is not None:
        ans_text = res.get("direct_answer", "")
        pct_str = f"{expected_pct:.1f}%"
        assert pct_str in ans_text or f"{expected_pct}%" in ans_text, (
            f"Query '{qtext}': expected {expected_pct}% in direct answer, got '{ans_text}'"
        )
