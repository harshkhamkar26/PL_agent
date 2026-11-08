"""
Deep Integration & Orchestration Test Suite for PortfolioAgent (Phase 4).
Validates multi-intent routing, hybrid analytics execution, portfolio comparison,
response grounding, and telemetry logging.
"""

import pytest
from agent.portfolio_agent import PortfolioAgent
from agent.intent_router import TOOL_COMPARE, TOOL_EXPOSURE, TOOL_HYBRID, TOOL_SQL


@pytest.fixture
def agent():
    a = PortfolioAgent()
    yield a
    a.close()


# --- 1. Multi-Intent Routing Coverage ---

def test_sql_routing_variations(agent):
    queries = [
        "How many portfolios do we have in total?",
        "What are the names of all active portfolios?",
        "Which securities are in the Technology sector?",
        "What is the average current price of securities in each sector?",
    ]
    for q in queries:
        res = agent.answer_question(q)
        assert res["selected_tool"] == TOOL_SQL
        assert res["direct_answer"] != ""
        assert res["telemetry"]["tool"] == TOOL_SQL


def test_exposure_routing_variations(agent):
    queries = [
        "What are the sector exposures for the Tech Innovation Fund?",
        "Calculate the sector exposure breakdown for international equity",
        "What is the sector breakdown of Growth Equity Fund?",
    ]
    for q in queries:
        res = agent.answer_question(q)
        assert res["selected_tool"] == TOOL_EXPOSURE
        assert res["telemetry"]["tool"] == TOOL_EXPOSURE
        assert "Equity Sector Exposure" in res["direct_answer"]


def test_hybrid_risk_routing(agent):
    res = agent.answer_question("Show sector exposure and total AUM for all high-risk portfolios")
    assert res["selected_tool"] == TOOL_HYBRID
    assert "85,000,000" in res["direct_answer"]
    assert len(res["evidence"]) == 4


def test_hybrid_top_aum_routing(agent):
    res = agent.answer_question("Show top 4 portfolios by total AUM and their sector exposure")
    assert res["selected_tool"] == TOOL_HYBRID
    assert res["selected_tool"] == TOOL_HYBRID
    assert len(res["evidence"]) == 4


def test_portfolio_comparison_routing(agent):
    res = agent.answer_question("Compare the sector exposures of Tech Innovation Fund and International Equity Fund")
    assert res["selected_tool"] == TOOL_COMPARE
    assert "Sector exposure comparison" in res["direct_answer"]
    assert len(res["evidence"]) == 4  # 4 sectors compared


# --- 2. 4-Part Evidence Grounding Structure ---

def test_evidence_grounding_structure(agent):
    res = agent.answer_question("How many portfolios do we have in total?")
    assert "direct_answer" in res
    assert "evidence" in res
    assert "methodology" in res
    assert "telemetry" in res
    assert "formatted_markdown" in res
    assert "13" in res["direct_answer"]


# --- 3. Session Query History Tracking ---

def test_session_history_tracking(agent):
    agent.clear_history()
    assert len(agent.get_history()) == 0

    agent.answer_question("How many portfolios do we have in total?")
    agent.answer_question("What are the sector exposures for the Tech Innovation Fund?")
    agent.answer_question("Show sector exposure and total AUM for all high-risk portfolios")

    history = agent.get_history()
    assert len(history) == 3
    assert history[0]["tool"] == TOOL_SQL
    assert history[1]["tool"] == TOOL_EXPOSURE
    assert history[2]["tool"] == TOOL_HYBRID

    agent.clear_history()
    assert len(agent.get_history()) == 0


# --- 4. Error Handling & Resilience ---

def test_invalid_portfolio_exposure_error_handling(agent):
    res = agent.answer_question("What are the sector exposures for NonExistentFundXYZ?")
    assert res["selected_tool"] == TOOL_EXPOSURE
    assert "Could not resolve portfolio" in res["direct_answer"]
