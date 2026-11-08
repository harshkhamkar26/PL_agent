"""
Deep Quantitative Test Suite for Exposure Calculator & Multi-Asset Integrity (Phase 3).
Validates equity isolation, bond exclusion, cash buffer reconciliation,
HHI concentration indices, and side-by-side portfolio comparisons.
"""

import pytest
from tools.exposure_calculator import ExposureCalculator
from database.db_manager import DatabaseManager


@pytest.fixture
def calc():
    return ExposureCalculator()


# --- 1. Official Ground Truth Questions ---

def test_q9_tech_innovation_fund(calc):
    res = calc.calculate_exposure("Tech Innovation Fund")
    assert res["portfolio_name"] == "Tech Innovation Fund"
    assert res["sector_exposures"] == {"Technology": 100.0}
    assert res["total_equity_exposure_pct"] == 100.0
    assert res["excluded_bond_weight_pct"] == 0.0
    assert res["unallocated_cash_pct"] == 0.0
    # HHI concentration
    assert res["hhi_concentration"] == 1.0
    assert res["effective_sectors_count"] == 1.0
    assert res["concentration_profile"] == "Highly Concentrated"


def test_q10_international_equity_fuzzy(calc):
    # Query via lower-case fuzzy string without "Fund"
    res = calc.calculate_exposure("international equity")
    assert res["portfolio_name"] == "International Equity Fund"
    expected = {"Energy": 38.0, "Technology": 36.0, "Automotive": 15.0, "Consumer Staples": 11.0}
    assert res["sector_exposures"] == expected
    assert res["total_equity_exposure_pct"] == 100.0
    assert res["excluded_bond_weight_pct"] == 0.0
    assert res["unallocated_cash_pct"] == 0.0
    # Effective number of sectors
    assert res["effective_sectors_count"] > 3.0


# --- 2. Multi-Asset & Bond Exclusion Verification ---

def test_balanced_portfolio_bond_exclusion(calc):
    res = calc.calculate_exposure("Balanced Portfolio")
    assert res["portfolio_id"] == 4
    # Equity weight must be exactly 36%, Bond weight 64%
    assert res["total_equity_exposure_pct"] == 36.0
    assert res["excluded_bond_weight_pct"] == 64.0
    assert res["unallocated_cash_pct"] == 0.0
    assert len(res["excluded_bonds"]) == 4
    # Check that bonds are NOT present in sector exposures
    assert "Bond" not in res["sector_exposures"]
    for sec_name in res["sector_exposures"].keys():
        assert sec_name != "Bond"


def test_conservative_income_fund_bond_exclusion(calc):
    res = calc.calculate_exposure("Conservative Income Fund")
    assert res["portfolio_id"] == 2
    # Equity weight must be 32%, Bond weight 68%
    assert res["total_equity_exposure_pct"] == 32.0
    assert res["excluded_bond_weight_pct"] == 68.0
    assert len(res["excluded_bonds"]) == 4


def test_pure_bond_funds_zero_equity(calc):
    for fund_name in ["Fixed Income Plus", "Total Bond Market Index Fund"]:
        res = calc.calculate_exposure(fund_name)
        assert res["total_equity_exposure_pct"] == 0.0
        assert res["excluded_bond_weight_pct"] == 100.0
        assert res["sector_exposures"] == {}
        assert res["concentration_profile"] == "Pure Fixed-Income (Zero Equity)"


# --- 3. Cash Buffer Anomaly Detection (Fund 11) ---

def test_fund_11_unallocated_cash_buffer(calc):
    res = calc.calculate_exposure("Total Stock Market Index Fund")
    assert res["portfolio_id"] == 11
    # 98% equity, 0% bonds, 2% unallocated buffer
    assert res["total_equity_exposure_pct"] == 98.0
    assert res["excluded_bond_weight_pct"] == 0.0
    assert res["unallocated_cash_pct"] == 2.0
    # Must preserve true weights without silent normalization
    total_weights = sum(res["sector_exposures"].values())
    assert round(total_weights, 2) == 98.0


# --- 4. Side-by-Side Portfolio Comparison ---

def test_portfolio_comparison_spread(calc):
    comp = calc.compare_portfolios("Tech Innovation Fund", "International Equity Fund")
    assert comp["portfolio_1"]["name"] == "Tech Innovation Fund"
    assert comp["portfolio_2"]["name"] == "International Equity Fund"
    assert comp["sectors_compared"] == 4
    # Technology spread: 100% vs 36% -> delta = +64%
    tech_row = next(r for r in comp["comparison_matrix"] if r["sector"] == "Technology")
    assert tech_row["portfolio_1_pct"] == 100.0
    assert tech_row["portfolio_2_pct"] == 36.0
    assert tech_row["active_delta_pct"] == 64.0
    assert "Tech Innovation Fund Overweight" in tech_row["spread_status"]


# --- 5. Entity Resolution Robustness ---

def test_entity_resolution_by_id(calc):
    pid, pname = calc.resolve_portfolio(3)
    assert pid == 3 and pname == "Tech Innovation Fund"
    pid, pname = calc.resolve_portfolio("7")
    assert pid == 7 and pname == "International Equity Fund"


def test_entity_resolution_invalid_raises_error(calc):
    with pytest.raises(ValueError) as excinfo:
        calc.resolve_portfolio("Non Existent Crypto Fund")
    assert "Could not resolve portfolio" in str(excinfo.value)
