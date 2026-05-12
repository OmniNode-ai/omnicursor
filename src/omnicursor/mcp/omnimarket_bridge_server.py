"""MCP server exposing Omnimarket bridge tools to Cursor."""

from __future__ import annotations

import json
import uuid

from mcp.server.fastmcp import FastMCP

from omnicursor import omnimarket_bridge

mcp = FastMCP("omnicursor-omnimarket")


@mcp.tool(
    description=(
        "Run Omnimarket node_local_review via subprocess against a local checkout. "
        "Requires OMNIMARKET_ROOT env var or omnimarket-main/ in repo root."
    ),
)
def run_local_review(
    dry_run: bool = True,
    max_iterations: int = 10,
    required_clean_runs: int = 2,
) -> str:
    result = omnimarket_bridge.run_local_review(
        dry_run=dry_run,
        max_iterations=max_iterations,
        required_clean_runs=required_clean_runs,
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    description=(
        "Run the full autonomous ticket pipeline for a Linear ticket via Omnimarket "
        "node_ticket_pipeline. Drives: IMPLEMENT → LOCAL_REVIEW → CREATE_PR → "
        "TEST_ITERATE → CI_WATCH → PR_REVIEW → AUTO_MERGE → DONE. "
        "Returns final_phase and pr_number. Timeout: 10 minutes. "
        "Requires OMNIMARKET_ROOT env var."
    ),
)
def run_ticket_pipeline(
    ticket_id: str,
    skip_test_iterate: bool = False,
    dry_run: bool = False,
) -> str:
    """ticket_id: Linear ticket ID e.g. 'OMN-42'."""
    result = omnimarket_bridge.run_ticket_pipeline(
        ticket_id=ticket_id,
        skip_test_iterate=skip_test_iterate,
        dry_run=dry_run,
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    description=(
        "Watch GitHub Actions CI for a PR and auto-fix failures via Omnimarket "
        "node_ci_watch. Polls until CI passes, fails, or times out. "
        "Returns terminal_status (passed/failed/timeout), failed_checks, and "
        "failure_summary. Requires OMNIMARKET_ROOT and gh CLI in PATH."
    ),
)
def run_ci_watch(
    pr_number: int,
    repo: str,
    timeout_minutes: int = 60,
    max_fix_cycles: int = 3,
    dry_run: bool = False,
) -> str:
    """repo: GitHub slug e.g. 'OmniNode-ai/OmniCursor'."""
    result = omnimarket_bridge.run_ci_watch(
        pr_number=pr_number,
        repo=repo,
        correlation_id=str(uuid.uuid4()),
        timeout_minutes=timeout_minutes,
        max_fix_cycles=max_fix_cycles,
        dry_run=dry_run,
    )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
