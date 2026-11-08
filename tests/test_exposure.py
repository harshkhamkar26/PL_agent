"""Unit tests for Exposure Calculator & Financial Reconciliation."""
import pytest
from tools.exposure_calculator import ExposureCalculator

@pytest.fixture
def calc():
    return ExposureCalculator()

def test_tech_innovation_fund_exposure(calc):
    res = calc.calculate_exposure("Tech Innovation Fund")
    assert res["sector_exposures"] == {"Technology": 100.0}
    assert res["total_equity_exposure_pct"] == 100.0
    assert res["excluded_bond_weight_pct"] == 0.0

def test_international_equity_fund_exposure(calc):
    res = calc.calculate_exposure("international equity")
    expected = {"Energy": 38.0, "Technology": 36.0, "Automotive": 15.0, "Consumer Staples": 11.0}
    assert res["sector_exposures"] == expected
    assert res["total_equity_exposure_pct"] == 100.0

def test_bond_exclusion_in_balanced_portfolio(calc):
    res = calc.calculate_exposure("Balanced Portfolio")
    # Balanced portfolio has bonds that should be excluded
    assert res["excluded_bond_weight_pct"] > 0
    assert len(res["excluded_bonds"]) > 0

def test_fund_11_unallocated_cash_detection(calc):
    res = calc.calculate_exposure("Total Stock Market Index Fund")
    assert res["unallocated_cash_pct"] == 2.0
