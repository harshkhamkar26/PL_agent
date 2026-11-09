"""
Main Command-Line Interface for PL Capital Portfolio Analytics Agent.
Supports positional CLI queries, flag-based queries, 10-question evaluation benchmarks,
and an interactive terminal with conversational GPT assistant capabilities.
"""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.portfolio_agent import PortfolioAgent
from evaluation.evaluator import AgentEvaluator

# Vercel / PaaS automatic FastAPI entrypoint compatibility
try:
    from api import app as app
except ImportError:
    pass


def clean_query_string(q: str) -> str:
    """Strips leading/trailing quotes that may be introduced via command shells."""
    cleaned = q.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def print_cli_banner():
    """Renders the institutional PL Capital terminal banner."""
    print("=" * 76)
    print("  PL CAPITAL // PORTFOLIO ANALYTICS INTELLIGENCE AGENT (CLI)")
    print("  Prabhudas Lilladher Capital • Institutional Financial AI Copilot (Est. 1944)")
    print("=" * 76)
    print("  [Commands] 'eval': Run Benchmark | 'portfolios': List Funds | 'status': Check Health")
    print("             'whoami': Agent Info  | 'help': View Examples    | 'exit': Quit Terminal\n")


def print_help_menu():
    """Prints guidance and sample prompts across all categories."""
    print("\n--- [PL Capital CLI Intelligence Guide] ---")
    print("You can ask ANY question in natural language (Financial, Quant, or Conversational):\n")
    print("1. Canonical Evaluation Prompts:")
    print("   • How many portfolios do we have in total?")
    print("   • What are the names of all active portfolios?")
    print("   • Which securities are in the Technology sector?")
    print("   • What is the total Assets Under Management (AUM) for portfolios with high target risk level?")
    print("   • Show me the top 5 holdings by cost basis in the Growth Equity Fund")
    print("   • What is the average current price of securities in each sector?")
    print("   • What are the sector exposures for the Tech Innovation Fund?\n")
    print("2. Arbitrary Financial Inquiries:")
    print("   • Show all bonds")
    print("   • Which portfolios hold Apple?")
    print("   • Show portfolios with AUM greater than 20 million")
    print("   • Which portfolios have the highest Sharpe ratio?")
    print("   • Show recent buy orders\n")
    print("3. Agent Wellbeing & GPT Persona Prompts:")
    print("   • Who are you?")
    print("   • How is your wellbeing?")
    print("   • What can you do?")
    print("   • How do you partition bonds from equity exposure?")
    print("   • Explain your AST security guardrails\n")


def run_interactive():
    """Runs interactive conversational CLI loop."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print_cli_banner()
    agent = PortfolioAgent()

    try:
        while True:
            try:
                user_input = input("PL-Agent> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSession ended.")
                break

            if not user_input:
                continue

            cleaned = clean_query_string(user_input)
            cmd = cleaned.lower()

            if cmd in {"exit", "quit", "q", ":q"}:
                print("Exiting PL Capital agent session. Goodbye.")
                break

            if cmd in {"help", "?", "--help"}:
                print_help_menu()
                continue

            if cmd in {"eval", "evaluate", "benchmark", "test"}:
                print("\nExecuting 10-Question Ground Truth Benchmark...")
                evaluator = AgentEvaluator()
                summary = evaluator.evaluate_all()
                print(f"Results: {summary['passed_questions']}/{summary['total_questions']} Passed ({summary['accuracy_pct']}%)")
                print(f"Average Latency: {summary['avg_latency_ms']} ms (P50: {summary['p50_latency_ms']} ms, P95: {summary['p95_latency_ms']} ms)")
                verdict = summary.get("regression_status", {}).get("message", "100% PASS - Zero Regression")
                print(f"Regression Guard: {verdict}\n")
                continue

            if cmd in {"portfolios", "funds", "list"}:
                res = agent.answer_question("What are the names of all active portfolios?")
                print("\n" + res["formatted_markdown"] + "\n")
                continue

            if cmd in {"whoami", "about"}:
                res = agent.answer_question("Who are you?")
                print("\n" + res["formatted_markdown"] + "\n")
                continue

            if cmd in {"status", "health", "wellbeing", "vitals"}:
                res = agent.answer_question("What is your current system status and wellbeing?")
                print("\n" + res["formatted_markdown"] + "\n")
                continue

            # Process query
            res = agent.answer_question(cleaned)
            print("\n" + res["formatted_markdown"] + "\n")

    finally:
        agent.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="PL Capital Portfolio Analytics Agent CLI",
        epilog="Examples:\n"
               "  python main.py \"How many portfolios do we have in total?\"\n"
               "  python main.py \"Who are you?\"\n"
               "  python main.py --query \"Show all bonds\"\n"
               "  python main.py --eval\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="*", help="Natural language inquiry or command (positional argument)")
    parser.add_argument("--query", "-q", type=str, help="Single-shot natural language query to execute")
    parser.add_argument("--eval", "-e", action="store_true", help="Run the 10-question ground truth evaluation benchmark")
    parser.add_argument("--eval-regression", "--regression", action="store_true", help="Run the 23-question expanded regression benchmark suite")

    args = parser.parse_args()

    # Evaluation Mode (Official 10 Canonical Questions)
    if args.eval:
        print("Executing official 10-question evaluation benchmark...")
        evaluator = AgentEvaluator()
        summary = evaluator.evaluate_all()
        verdict = summary.get("regression_status", {}).get("message", "100% PASS - Zero Regression")
        print(f"Verdict: {verdict}")
        print(f"Accuracy: {summary['passed_questions']}/{summary['total_questions']} Passed ({summary['accuracy_pct']}%)")
        print(f"Average Latency: {summary['avg_latency_ms']} ms")
        sys.exit(0 if summary["accuracy_pct"] == 100.0 else 1)

    # Expanded Regression Mode (23 Expanded Questions)
    if args.eval_regression:
        import json
        reg_path = BASE_DIR / "evaluation" / "regression_questions.json"
        print("Executing 23-question expanded regression benchmark suite...")
        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        questions = data.get("questions", [])
        agent = PortfolioAgent()
        passed = 0
        print("-" * 75)
        for q_item in questions:
            qid = q_item["id"]
            qtext = q_item["question"]
            res = agent.answer_question(qtext)
            ok = bool(res and res.get("direct_answer"))
            if q_item.get("expected_tool") and res["selected_tool"] != q_item["expected_tool"]:
                ok = False
            if q_item.get("expected_record_count") and isinstance(res.get("evidence"), list):
                if len(res["evidence"]) != q_item["expected_record_count"]:
                    ok = False
            if ok:
                passed += 1
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {qid:<3s} | Tool: {res['selected_tool']:<22s} | {qtext[:42]}...")
        print("-" * 75)
        agent.close()
        acc = round((passed / len(questions)) * 100.0, 1)
        print(f"Regression Accuracy: {passed}/{len(questions)} Passed ({acc}%)")
        sys.exit(0 if acc == 100.0 else 1)

    # Resolve query from either --query flag or positional arguments
    query_str = ""
    if args.query:
        query_str = args.query.strip()
    elif args.prompt:
        query_str = " ".join(args.prompt).strip()

    if query_str:
        cleaned = clean_query_string(query_str)
        agent = PortfolioAgent()
        res = agent.answer_question(cleaned)
        print(res["formatted_markdown"])
        agent.close()
        return

    # Default to Interactive Mode
    run_interactive()


if __name__ == "__main__":
    main()
