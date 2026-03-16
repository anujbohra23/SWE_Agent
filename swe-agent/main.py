#!/usr/bin/env python3
"""
SWE-Agent CLI entry point.

Usage:
    python main.py \\
        --repo data/demo_repo \\
        --issue "The add_numbers function returns wrong results for negative inputs." \\
        --test-cmd "pytest tests/ -v"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Load .env before importing app modules so settings are populated
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

# Initialise logging before app imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("swe-agent")

# Suppress noisy third-party loggers
for _noisy in ("httpx", "httpcore", "huggingface_hub", "sentence_transformers",
               "faiss", "urllib3", "openai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

from app.config import settings
from app.graph import build_graph

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SWE-Agent: autonomous software engineering agent"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the local Python repository to fix.",
    )
    parser.add_argument(
        "--issue",
        required=True,
        help="Issue / bug description (GitHub-style).",
    )
    parser.add_argument(
        "--test-cmd",
        default="pytest tests/ -v",
        help="Test command to run (default: 'pytest tests/ -v').",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=settings.max_retries,
        help=f"Max patch-retry cycles (default: {settings.max_retries}).",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory to write JSON run logs (default: logs/).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress rich output; print only the final JSON report.",
    )
    return parser.parse_args()


def validate_repo(repo_path: str) -> str:
    """Resolve and validate the repo path."""
    p = Path(repo_path).resolve()
    if not p.exists():
        console.print(f"[red]Error:[/red] Repository path does not exist: {p}")
        sys.exit(1)
    if not p.is_dir():
        console.print(f"[red]Error:[/red] Repository path is not a directory: {p}")
        sys.exit(1)
    return str(p)


def save_log(log_dir: str, state: dict) -> str:
    """Serialize state to a JSON log file and return the path."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    filename = log_path / f"run_{ts}.json"

    # Make state JSON-serialisable
    def default_serialiser(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return str(obj)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=default_serialiser)

    return str(filename)


def print_report(report, quiet: bool) -> None:
    """Pretty-print the final report using Rich."""
    if quiet:
        print(json.dumps(report.model_dump(), indent=2))
        return

    status_colour = "green" if report.success else "red"
    status_text = "✅ FIXED" if report.success else "❌ NOT FIXED"

    console.print()
    console.print(Panel(
        f"[bold {status_colour}]{status_text}[/bold {status_colour}]  "
        f"(retries: {report.retry_count})",
        title="SWE-Agent Result",
        expand=False,
    ))

    console.print(f"\n[bold]Summary:[/bold] {report.summary}\n")
    console.print(f"[bold]Planned files:[/bold] {', '.join(report.planned_files) or '(none)'}")
    console.print(f"[bold]Retrieved files:[/bold] {', '.join(report.retrieved_files[:10]) or '(none)'}")
    console.print(f"[bold]Sandbox:[/bold] {report.sandbox_path}\n")

    if report.final_diff:
        console.print("[bold]Diff:[/bold]")
        console.print(Syntax(report.final_diff, "diff", theme="monokai", line_numbers=False))
        console.print()

    console.print("[bold]Test Output (tail):[/bold]")
    tail = "\n".join(report.final_test_output.splitlines()[-40:])
    console.print(Panel(tail, expand=False))


def main() -> None:
    args = parse_args()
    repo_path = validate_repo(args.repo)

    if not args.quiet:
        console.print(Panel(
            f"[bold]Repo:[/bold] {repo_path}\n"
            f"[bold]Issue:[/bold] {args.issue}\n"
            f"[bold]Test cmd:[/bold] {args.test_cmd}\n"
            f"[bold]Max retries:[/bold] {args.max_retries}",
            title="🤖 SWE-Agent Starting",
        ))

    # Build initial state
    initial_state = {
        "repo_path": repo_path,
        "issue_text": args.issue,
        "test_command": args.test_cmd,
        "max_retries": args.max_retries,
        "retry_count": 0,
        "retry_history": [],
    }

    # Run graph
    graph = build_graph()
    logger.info("Graph compiled. Starting run…")

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        logger.exception("Graph execution failed: %s", e)
        console.print(f"[red]Fatal error during agent run:[/red] {e}")
        sys.exit(1)

    # Save log
    log_file = save_log(args.log_dir, final_state)
    if not args.quiet:
        console.print(f"\n[dim]Full log saved to: {log_file}[/dim]")

    # Print report
    report = final_state.get("final_report")
    if report is None:
        console.print("[red]No final report produced.[/red]")
        sys.exit(1)

    print_report(report, args.quiet)

    # Exit code mirrors test success
    sys.exit(0 if report.success else 1)


if __name__ == "__main__":
    main()