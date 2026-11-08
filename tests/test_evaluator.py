"""Unit tests for Benchmark Evaluator and Regression Harness (Phase 5)."""
import pytest
from evaluation.evaluator import AgentEvaluator

def test_evaluator_achieves_100_percent():
    evaluator = AgentEvaluator()
    summary = evaluator.evaluate_all()
    assert summary["total_questions"] == 10
    assert summary["passed_questions"] == 10
    assert summary["accuracy_pct"] == 100.0
    assert summary["routing_accuracy_pct"] == 100.0
    assert summary["completeness_pct"] == 100.0
    assert summary["avg_latency_ms"] < 20.0  # Ultra-fast sub-20ms execution
    assert summary["regression_status"]["status"] in {"INITIAL_BASELINE", "PASS_NO_REGRESSION"}
