"""
Tests for Conversational Assistant, Agent Persona, and Wellbeing Diagnostics.
"""
import pytest
from fastapi.testclient import TestClient
from api import app
from agent.portfolio_agent import PortfolioAgent
from intelligence.conversational_assistant import ConversationalAssistant

client = TestClient(app)

def test_conversational_assistant_identity():
    assistant = ConversationalAssistant()
    res = assistant.answer_chat("Who are you and what can you do?")
    assert "PL Capital Financial Intelligence Agent" in res["direct_answer"]
    assert "key_capabilities" in res
    assert len(res["key_capabilities"]) > 0

def test_conversational_assistant_wellbeing():
    assistant = ConversationalAssistant()
    res = assistant.answer_chat("What is your wellbeing and system status?")
    assert "OPTIMAL" in res["direct_answer"]
    assert "system_vitals" in res
    assert "0" in res["system_vitals"]["Foreign Key Violations"]

def test_conversational_assistant_methodology_bonds():
    assistant = ConversationalAssistant()
    res = assistant.answer_chat("Why do you exclude bonds from equity sector exposure?")
    assert "partitioned and excluded" in res["direct_answer"]
    assert "explanation" in res

def test_conversational_assistant_ast_security():
    assistant = ConversationalAssistant()
    res = assistant.answer_chat("How does your AST read-only security guardrail work?")
    assert "AST" in res["direct_answer"]
    assert "explanation" in res

def test_portfolio_agent_conversational_routing():
    agent = PortfolioAgent()
    res = agent.answer_question("Who are you?")
    assert res["selected_tool"] == "conversational_assistant"
    assert "PL Capital Financial Intelligence Agent" in res["direct_answer"]

    res_wb = agent.answer_question("What is your wellbeing?")
    assert res_wb["selected_tool"] == "conversational_assistant"
    assert "OPTIMAL" in res_wb["direct_answer"]

def test_api_conversational_endpoints():
    response = client.post("/api/v1/query", json={"question": "Who are you?"})
    assert response.status_code == 200
    data = response.json()
    assert data["selected_tool"] == "conversational_assistant"
    assert "PL Capital" in data["direct_answer"]

    response_wb = client.post("/api/v1/query", json={"question": "What is your wellbeing?"})
    assert response_wb.status_code == 200
    data_wb = response_wb.json()
    assert data_wb["selected_tool"] == "conversational_assistant"
    assert "OPTIMAL" in data_wb["direct_answer"]
