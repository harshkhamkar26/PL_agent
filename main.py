"""
Main Command-Line Interface for PL Capital Portfolio Analytics Agent.
Supports interactive conversational loop, single-shot execution, and evaluation benchmark.
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


def run_interactive():
    """Runs interactive CLI loop."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 70)
    print("  PL CAPITAL - PORTFOLIO ANALYTICS INTELLIGENCE AGENT")
    print("  Evidence-Grounded Financial Question Answering System")
    print("=" * 70)
    print("Commands: 'eval' to run benchmark | 'portfolios' to list funds | 'exit' to quit\n")

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

            cmd = user_input.lower()
            if cmd in {"exit", "quit", "q"}:
                print("Exiting agent session. Goodbye.")
                break

            if cmd in {"eval", "evaluate", "test"}:
                print("\nExecuting 10-Question Ground Truth Benchmark...")
                evaluator = AgentEvaluator()
                summary = evaluator.evaluate_all()
                print(f"Results: {summary['passed_questions']}/{summary['total_questions']} Passed ({summary['accuracy_pct']}%)")
                print(f"Average Latency: {summary['avg_latency_ms']} ms\n")
                continue

            if cmd in {"portfolios", "funds", "list"}:
                res = agent.answer_question("What are the names of all active portfolios?")
                print("\n" + res["formatted_markdown"] + "\n")
                continue

            print("\nAnalyzing query...")
            res = agent.answer_question(user_input)
            print("\n" + res["formatted_markdown"] + "\n")

    finally:
        agent.close()


def main():
    parser = argparse.ArgumentParser(description="PL Capital Portfolio Analytics Agent CLI")
    parser.add_argument("--query", "-q", type=str, help="Single-shot natural language query to execute")
    parser.add_argument("--eval", "-e", action="store_true", help="Run the 10-question ground truth evaluation")

    args = parser.parse_args()

    if args.eval:
        evaluator = AgentEvaluator()
        summary = evaluator.evaluate_all()
        print(f"Passed: {summary['passed_questions']}/{summary['total_questions']} ({summary['accuracy_pct']}%)")
        sys.exit(0 if summary["accuracy_pct"] == 100.0 else 1)

    if args.query:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        agent = PortfolioAgent()
        res = agent.answer_question(args.query)
        print(res["formatted_markdown"])
        agent.close()
        return

    run_interactive()


if __name__ == "__main__":
    main()
