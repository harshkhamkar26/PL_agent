# PL Capital Portfolio Analytics Agent - Official Evaluation Report
**Generated:** 2026-11-09T22:02:46.394777  
**Overall Accuracy:** `100.0%` (10/10 Passed)  
**Tool Routing Accuracy:** `100.0%`  
**Evidence Completeness Score:** `100.0%`  
**Average Query Latency:** `5.4 ms` (P50: `3.53 ms`, P95: `13.46 ms)  
**Regression Guard:** `PASS_NO_REGRESSION` (Accuracy matched or exceeded baseline (100.0% >= 100.0%).)  

## Benchmark Results (All 10 Questions)

| ID | Type | Difficulty | Question | Tool Selected | Routing | Result | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Q1 | `text2sql` | easy | How many portfolios do we have in total? | `sql_query_tool` | PASS | **PASS** | 13.46 |
| Q2 | `text2sql` | easy | What are the names of all active portfolios? | `sql_query_tool` | PASS | **PASS** | 3.07 |
| Q3 | `text2sql` | easy | Which securities are in the Technology sector? | `sql_query_tool` | PASS | **PASS** | 3.39 |
| Q4 | `text2sql` | medium | What is the total Assets Under Management (AUM) for portfolios with high target risk level? | `sql_query_tool` | PASS | **PASS** | 3.06 |
| Q5 | `text2sql` | medium | Show me the top 5 holdings by cost basis in the Growth Equity Fund | `sql_query_tool` | PASS | **PASS** | 3.89 |
| Q6 | `text2sql` | medium | What is the average current price of securities in each sector? | `sql_query_tool` | PASS | **PASS** | 3.53 |
| Q7 | `text2sql` | hard | For each portfolio, show the total value of Technology sector holdings and what percentage it represents of the total portfolio value | `sql_query_tool` | PASS | **PASS** | 8.0 |
| Q8 | `text2sql` | hard | Find portfolios that have holdings in more than 5 different sectors and show their diversification metrics | `sql_query_tool` | PASS | **PASS** | 7.42 |
| Q9 | `exposure_calculator` | medium | What are the sector exposures for the Tech Innovation Fund? | `exposure_calculator` | PASS | **PASS** | 1.79 |
| Q10 | `exposure_calculator` | medium | Calculate the sector exposure breakdown for international equity | `exposure_calculator` | PASS | **PASS** | 1.6 |

## Financial Integrity Verification
- **Fixed-Income Partitioning:** Confirmed bond exclusion in equity sector exposure.
- **Cash Buffer Auditing:** Detected and disclosed 2% unallocated weight in Portfolio 11 (`Total Stock Market Index Fund`).
- **AST Safety Guardrails:** 100% of generated queries passed read-only validation without administrative exposure.
- **Query Plan Profiling:** Validated that relational joins utilized composite indexes without redundant table scans.