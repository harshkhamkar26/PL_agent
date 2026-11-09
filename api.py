"""
Enterprise REST API for PL Capital Portfolio Analytics Agent.
Built with FastAPI, featuring Swagger UI, schema validation,
portfolio comparisons, CSV export, and financial risk glossary.
"""

import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

WEB_DIR = BASE_DIR / "web"

from agent.portfolio_agent import PortfolioAgent
from database.db_manager import DatabaseManager, default_db_manager
from evaluation.evaluator import AgentEvaluator
from tools.exposure_calculator import ExposureCalculator
from validation.data_reconciler import DataReconciler
from validation.sql_validator import ALLOWED_TABLES, SQLValidator

from fastapi.middleware.cors import CORSMiddleware

import traceback
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse

_init_error = None
try:
    agent = PortfolioAgent()
    db_manager = default_db_manager
    exposure_calc = ExposureCalculator(db_manager)
    reconciler = DataReconciler(db_manager)
except Exception:
    _init_error = traceback.format_exc()
    agent = None
    db_manager = None
    exposure_calc = None
    reconciler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up database connection and master entity indexes."""
    if db_manager is not None:
        try:
            conn = db_manager.get_connection()
            conn.close()
        except Exception as e:
            print(f"[API Startup] DB warm-up notice: {e}")
    yield


app = FastAPI(
    title="PL Capital Portfolio Analytics API",
    description="Evidence-Grounded Financial Intelligence Agent REST API with Multi-Tool Routing & Telemetry",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def diagnostic_middleware(request, call_next):
    if _init_error:
        return JSONResponse(
            status_code=200,
            content={
                "status": "INIT_ERROR",
                "error": _init_error,
            }
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Dashboard"], response_class=HTMLResponse)
def serve_dashboard():
    """Serves the interactive web cockpit application."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="""<!DOCTYPE html><html><head><title>PL Capital API</title></head>
        <body style="background:#121418;color:#eee;font-family:sans-serif;padding:40px;">
        <h1>PL Capital Portfolio Analytics API</h1>
        <p>Evidence-Grounded Financial Intelligence Agent</p>
        <p><a href="/docs" style="color:#ff5722;">Access Swagger API Documentation</a></p>
        </body></html>"""
    )


@app.get("/dashboard", tags=["Dashboard"], response_class=HTMLResponse)
def serve_dashboard_alias():
    """Serves the interactive web cockpit application (alias)."""
    return serve_dashboard()


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about investment portfolios")
    target_dataset: Optional[str] = Field(None, description="Optional target database table scope")
    api_key: Optional[str] = Field(None, description="Optional per-request Google Gemini API key")


class CustomSQLRequest(BaseModel):
    sql: str = Field(..., description="User-defined SELECT query to execute through AST guardrails")


class KeyConfigRequest(BaseModel):
    api_key: str = Field(..., description="Google Gemini API key")
    save_to_env: bool = Field(False, description="Persist key to local .env configuration file")


class QueryResponse(BaseModel):
    timestamp: str
    question: str
    selected_tool: str
    routing_rationale: str
    direct_answer: str
    methodology: str
    formatted_markdown: str
    telemetry: Dict[str, Any]
    evidence: Optional[Any] = None
    total_latency_ms: float
    primary_dataset: Optional[str] = None
    target_dataset: Optional[str] = None
    generated_sql: Optional[str] = None


@app.get("/health", tags=["System"])
def health_check():
    """Health status and database record integrity check."""
    summary = db_manager.verify_database()
    return {
        "status": "healthy",
        "service": "PL Capital Financial Intelligence API",
        "version": "2.0.0",
        "database": {
            "tables": summary["total_tables"],
            "records": summary["total_records"],
            "foreign_key_violations": summary["fk_violations"],
            "all_counts_match": summary["all_counts_match"],
        },
    }


@app.get("/api/v1/config/key/status", tags=["Intelligence Config"])
def get_api_key_status():
    """Returns active AI engine status, masking sensitive tokens."""
    return agent.gemini_client.get_status()


@app.post("/api/v1/config/key", tags=["Intelligence Config"])
def configure_api_key(req: KeyConfigRequest):
    """
    Validates a Google Gemini API key via live API handshake and activates it.
    """
    clean_key = req.api_key.strip()
    if not clean_key:
        agent.gemini_client.set_api_key("", save_to_env=req.save_to_env)
        return {"success": True, "message": "API key cleared. Local deterministic engine active."}

    # Perform live connection verification
    test_result = agent.gemini_client.test_connection(test_key=clean_key)
    if test_result.get("success"):
        agent.gemini_client.set_api_key(clean_key, save_to_env=req.save_to_env)
        return {
            "success": True,
            "message": test_result.get("message", "API key verified successfully."),
            "model": test_result.get("model", "gemini-2.5-flash"),
            "latency_ms": test_result.get("latency_ms", 0),
        }
    else:
        return {
            "success": False,
            "error": test_result.get("error", "Failed to authenticate API key with Google GenAI."),
            "latency_ms": test_result.get("latency_ms", 0),
        }


@app.post("/api/v1/query", response_model=QueryResponse, tags=["Agent Analytics"])
def ask_portfolio_agent(req: QueryRequest):
    """
    Translates a natural language question into validated SQL or exposure metrics,
    returning an evidence-grounded financial audit payload with dataset traceability.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    res = agent.answer_question(
        req.question,
        target_dataset=req.target_dataset,
        api_key=req.api_key,
    )
    return QueryResponse(
        timestamp=res.get("timestamp", ""),
        question=res["question"],
        selected_tool=res["selected_tool"],
        routing_rationale=res["routing_rationale"],
        direct_answer=res["direct_answer"],
        methodology=res["methodology"],
        formatted_markdown=res["formatted_markdown"],
        telemetry=res["telemetry"],
        evidence=res.get("evidence"),
        total_latency_ms=res.get("total_latency_ms", 0.0),
        primary_dataset=res.get("primary_dataset"),
        target_dataset=res.get("target_dataset"),
        generated_sql=res.get("generated_sql"),
    )


@app.get("/api/v1/exposure/{identifier}", tags=["Portfolio Tools"])
def get_portfolio_exposure(identifier: str):
    """
    Calculates equity sector exposure for a specific portfolio,
    enforcing bond exclusion and weight reconciliation.
    """
    try:
        return exposure_calc.calculate_exposure(identifier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/compare/{id1}/{id2}", tags=["Portfolio Tools"])
def compare_portfolios(id1: str, id2: str):
    """
    Performs side-by-side sector exposure and active spread comparison
    between two portfolios.
    """
    try:
        return exposure_calc.compare_portfolios(id1, id2)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolios", tags=["Portfolio Tools"])
def list_portfolios():
    """Returns list of all active and passive portfolios in the database."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT portfolio_id, portfolio_name, target_risk_level, total_aum, strategy_type, benchmark_index, status FROM portfolios ORDER BY portfolio_id")
    portfolios = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"total": len(portfolios), "portfolios": portfolios}


@app.get("/api/v1/portfolio/{portfolio_id}/performance", tags=["Portfolio Analytics"])
def get_portfolio_performance(portfolio_id: int):
    """Returns historical NAV series and risk metrics for a specific portfolio."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT performance_date, nav, total_return_1m, total_return_3m, total_return_1y, volatility, sharpe_ratio, max_drawdown FROM portfolio_performance WHERE portfolio_id = ? ORDER BY performance_date",
        (portfolio_id,),
    )
    perf = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        "SELECT calculation_date, var_95, var_99, cvar_95, beta, correlation_sp500, tracking_error, information_ratio, sortino_ratio FROM risk_metrics WHERE portfolio_id = ? ORDER BY calculation_date",
        (portfolio_id,),
    )
    risk = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not perf and not risk:
        raise HTTPException(status_code=404, detail=f"No performance or risk data found for portfolio {portfolio_id}")

    return {
        "portfolio_id": portfolio_id,
        "performance_records": perf,
        "risk_records": risk,
    }


@app.get("/api/v1/reconcile/{portfolio_id}", tags=["Integrity & Auditing"])
def reconcile_portfolio(portfolio_id: int):
    """Audits weights, detects unallocated cash buffers, and checks bond holdings."""
    try:
        return reconciler.reconcile_portfolio(portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/export/audit-csv", tags=["Integrity & Auditing"])
def export_audit_csv():
    """Exports portfolio weight reconciliation audit as downloadable CSV."""
    audits = reconciler.audit_all_portfolios()
    summary = []
    for a in audits:
        p = a["portfolio"]
        summary.append({
            "Portfolio ID": p["portfolio_id"],
            "Portfolio Name": p["portfolio_name"],
            "Target Risk": p["target_risk_level"],
            "Holdings Count": a["total_holdings_count"],
            "Total Weight (%)": a["total_weight_pct"],
            "Equity Weight (%)": a["equity_weight_pct"],
            "Bond Weight (%)": a["bond_weight_pct"],
            "Unallocated Cash Buffer (%)": a["unallocated_weight_pct"],
            "Audit Status": a["reconciliation_status"],
        })
    df = pd.DataFrame(summary)
    csv_str = df.to_csv(index=False)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio_weight_audit.csv"},
    )


@app.get("/api/v1/metrics/glossary", tags=["Financial Reference"])
def get_metrics_glossary():
    """Provides institutional definitions for quantitative risk and performance metrics."""
    return {
        "Sharpe Ratio": "Measure of risk-adjusted excess return per unit of total portfolio volatility: (R_p - R_f) / sigma_p.",
        "Sortino Ratio": "Modification of Sharpe ratio using downside deviation rather than total standard deviation.",
        "Value at Risk (VaR 95%)": "Maximum estimated portfolio loss with 95% confidence over a specific investment horizon.",
        "Conditional VaR (CVaR 95% / Expected Shortfall)": "Expected average loss in the tail distribution beyond the 95% VaR threshold.",
        "Beta": "Measure of portfolio systematic risk / volatility relative to the benchmark market index (S&P 500).",
        "Herfindahl-Hirschman Index (HHI)": "Measure of sector concentration: sum of squared sector weights. HHI > 0.5 indicates high concentration.",
        "Effective Number of Sectors (Neff)": "Reciprocal of sector HHI (1 / HHI), representing the number of equally weighted sectors.",
        "Max Drawdown": "Maximum observed peak-to-trough decline before a new peak is achieved.",
    }


@app.get("/api/v1/history", tags=["Session & Audit"])
def get_query_history():
    """Returns the session query log with tools routed and latencies."""
    return {"total_queries": len(agent.get_history()), "history": agent.get_history()}


@app.get("/api/v1/evaluate", tags=["Benchmark & Evaluation"])
def run_evaluation():
    """Runs the 10-question ground truth evaluation benchmark."""
    evaluator = AgentEvaluator(db_manager)
    return evaluator.evaluate_all()


@app.get("/api/v1/dataset/tables", tags=["Dataset Studio"])
def list_dataset_tables():
    """Lists all 9 relational tables with row counts and column schemas."""
    summary = db_manager.verify_database()
    schema_summary = db_manager.get_schema_summary()
    tables = []
    descriptions = {
        "portfolios": "Investment portfolios with AUM, target risk level, strategy, and benchmark index.",
        "holdings": "Constituent portfolio positions, quantities, cost basis, and allocation weights.",
        "securities": "Master security definition for stocks and fixed-income bonds.",
        "sectors": "Institutional industry classifications (10 sectors).",
        "transactions": "Historical BUY and SELL execution logs with prices and settlement dates.",
        "historical_prices": "Daily pricing time series with open, close, high, low, and volume.",
        "benchmarks": "Market benchmark definitions (S&P 500, QQQ, AGG, etc.).",
        "portfolio_performance": "Daily NAV, multi-horizon returns, Sharpe ratio, and drawdowns.",
        "risk_metrics": "Value at Risk (VaR 95/99), CVaR, Beta, Tracking Error, and Sortino ratio.",
    }
    for tbl, info in summary["table_details"].items():
        cols = schema_summary.get(tbl, [])
        tables.append({
            "table_name": tbl,
            "row_count": info["count"],
            "status": info["status"],
            "description": descriptions.get(tbl, "Relational dataset table"),
            "columns_count": len(cols),
            "columns": cols,
        })
    return {"total_tables": len(tables), "total_records": summary["total_records"], "tables": tables}


@app.get("/api/v1/dataset/table/{table_name}", tags=["Dataset Studio"])
def get_table_data(
    table_name: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    """Returns paginated records from any of the 9 relational tables."""
    if table_name.lower() not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"Table '{table_name}' is not in approved schema.")

    conn = db_manager.get_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    col_info = [{"name": r["name"], "type": r["type"], "pk": bool(r["pk"])} for r in cur.fetchall()]
    col_names = [c["name"] for c in col_info]

    where_clause = ""
    params = []
    if search:
        text_cols = [c["name"] for c in col_info if "CHAR" in c["type"].upper() or "TEXT" in c["type"].upper() or c["name"] in ["portfolio_name", "symbol", "company_name", "sector_name", "notes"]]
        if not text_cols:
            text_cols = col_names[:3]
        clauses = [f"{col} LIKE ?" for col in text_cols]
        where_clause = " WHERE " + " OR ".join(clauses)
        params = [f"%{search}%"] * len(text_cols)

    count_query = f"SELECT COUNT(*) FROM {table_name}{where_clause};"
    cur.execute(count_query, params)
    total_matching = cur.fetchone()[0]

    data_query = f"SELECT * FROM {table_name}{where_clause} LIMIT ? OFFSET ?;"
    cur.execute(data_query, params + [limit, offset])
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "table_name": table_name,
        "total_rows": total_matching,
        "limit": limit,
        "offset": offset,
        "columns": col_info,
        "rows": rows,
    }


@app.post("/api/v1/dataset/sql", tags=["Dataset Studio"])
def execute_custom_sql(req: CustomSQLRequest):
    """Executes any user-defined SQL query safely through AST inspection."""
    res = agent.sql_tool.execute_direct_sql(req.sql)
    return res


@app.get("/api/v1/dataset/table/{table_name}/csv", tags=["Dataset Studio"])
def export_table_csv(table_name: str):
    """Exports any relational table as downloadable CSV."""
    if table_name.lower() not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"Table '{table_name}' is not in approved schema.")
    conn = db_manager.get_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    csv_str = df.to_csv(index=False)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
    )


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting PL Capital Agent REST API on http://{host}:{port} ...")
    uvicorn.run("api:app", host=host, port=port, reload=False)
