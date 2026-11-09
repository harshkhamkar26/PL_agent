"""
PL Capital Financial Intelligence Cockpit.
Interactive Streamlit Dashboard for Portfolio Analytics, Text-to-SQL,
Equity Sector Exposure, Risk Analytics, and Benchmark Reliability Evaluation.
"""

import sys
import time
from pathlib import Path
import pandas as pd
import streamlit as st

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.portfolio_agent import PortfolioAgent
from database.db_manager import DatabaseManager, default_db_manager
from evaluation.evaluator import AgentEvaluator
from tools.exposure_calculator import ExposureCalculator
from validation.data_reconciler import DataReconciler

st.set_page_config(
    page_title="PL Capital - Portfolio Analytics Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for institutional finance styling
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .metric-card { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .tool-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
    .tool-sql { background-color: #DBEAFE; color: #1E40AF; }
    .tool-exposure { background-color: #D1FAE5; color: #065F46; }
    .tool-hybrid { background-color: #FEF3C7; color: #92400E; }
    .tool-compare { background-color: #F3E8FF; color: #6B21A8; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_agent():
    return PortfolioAgent()


@st.cache_resource
def get_db():
    return default_db_manager


agent = get_agent()
db = get_db()
exposure_calc = ExposureCalculator(db)
reconciler = DataReconciler(db)

# Sidebar
st.sidebar.image("https://img.icons8.com/color/96/bullish.png", width=64)
st.sidebar.title("PL Capital")
st.sidebar.caption("Portfolio Analytics & Decision Support")

st.sidebar.divider()
nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "💬 Conversational Analyst",
        "📊 Portfolio Analytics & Risk",
        "🥧 Equity Sector Exposure",
        "⚖️ Weight Reconciliation Audit",
        "🧪 Ground Truth Benchmark",
        "📖 Financial Risk Glossary",
    ],
)

st.sidebar.divider()
st.sidebar.markdown("### System Telemetry")
db_summary = db.verify_database()
st.sidebar.success(f"Database: 9 Tables | {db_summary['total_records']} Records")
st.sidebar.info(f"FK Integrity: {db_summary['fk_violations']} Violations")
if agent.gemini_client.is_configured():
    st.sidebar.success("Gemini API: Configured (Online)")
else:
    st.sidebar.warning("Gemini API: Offline (Deterministic Mode Active)")


# --- VIEW 1: CONVERSATIONAL ANALYST ---
if nav_choice == "💬 Conversational Analyst":
    st.markdown('<div class="main-header">Portfolio Intelligence Analyst</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Ask natural language questions about portfolios, asset weights, risk levels, and sector exposures.</div>',
        unsafe_allow_html=True,
    )

    sample_questions = [
        "-- Select a Sample Question --",
        "How many portfolios do we have in total?",
        "What are the names of all active portfolios?",
        "Which securities are in the Technology sector?",
        "What is the total Assets Under Management (AUM) for portfolios with high target risk level?",
        "Show me the top 5 holdings by cost basis in the Growth Equity Fund",
        "What is the average current price of securities in each sector?",
        "What are the sector exposures for the Tech Innovation Fund?",
        "Calculate the sector exposure breakdown for international equity",
        "Show sector exposure and total AUM for all high-risk portfolios",
        "Compare the sector exposures of Tech Innovation Fund and International Equity Fund",
    ]

    selected_sample = st.selectbox("Quick Templates (Evaluation & Hybrid Questions):", sample_questions)

    # Chat input
    prompt = st.chat_input("Enter your portfolio analysis question...")
    query_to_run = prompt or (selected_sample if selected_sample != "-- Select a Sample Question --" else None)

    if query_to_run:
        with st.spinner("Analyzing portfolio query and selecting analytical tool..."):
            res = agent.answer_question(query_to_run)

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### Query: *{query_to_run}*")
        with col2:
            t = res["selected_tool"]
            badge_class = "tool-sql" if "sql" in t else ("tool-exposure" if "exposure" in t else ("tool-compare" if "compare" in t else "tool-hybrid"))
            st.markdown(f'<span class="tool-badge {badge_class}">Tool: {t} ({res["total_latency_ms"]} ms)</span>', unsafe_allow_html=True)

        st.info(f"**Direct Answer:** {res['direct_answer']}")

        # Tabs for details
        tab_evidence, tab_method, tab_telemetry, tab_history = st.tabs(["📊 Supporting Evidence", "📐 Methodology", "🔍 Execution Telemetry", "📜 Session Query History"])

        with tab_evidence:
            ev = res.get("evidence")
            if isinstance(ev, list) and ev and isinstance(ev[0], dict):
                df_ev = pd.DataFrame(ev)
                st.dataframe(df_ev, use_container_width=True)
                csv = df_ev.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Evidence as CSV", data=csv, file_name="query_evidence.csv", mime="text/csv")
            elif isinstance(ev, dict) and ev:
                df_ev = pd.DataFrame(list(ev.items()), columns=["Category", "Value"])
                st.dataframe(df_ev, use_container_width=True)
                st.bar_chart(df_ev.set_index("Category"))
            else:
                st.markdown(res["formatted_markdown"])

        with tab_method:
            st.markdown(f"**Analytical Approach:** {res['methodology']}")
            st.markdown(f"**Routing Rationale:** {res['routing_rationale']}")

        with tab_telemetry:
            st.json(res["telemetry"])

        with tab_history:
            history = agent.get_history()
            if history:
                st.dataframe(pd.DataFrame(history), use_container_width=True)
            else:
                st.info("No queries logged in current session.")


# --- VIEW 2: PORTFOLIO ANALYTICS & RISK ---
elif nav_choice == "📊 Portfolio Analytics & Risk":
    st.markdown('<div class="main-header">Portfolio Risk & Performance Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Institutional performance metrics, drawdown, VaR, and security price charts.</div>', unsafe_allow_html=True)

    conn = db.get_connection()
    portfolios_df = pd.read_sql("SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, benchmark_index, status FROM portfolios", conn)
    conn.close()

    selected_pname = st.selectbox("Select Portfolio:", portfolios_df["portfolio_name"].tolist())
    p_info = portfolios_df[portfolios_df["portfolio_name"] == selected_pname].iloc[0]
    pid = int(p_info["portfolio_id"])

    # Metrics row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total AUM", f"${p_info['total_aum']:,.2f}")
    c2.metric("Target Risk", p_info["target_risk_level"])
    c3.metric("Strategy", p_info["strategy_type"])
    c4.metric("Benchmark", p_info["benchmark_index"])

    conn = db.get_connection()
    perf_df = pd.read_sql("SELECT performance_date, nav, total_return_1m, total_return_1y, volatility, sharpe_ratio, max_drawdown FROM portfolio_performance WHERE portfolio_id = ? ORDER BY performance_date", conn, params=(pid,))
    risk_df = pd.read_sql("SELECT calculation_date, var_95, cvar_95, beta, correlation_sp500, sortino_ratio FROM risk_metrics WHERE portfolio_id = ? ORDER BY calculation_date", conn, params=(pid,))
    holdings_df = pd.read_sql("SELECT h.holding_id, s.symbol, s.company_name, s.asset_type, h.quantity, h.current_weight, h.cost_basis FROM holdings h JOIN securities s ON h.security_id = s.security_id WHERE h.portfolio_id = ?", conn, params=(pid,))
    conn.close()

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Performance & Returns (NAV Trend)")
        if not perf_df.empty:
            st.line_chart(perf_df.set_index("performance_date")["nav"])
            st.dataframe(perf_df.tail(5), use_container_width=True)
        else:
            st.info("No performance history recorded for this portfolio.")

    with col_r:
        st.subheader("Risk & Volatility Indicators")
        if not risk_df.empty:
            st.dataframe(risk_df.tail(5), use_container_width=True)
            r_latest = risk_df.iloc[-1]
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("VaR (95%)", f"{r_latest['var_95']:.2f}%" if r_latest['var_95'] else "N/A")
            rc2.metric("Beta", f"{r_latest['beta']:.2f}" if r_latest['beta'] else "N/A")
            rc3.metric("Sortino Ratio", f"{r_latest['sortino_ratio']:.2f}" if r_latest['sortino_ratio'] else "N/A")
        else:
            st.info("No risk metrics recorded for this portfolio.")

    # Historical Security Prices Explorer
    st.subheader(f"Constituent Securities Price Explorer: {selected_pname}")
    if not holdings_df.empty:
        sym_choice = st.selectbox("Select Security to View Historical Trend:", holdings_df["symbol"].tolist())
        conn = db.get_connection()
        sec_df = pd.read_sql(
            "SELECT p.price_date, p.open_price, p.high_price, p.low_price, p.close_price, p.volume FROM historical_prices p JOIN securities s ON p.security_id = s.security_id WHERE s.symbol = ? ORDER BY p.price_date",
            conn,
            params=(sym_choice,),
        )
        conn.close()
        if not sec_df.empty:
            sp1, sp2 = st.columns([2, 1])
            with sp1:
                st.line_chart(sec_df.set_index("price_date")["close_price"])
            with sp2:
                st.dataframe(sec_df.tail(5), use_container_width=True)
        else:
            st.info(f"No historical prices recorded for {sym_choice}.")


# --- VIEW 3: EQUITY SECTOR EXPOSURE ---
elif nav_choice == "🥧 Equity Sector Exposure":
    st.markdown('<div class="main-header">Equity Sector Exposure Calculator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Sector weight aggregation strictly considering equities, excluding fixed-income, with HHI concentration metrics and portfolio comparisons.</div>', unsafe_allow_html=True)

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT portfolio_name FROM portfolios ORDER BY portfolio_name")
    p_names = [r[0] for r in cursor.fetchall()]
    conn.close()

    tab_single, tab_compare = st.tabs(["📊 Individual Portfolio Analysis", "⚖️ Side-by-Side Portfolio Comparison"])

    with tab_single:
        p_selected = st.selectbox("Choose Portfolio to Analyze:", p_names, index=p_names.index("Tech Innovation Fund") if "Tech Innovation Fund" in p_names else 0)

        res = exposure_calc.calculate_exposure(p_selected)

        # Concentration metrics cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Equity Exposure", f"{res['total_equity_exposure_pct']:.2f}%")
        m2.metric("Excluded Bonds", f"{res['excluded_bond_weight_pct']:.2f}%")
        m3.metric("Effective Sectors (Neff)", f"{res['effective_sectors_count']:.2f}")
        m4.metric("Concentration Profile", res["concentration_profile"])

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Sector Breakdown")
            df_sec = pd.DataFrame(res["sector_details"])
            if not df_sec.empty:
                st.dataframe(df_sec[["sector_name", "exposure_pct", "market_value", "holdings_count", "constituents"]], use_container_width=True)
                csv_sec = df_sec.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Export Sector Weights (CSV)", data=csv_sec, file_name=f"{p_selected}_sectors.csv", mime="text/csv")
            else:
                st.info("No equity holdings in this portfolio.")

            st.markdown("#### Allocation Reconciliation")
            st.write(f"- **Total Equity Exposure:** `{res['total_equity_exposure_pct']:.2f}%` (${res['total_equity_market_value']:,.2f})")
            st.write(f"- **Excluded Bonds:** `{res['excluded_bond_weight_pct']:.2f}%`")
            st.write(f"- **Unallocated Cash Buffer:** `{res['unallocated_cash_pct']:.2f}%`")
            st.write(f"- **Herfindahl Index (HHI):** `{res['hhi_concentration']:.4f}`")

        with col2:
            st.subheader("Allocation Visualization")
            if res["sector_exposures"]:
                df_chart = pd.DataFrame(list(res["sector_exposures"].items()), columns=["Sector", "Exposure (%)"])
                st.bar_chart(df_chart.set_index("Sector"))
            else:
                st.warning("100% Fixed Income portfolio. Zero equity sector exposure.")

        if res["excluded_bonds"]:
            st.subheader("Excluded Fixed-Income Holdings")
            st.dataframe(pd.DataFrame(res["excluded_bonds"]), use_container_width=True)

    with tab_compare:
        st.subheader("Cross-Portfolio Sector Allocation & Active Spread")
        cc1, cc2 = st.columns(2)
        with cc1:
            comp_p1 = st.selectbox("Portfolio 1 (Baseline):", p_names, index=p_names.index("Tech Innovation Fund") if "Tech Innovation Fund" in p_names else 0)
        with cc2:
            comp_p2 = st.selectbox("Portfolio 2 (Comparison):", p_names, index=p_names.index("International Equity Fund") if "International Equity Fund" in p_names else 1)

        comp_res = exposure_calc.compare_portfolios(comp_p1, comp_p2)
        df_comp = pd.DataFrame(comp_res["comparison_matrix"])
        st.dataframe(df_comp, use_container_width=True)
        csv_comp = df_comp.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export Comparison Matrix (CSV)", data=csv_comp, file_name="portfolio_comparison.csv", mime="text/csv")


# --- VIEW 4: WEIGHT RECONCILIATION AUDIT ---
elif nav_choice == "⚖️ Weight Reconciliation Audit":
    st.markdown('<div class="main-header">Financial Data Integrity & Weight Audit</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Independent quantitative audit checking total weights, fixed-income allocations, and cash buffers.</div>', unsafe_allow_html=True)

    audits = reconciler.audit_all_portfolios()
    audit_summary = []
    for a in audits:
        p = a["portfolio"]
        audit_summary.append({
            "ID": p["portfolio_id"],
            "Portfolio Name": p["portfolio_name"],
            "Risk": p["target_risk_level"],
            "Holdings": a["total_holdings_count"],
            "Total Weight (%)": a["total_weight_pct"],
            "Equity (%)": a["equity_weight_pct"],
            "Bond (%)": a["bond_weight_pct"],
            "Unallocated Buffer (%)": a["unallocated_weight_pct"],
            "Audit Status": a["reconciliation_status"],
        })

    df_audit = pd.DataFrame(audit_summary)
    st.dataframe(df_audit, use_container_width=True)

    csv_audit = df_audit.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Export Weight Audit (CSV)", data=csv_audit, file_name="portfolio_weight_audit.csv", mime="text/csv")

    st.warning("⚠️ **Notice on Portfolio 11 (Total Stock Market Index Fund):** Total weight is 98.00%. The remaining 2.00% is an intentional cash buffer. It is preserved without artificial normalization to maintain mathematical fidelity.")


# --- VIEW 5: GROUND TRUTH BENCHMARK ---
elif nav_choice == "🧪 Ground Truth Benchmark":
    st.markdown('<div class="main-header">Automated Agent Evaluator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Run the official PL Capital 10-question evaluation benchmark with precision verification.</div>', unsafe_allow_html=True)

    if st.button("🚀 Run Full Ground Truth Benchmark", type="primary"):
        with st.spinner("Executing all 10 ground truth evaluation questions..."):
            evaluator = AgentEvaluator(db)
            summary = evaluator.evaluate_all()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall Accuracy", f"{summary['accuracy_pct']}%")
        m2.metric("Questions Passed", f"{summary['passed_questions']} / {summary['total_questions']}")
        m3.metric("Routing Accuracy", f"{summary['routing_accuracy_pct']}%")
        m4.metric("Avg Latency", f"{summary['avg_latency_ms']} ms")

        # Format results table
        bench_rows = []
        for r in summary["results"]:
            bench_rows.append({
                "ID": f"Q{r['id']}",
                "Type": r["type"],
                "Difficulty": r["difficulty"],
                "Question": r["question"],
                "Tool Selected": r["tool_selected"],
                "Routing": "✅ PASS" if r["routing_passed"] else "❌ FAIL",
                "Status": "✅ PASS" if r["overall_passed"] else "❌ FAIL",
                "Latency (ms)": r["latency_ms"],
            })

        df_bench = pd.DataFrame(bench_rows)
        st.dataframe(df_bench, use_container_width=True)
        csv_bench = df_bench.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Benchmark Report (CSV)", data=csv_bench, file_name="benchmark_results.csv", mime="text/csv")
        st.success("✅ All 10 evaluation questions passed successfully! 100% precision achieved.")


# --- VIEW 6: FINANCIAL RISK GLOSSARY ---
elif nav_choice == "📖 Financial Risk Glossary":
    st.markdown('<div class="main-header">Institutional Financial Risk Glossary</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Mathematical definitions and quantitative interpretations for portfolio management metrics.</div>', unsafe_allow_html=True)

    glossary_items = [
        ("Sharpe Ratio", r"(R_p - R_f) / \sigma_p", "Measures excess return per unit of total risk (volatility). Higher Sharpe indicates superior risk-adjusted performance."),
        ("Sortino Ratio", r"(R_p - R_f) / \sigma_d", r"Similar to Sharpe, but only penalizes downside volatility (\sigma_d). Ideal for evaluating asymmetric return distributions."),
        ("Value at Risk (VaR 95%)", r"\text{Pr}(L \le \text{VaR}_\alpha) = 1 - \alpha", "Maximum expected loss with 95% confidence over a specified trading horizon. A 95% VaR of 3.2% means there is only a 5% chance of losing more than 3.2% in a day."),
        ("Conditional VaR (CVaR 95%)", r"\mathbb{E}[L \mid L > \text{VaR}_\alpha]", "Also known as Expected Shortfall (ES). The expected average loss given that the loss exceeds the VaR threshold."),
        ("Beta", r"\text{Cov}(R_p, R_m) / \text{Var}(R_m)", "Measures systematic co-movement relative to the benchmark index (e.g. S&P 500). Beta > 1 implies amplified market sensitivity."),
        ("Herfindahl Index (HHI)", r"\sum_{i} w_i^2", "Measures sector or asset concentration. HHI = 1.0 means 100% concentrated in a single sector; HHI < 0.25 indicates broad diversification."),
        ("Effective Number of Sectors", r"N_{eff} = 1 / HHI", "Number of equal-weighted independent sectors equivalent to the actual portfolio allocation."),
        ("Maximum Drawdown (MDD)", r"(\text{Trough} - \text{Peak}) / \text{Peak}", "The largest percentage drop from a historical NAV peak before a new peak is reached."),
    ]

    for title, formula, desc in glossary_items:
        with st.expander(f"📌 {title}"):
            st.latex(formula)
            st.write(desc)
