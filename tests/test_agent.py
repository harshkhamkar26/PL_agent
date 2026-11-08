"""Integration tests for PortfolioAgent and Intent Routing."""
import pytest
from agent.portfolio_agent import PortfolioAgent
from agent.intent_router import TOOL_SQL, TOOL_EXPOSURE, TOOL_HYBRID

@pytest.fixture
def agent():
    a = PortfolioAgent()
    yield a
    a.close()

def test_agent_routes_and_executes(agent):
    # SQL query test
    res_sql = agent.answer_question("How many portfolios do we have in total?")
    assert res_sql["selected_tool"] == TOOL_SQL
    assert "13" in res_sql["direct_answer"]

    # Exposure test
    res_exp = agent.answer_question("What are the sector exposures for the Tech Innovation Fund?")
    assert res_exp["selected_tool"] == TOOL_EXPOSURE
    assert "Technology" in res_exp["direct_answer"]

    # Hybrid test
    res_hyb = agent.answer_question("Show sector exposure and total AUM for all high-risk portfolios")
    assert res_hyb["selected_tool"] == TOOL_HYBRID
    assert "85,000,000" in res_hyb["direct_answer"]
