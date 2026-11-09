# PL Capital Portfolio Analytics Agent - Official Evaluation Report
**Generated:** 2026-11-09T22:09:50.090989  
**Overall Accuracy:** `100.0%` (10/10 Passed)  
**Tool Routing Accuracy:** `100.0%`  
**Evidence Completeness Score:** `100.0%`  
**Average Query Latency:** `3.64 ms` (P50: `2.46 ms`, P95: `7.67 ms)  
**Regression Guard:** `PASS_NO_REGRESSION` (Accuracy matched or exceeded baseline (100.0% >= 100.0%).)  

## Benchmark Results (All 10 Questions)

| ID | Type | Difficulty | Question | Tool Selected | Routing | Result | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Q1 | `text2sql` | easy | How many portfolios do we have in total? | `sql_query_tool` | PASS | **PASS** | 2.28 |
| Q2 | `text2sql` | easy | What are the names of all active portfolios? | `sql_query_tool` | PASS | **PASS** | 2.24 |
| Q3 | `text2sql` | easy | Which securities are in the Technology sector? | `sql_query_tool` | PASS | **PASS** | 2.46 |
| Q4 | `text2sql` | medium | What is the total Assets Under Management (AUM) for portfolios with high target risk level? | `sql_query_tool` | PASS | **PASS** | 2.35 |
| Q5 | `text2sql` | medium | Show me the top 5 holdings by cost basis in the Growth Equity Fund | `sql_query_tool` | PASS | **PASS** | 3.31 |
| Q6 | `text2sql` | medium | What is the average current price of securities in each sector? | `sql_query_tool` | PASS | **PASS** | 3.38 |
| Q7 | `text2sql` | hard | For each portfolio, show the total value of Technology sector holdings and what percentage it represents of the total portfolio value | `sql_query_tool` | PASS | **PASS** | 7.67 |
| Q8 | `text2sql` | hard | Find portfolios that have holdings in more than 5 different sectors and show their diversification metrics | `sql_query_tool` | PASS | **PASS** | 6.21 |
| Q9 | `exposure_calculator` | medium | What are the sector exposures for the Tech Innovation Fund? | `exposure_calculator` | PASS | **PASS** | 1.38 |
| Q10 | `exposure_calculator` | medium | Calculate the sector exposure breakdown for international equity | `exposure_calculator` | PASS | **PASS** | 1.3 |

## Financial Integrity Verification
- **Fixed-Income Partitioning:** Confirmed bond exclusion in equity sector exposure.
- **Cash Buffer Auditing:** Detected and disclosed 2% unallocated weight in Portfolio 11 (`Total Stock Market Index Fund`).
- **AST Safety Guardrails:** 100% of generated queries passed read-only validation without administrative exposure.
- **Query Plan Profiling:** Validated that relational joins utilized composite indexes without redundant table scans.