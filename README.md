# Finance Intelligence Agent (FIA)
### An Explainable, Evidence-Grounded AI System for Portfolio Analytics & Decision Support
**PL Capital (Prabhudas Lilladher) — AI Engineering Internship Assessment**

[![Evaluation](https://img.shields.io/badge/Canonical%20Benchmark-10%2F10%20(100%25)-brightgreen.svg)]()
[![Regression Suite](https://img.shields.io/badge/Regression%20Suite-23%2F23%20(100%25)-brightgreen.svg)]()
[![Test Suite](https://img.shields.io/badge/Pytest-106%20Passed-brightgreen.svg)]()
[![SQL Safety](https://img.shields.io/badge/SQL%20Security-AST%20(sqlglot)%20%2B%20C--Authorizer-green.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20Streamlit%20%7C%20Web%20Cockpit-orange.svg)]()

---

## Executive Overview

In institutional investment management and equity research, an unauditable AI black-box is unacceptable. Portfolio managers, quantitative analysts, and compliance officers require **mathematical precision**, **strict asset classification**, and an **uncompromising audit trail**.

The **Finance Intelligence Agent (FIA)** transforms natural language investment queries into validated, evidence-backed portfolio analytics. Beyond the core assessment deliverables, the system introduces a **production-grade financial intelligence architecture** designed for institutional buy-side and sell-side workflows.

### Core Engineering Differentiators
1. **100% Canonical Benchmark Accuracy:** Achieves a **10/10 (100.0%) pass rate** on the official PL Capital ground truth evaluation suite with ~2.3ms average latency.
2. **23/23 (100.0%) Expanded Regression Suite:** Covers company name queries, ticker symbols, scalar aggregations, grouped returns, transaction filtering, sector percentage allocations, portfolio comparisons, and risk profiles.
3. **Genuine AST-Based SQL Security Layer (`sqlglot`):**
   - True Abstract Syntax Tree decomposition replacing fragile regex-only checks.
   - Enforces read-only statements (`SELECT`, `WITH`).
   - Rejects mutations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA`, `ATTACH`, `DETACH`).
   - Walks AST to extract table references; verifies all non-CTE tables belong to `ALLOWED_TABLES`.
   - **Defense-in-Depth:** Hardware/C-level SQLite authorizer (`conn.set_authorizer`) active on all database executions.
4. **Financial Entity Resolver (`agent/entity_resolver.py`):**
   - Dynamic memory cache grounded directly against SQLite tables (`securities`, `portfolios`, `sectors`, `benchmarks`).
   - Bidirectional resolution: company names to tickers (e.g. "Apple" $\rightarrow$ `AAPL`), tickers to company names (`AAPL` $\rightarrow$ "Apple Inc."), and common aliases (e.g. "Google" $\rightarrow$ `GOOGL`, "Nvidia" $\rightarrow$ `NVDA`, "Amazon" $\rightarrow$ `AMZN`, "Tesla" $\rightarrow$ `TSLA`, "Facebook" $\rightarrow$ `META`).
   - Resolves security IDs before query compilation.
5. **Post-Execution Result Validation Layer (`validation/result_validator.py`):**
   - Verifies result shape matches user intent (aggregations return scalar records; entity queries contain requested symbols).
   - Enforces financial sanity bounds (non-negative AUM, positive prices, valid allocations in $[0, 100]\%$).
6. **Institutional Financial Data Integrity & Reconciliation:**
   - **Fixed-Income Partitioning:** Strictly excludes bonds (`asset_type = 'Bond'`, `sector_id IS NULL`) from equity sector exposures.
   - **Cash Buffer Auditing:** Uncovers and reports the real-world **2.00% unallocated cash buffer** in Portfolio 11 (`Total Stock Market Index Fund`) rather than silently normalizing to 100%.
7. **4-Part Evidence Grounding:** Every analytical response includes:
   - *Direct Answer* (financially formatted with currency and percentages).
   - *Constituent Supporting Evidence* (underlying records and assets).
   - *Methodology & Reconciliation* (algebraic formulas and CTE logic).
   - *Verified Telemetry* (read-only verification, latency in ms, row scan count).
8. **Multi-Interface Production Readiness:**
   - Interactive terminal CLI (`main.py` with `--eval` and `--regression`).
   - Enterprise FastAPI REST API with Swagger UI (`api.py`).
   - Institutional Streamlit Financial Cockpit (`app.py`).
   - Interactive Web Cockpit with Railway Aesthetic (`web/index.html`).

---

## Agent Intelligence Improvements

The following 5 verified failure modes were investigated, diagnosed, and permanently resolved:

### 1. Company-Name and Ticker Resolution (Section 4.1)
- **Previous Failure:** "Which portfolios hold Apple?" returned all 13 portfolios via fallback table dump, whereas "Which portfolios hold AAPL?" worked correctly.
- **Root Cause:** Known ticker lists only checked uppercase symbols (`AAPL`); natural company names ("Apple") missed token matching and defaulted to full portfolios query.
- **Resolution:** Implemented `EntityResolver` grounded in securities master data. Natural language queries referencing "Apple", "Microsoft", "NVIDIA", "Amazon", etc. resolve to exact `security_id` values and generate SQL joining `holdings`, `portfolios`, and `securities` filtered by `WHERE s.security_id = ?`.
- **Verified Behavior:** "Which portfolios hold Apple?" returns **exactly the 7 portfolios** holding `AAPL` ($1,866,148 cost basis).

### 2. Correct Aggregate SQL Generation (Section 4.2)
- **Previous Failure:** "What is the total AUM across all portfolios?" returned 13 individual rows instead of one aggregate total.
- **Root Cause:** Keyword "aum" was routed to table-level selection without detecting scalar aggregation intent.
- **Resolution:** Added aggregate-intent recognition for total AUM, average AUM, active count, and sector totals.
- **Verified Behavior:** "What is the total AUM across all portfolios?" generates `SELECT SUM(total_aum) AS total_aum, COUNT(*) AS total_portfolios FROM portfolios;` and returns a single scalar record of **$323,500,000.00** across 13 portfolios.

### 3. Average Return Calculations (Section 4.3)
- **Previous Failure:** "What is the average return for each portfolio?" sorted performance by Sharpe ratio instead of calculating grouped average returns.
- **Root Cause:** Query templates mapped generic "return" to Sharpe ratio ranking.
- **Resolution:** Implemented grouped financial aggregation over `portfolio_performance` by `portfolio_id` computing `AVG(total_return_1y)` and `AVG(total_return_1m)`.
- **Verified Behavior:** "What is the average return for each portfolio?" returns 4 grouped portfolio records: Tech Innovation (39.98%), Growth Equity (23.79%), Balanced (21.34%), and Conservative Income (13.50%).

### 4. Transaction Filtering (Section 4.4)
- **Previous Failure:** "Give me all transactions for Apple" returned 10 recent transactions of unrelated securities (XOM, BAC, KO).
- **Root Cause:** Keyword "transaction" dispatched a generic transaction table scan without security filtering.
- **Resolution:** `EntityResolver` extracts security entity and binds `s.security_id` to `transactions JOIN securities JOIN portfolios`. Supports `BUY` and `SELL` filters and date ordering.
- **Verified Behavior:** "Give me all transactions for Apple" returns **exactly 4 BUY transactions** for Apple Inc. (`AAPL`).

### 5. Sector Exposure Routing (Section 4.5)
- **Previous Failure:** "What percentage of Growth Equity Fund is invested in Technology?" dumped holdings instead of calculating sector exposure.
- **Root Cause:** Intent router did not recognize portfolio + sector percentage inquiry patterns.
- **Resolution:** Intent router detects portfolio entity + sector entity + percentage/allocation intent, routing to `ExposureCalculator` with `target_sector="Technology"`. Formatter highlights exact allocation.
- **Verified Behavior:** "What percentage of Growth Equity Fund is invested in Technology?" returns: **Growth Equity Fund has a 93.0% equity allocation to Technology** ($1,866,148 market value across 7 holdings, strictly excluding fixed-income).

---

## Architecture

```mermaid
flowchart TD
    subgraph UI ["Interface Deployment Layer"]
        CLI["CLI Agent (main.py)"]
        WEB["Streamlit Cockpit (app.py)"]
        API["FastAPI REST API (api.py)"]
        HTML["Web Cockpit (web/index.html)"]
    end

    subgraph Core ["Agent Core & Entity Grounding (agent/)"]
        Resolver["Financial Entity Resolver (entity_resolver.py)"]
        Router["Intent Classifier & Entity Router (intent_router.py)"]
        Formatter["4-Part Evidence Formatter (response_formatter.py)"]
        History["Session Query History & Telemetry"]
    end

    subgraph Tools ["Analytical Tools Layer (tools/)"]
        SQLTool["Explainable SQL Engine (sql_tool.py)"]
        ExpTool["Quantitative Exposure Calculator (exposure_calculator.py)"]
        HybTool["Hybrid Analytics Engine (hybrid_analytics.py)"]
    end

    subgraph Guardrails ["Security & Validation (validation/ & intelligence/)"]
        AST["AST SQL Guardrail - sqlglot (sql_validator.py)"]
        CAuthorizer["SQLite C-Level Authorizer (db_manager.py)"]
        ResultVal["Result Shape Validator (result_validator.py)"]
        Reconciler["Data Reconciler (data_reconciler.py)"]
        Gemini["Google Gemini Client (gemini_client.py)"]
        Templates["Deterministic Pattern Compiler (query_templates.py)"]
    end

    subgraph Storage ["Relational Data Layer (database/ & data/)"]
        DB[(SQLite: portfolio_database.db)]
        CSVs["9 Relational CSV Datasets (603 records)"]
    end

    UI --> Router
    Router --> Resolver
    Router --> Tools
    SQLTool --> AST
    AST --> CAuthorizer
    AST --> Templates
    AST --> Gemini
    Templates --> DB
    Gemini --> DB
    SQLTool --> ResultVal
    ExpTool --> Reconciler
    ExpTool --> ResultVal
    Reconciler --> DB
    HybTool --> SQLTool
    HybTool --> ExpTool
    Tools --> Formatter
    Formatter --> History
    History --> UI
```

---

## Benchmark Evaluation Matrix

### Official Ground Truth Evaluation (10/10 Passed - 100.0%)

| ID | Category | Question | Tool Used | Status | Execution Latency |
| :---: | :---: | :--- | :---: | :---: | :---: |
| **Q1** | Text-to-SQL | *How many portfolios do we have in total?* | `sql_query_tool` | **PASS** | 2.69 ms |
| **Q2** | Text-to-SQL | *What are the names of all active portfolios?* | `sql_query_tool` | **PASS** | 1.56 ms |
| **Q3** | Text-to-SQL | *Which securities are in the Technology sector?* | `sql_query_tool` | **PASS** | 1.57 ms |
| **Q4** | Text-to-SQL | *What is the total AUM for high target risk portfolios?* | `sql_query_tool` | **PASS** | 1.64 ms |
| **Q5** | Text-to-SQL | *Top 5 holdings by cost basis in Growth Equity Fund* | `sql_query_tool` | **PASS** | 1.40 ms |
| **Q6** | Text-to-SQL | *Average current price of securities in each sector* | `sql_query_tool` | **PASS** | 1.35 ms |
| **Q7** | Text-to-SQL | *Technology value and % of total portfolio value* | `sql_query_tool` | **PASS** | 1.90 ms |
| **Q8** | Text-to-SQL | *Portfolios with >5 sectors & diversification metrics* | `sql_query_tool` | **PASS** | 1.87 ms |
| **Q9** | Exposure | *Sector exposures for Tech Innovation Fund* | `exposure_calculator` | **PASS** | 0.93 ms |
| **Q10**| Exposure | *Sector exposure breakdown for international equity* | `exposure_calculator` | **PASS** | 1.53 ms |

### Expanded Regression Benchmark Suite (23/23 Passed - 100.0%)

Stored in `evaluation/regression_questions.json` and executed via `python main.py --regression`:
- **R1-R4:** Company and symbol resolution (Apple, AAPL, Microsoft, MSFT).
- **R5-R8:** Scalar and grouped aggregations (Total AUM, Average AUM, Active count, Highest avg price).
- **R9-R10:** Grouped portfolio average returns.
- **R11-R13:** Filtered transactions for securities (Apple, AAPL, Amazon).
- **R14:** Sector percentage exposure (Growth Equity Fund in Technology $\rightarrow$ 93.0%).
- **R15-R16:** Dedicated single portfolio sector exposures (Tech Innovation, International Equity).
- **R17:** Side-by-side active spread portfolio comparison.
- **R18:** Multi-step hybrid risk cohort and sector exposure aggregation.
- **R19-R20:** Capital preservation (lowest max drawdown) and downside return (Sortino ratio).
- **R21:** Fixed-income bond partitioning from equities.
- **R22:** Market capitalization rankings (top 5 stocks).
- **R23:** Conversational assistant persona and system wellbeing.

---

## Project Structure

```
pl_capital_agent/
├── data/                                 # 9 Institutional Relational Datasets
│   ├── portfolios.csv, holdings.csv, securities.csv, sectors.csv, transactions.csv,
│   ├── historical_prices.csv, benchmarks.csv, portfolio_performance.csv, risk_metrics.csv
├── database/                             # Database Engineering
│   ├── database_schema.sql               # Relational DDL with composite indexes
│   ├── db_manager.py                     # SQLite lifecycle, authorizer & ingestion
│   └── portfolio_database.db             # Relational SQLite database (603 records)
├── tools/                                # Analytical Tools Layer
│   ├── sql_tool.py                       # Explainable Text-to-SQL engine with EXPLAIN plan
│   ├── exposure_calculator.py            # Pure equity exposure calculator & comparisons
│   └── hybrid_analytics.py               # Combined multi-tool engine (Risk, Status, Top AUM)
├── agent/                                # Agent Core Layer
│   ├── entity_resolver.py                # Financial Entity Resolver (securities, portfolios, sectors)
│   ├── intent_router.py                  # Intent classification & entity routing
│   ├── portfolio_agent.py                # Main dispatching agent with session history
│   └── response_formatter.py             # 4-part evidence audit card formatter
├── validation/                           # Safeguards & Reconcilers
│   ├── sql_validator.py                  # AST SQL safety guardrail (sqlglot) + SQLite C-authorizer
│   ├── result_validator.py               # Post-execution result shape & financial bounds validator
│   └── data_reconciler.py                # Portfolio weight reconciliation & cash buffer auditor
├── intelligence/                         # LLM & Semantic Logic
│   ├── conversational_assistant.py       # Deterministic conversational assistant & wellbeing
│   ├── gemini_client.py                  # Google Gemini API connector (google-genai)
│   └── query_templates.py                # Deterministic pattern compiler & universal synthesizer
├── evaluation/                           # Benchmark & Verification
│   ├── ground_truth_dataset.json         # Official 10 benchmark questions
│   ├── regression_questions.json         # 23 expanded regression questions
│   ├── evaluator.py                      # Automated evaluation script with regression guard
│   └── reports/                          # Generated markdown & JSON reports
│       ├── EVALUATION_REPORT.md
│       └── evaluation_results.json
├── web/                                  # High-Performance Web Cockpit
│   └── index.html                        # Institutional frontend with Railway aesthetics
├── tests/                                # Comprehensive Pytest Suite (106 tests)
│   ├── test_db.py                        # DB schema and row count tests
│   ├── test_sql_tool.py                  # SQL execution tests
│   ├── test_sql_engine_deep.py           # AST security and 8-question deep tests
│   ├── test_exposure.py                  # Basic exposure tests
│   ├── test_exposure_deep.py             # Quantitative concentration & spread tests
│   ├── test_agent.py                     # Agent routing tests
│   ├── test_agent_deep.py                # Hybrid analytics & session history tests
│   ├── test_evaluator.py                 # Evaluator harness tests
│   ├── test_api_endpoints.py             # FastAPI REST endpoint integration tests
│   ├── test_api_key_and_datasets.py      # Dataset viewing and config tests
│   ├── test_conversational_assistant.py  # Conversational assistant tests
│   ├── test_entity_resolver_and_result_validator.py # EntityResolver & ResultValidator tests
│   └── test_regression_suite.py          # 23-question regression suite tests
├── api.py                                # Enterprise FastAPI REST API with Swagger
├── app.py                                # Streamlit Financial Intelligence Cockpit
├── main.py                               # Interactive Command-Line Agent (CLI)
├── Dockerfile                            # Production Container Specification
├── Procfile                              # Web deployment process file
├── render.yaml                           # Cloud PaaS deployment configuration
├── railway.json                          # Railway cloud deployment configuration
├── requirements.txt                      # Python dependencies (includes sqlglot)
├── .env.example                          # Environment variable template
└── README.md                             # Comprehensive technical documentation
```

---

## Quickstart & Installation

### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/harshkhamkar26/PL_agent.git
cd PL_agent

# Install dependencies (Python 3.10+)
pip install -r requirements.txt
```

### 2. Configure Gemini API (Optional)
The agent operates at **100% accuracy offline** via its deterministic engine. If you wish to enable open-ended natural language queries beyond the evaluation suite:
```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

### 3. Initialize the Database
```bash
python database/db_manager.py
```
*Output: All 9 tables initialized, 603 records verified, 0 foreign key violations.*

---

## Running the Deliverables

### Deliverable 1: Command-Line Agent (`main.py`)
Run the interactive conversational agent:
```bash
python main.py
```

Execute a single query directly:
```bash
python main.py "Which portfolios hold Apple?"
```

Run the official 10-question evaluation benchmark:
```bash
python main.py --eval
```

Run the expanded 23-question regression benchmark suite:
```bash
python main.py --regression
```

### Deliverable 2: Ground Truth Evaluator (`evaluation/evaluator.py`)
Run all 10 ground truth questions and verify zero regression:
```bash
python evaluation/evaluator.py
```

### Deliverable 3: Streamlit Financial Cockpit (`app.py`)
Launch the interactive Streamlit dashboard:
```bash
streamlit run app.py
```

### Deliverable 4: Enterprise REST API & Web Cockpit (`api.py`)
Launch the FastAPI server:
```bash
python api.py
```
- **Interactive Web Cockpit:** `http://127.0.0.1:8000/`
- **Interactive Swagger Documentation:** `http://127.0.0.1:8000/docs`

### Automated Test Suite (`pytest`)
Run all **106 automated tests**:
```bash
python -m pytest tests/ -v
```
*Result: 106 passed in ~2.2s.*

---

## Author & Submission Details
- **Candidate:** Harsh Khamkar
- **Repository:** `harshkhamkar26/PL_agent`
- **Assessment:** AI Engineering Take-Home: Portfolio Analytics Agent
- **Organization:** PL Capital (Prabhudas Lilladher)
