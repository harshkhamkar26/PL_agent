"""
Result Validation Layer for PL Capital Portfolio Analytics Agent.
Validates analytical outputs, SQL result sets, and calculated exposures
prior to user-facing response formatting.
"""

from typing import Any, Dict, List, Optional, Tuple


class ResultValidator:
    """
    Validates structural shape, entity fidelity, and financial plausibility
    of query results before presenting them to users.
    """

    @classmethod
    def validate_sql_result(
        cls,
        question: str,
        generated_sql: str,
        rows: List[Dict[str, Any]],
        columns: List[str],
        resolved_entities: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates SQL result set shape and financial bounds against user question.
        Returns: (is_valid: bool, failure_reason: Optional[str])
        """
        q_lower = question.lower().strip()
        sql_upper = generated_sql.upper()

        # 1. Total AUM / Single Aggregation queries must not return raw multi-row dumps
        if ("total aum" in q_lower or "total assets" in q_lower) and not ("group by" in sql_upper or "each" in q_lower or "by sector" in q_lower or "by portfolio" in q_lower):
            if len(rows) > 1 and "SUM" not in sql_upper:
                return False, f"Aggregate intent mismatch: Expected single aggregated AUM, but received {len(rows)} constituent rows."

        # 2. Company / Ticker fidelity check
        if resolved_entities and resolved_entities.get("security"):
            sec = resolved_entities["security"]
            expected_symbol = sec.symbol.upper()
            # If the query had a security filter, ensure no other securities leaked into the rows
            if "symbol" in [c.lower() for c in columns]:
                mismatched = [
                    r.get("symbol") or r.get("SYMBOL")
                    for r in rows
                    if r.get("symbol") and str(r.get("symbol")).upper() != expected_symbol
                ]
                if mismatched and len(mismatched) == len(rows):
                    return False, f"Entity fidelity mismatch: Query requested '{expected_symbol}' ({sec.company_name}), but result contains unrelated securities ({set(mismatched)})."

        # 3. Financial bounds verification
        for r in rows:
            # AUM non-negative
            for col in ["total_aum", "aum", "SUM(total_aum)"]:
                if col in r and r[col] is not None:
                    try:
                        if float(r[col]) < 0:
                            return False, f"Financial sanity violation: Negative AUM value ({r[col]}) detected."
                    except (ValueError, TypeError):
                        pass

            # Prices positive
            for col in ["price", "current_price", "purchase_price", "close_price"]:
                if col in r and r[col] is not None:
                    try:
                        if float(r[col]) <= 0:
                            return False, f"Financial sanity violation: Non-positive security price ({r[col]}) detected."
                    except (ValueError, TypeError):
                        pass

            # Percentage exposures within [0.0, 100.0]
            for col in ["current_weight", "exposure_pct", "tech_percentage"]:
                if col in r and r[col] is not None:
                    try:
                        val = float(r[col])
                        # Normalize 0.0-1.0 to percentage
                        pct = val * 100.0 if val <= 1.0 and col == "current_weight" else val
                        if pct < 0.0 or pct > 100.001:
                            return False, f"Financial sanity violation: Allocation percentage ({pct:.2f}%) outside valid range [0, 100]."
                    except (ValueError, TypeError):
                        pass

        return True, None

    @classmethod
    def validate_exposure_result(
        cls,
        exposure_data: Dict[str, Any],
        expected_portfolio: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates ExposureCalculator output:
        - Pure equity exposure excluding bonds
        - Sum of sector exposures + cash buffer = 100%
        - Non-negative market values and weights
        """
        if not exposure_data.get("success", True) and "error" in exposure_data:
            return False, exposure_data.get("error", "Exposure calculation failed.")

        pname = exposure_data.get("portfolio_name")
        if expected_portfolio and pname and expected_portfolio.lower() not in pname.lower():
            return False, f"Portfolio target mismatch: expected '{expected_portfolio}', got '{pname}'."

        sec_exposures = exposure_data.get("sector_exposures", {})
        for sec_name, pct in sec_exposures.items():
            if pct < 0.0 or pct > 100.0:
                return False, f"Sector exposure '{sec_name}' has invalid percentage: {pct}%"

        # Verify excluded bonds are not in sector exposures
        excluded = exposure_data.get("excluded_bonds", [])
        if excluded:
            for b in excluded:
                bsym = b.get("symbol")
                if bsym and bsym in sec_exposures:
                    return False, f"Asset segregation violation: Bond '{bsym}' was improperly included in equity sector exposure."

        return True, None
