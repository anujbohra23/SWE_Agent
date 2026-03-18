"""
Reporter node: assembles the FinalReport from all state data.
This is the terminal node of the graph.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.state import AgentState
from app.schemas import FinalReport
from app.tools.llm import chat

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM = (
    "You are a helpful software engineering assistant. "
    "Write a concise one-paragraph summary of an automated code fix attempt."
)


def _build_summary(state: AgentState, success: bool) -> str:
    """Ask the LLM to write a human-readable summary of the run."""
    plan = state.get("plan")
    test_result = state.get("test_result")
    retry_count = state.get("retry_count", 0)
    patch = state.get("current_patch")

    details = (
        f"Issue: {state['issue_text'][:300]}\n"
        f"Planned files: {plan.likely_files if plan else []}\n"
        f"Retries: {retry_count}\n"
        f"Outcome: {'PASSED' if success else 'FAILED'}\n"
        f"Patch strategy: {patch.overall_reasoning[:300] if patch else 'none'}\n"
        f"Test output tail: {(test_result.stdout or '')[-500:] if test_result else ''}"
    )

    try:
        return chat(system=_SUMMARY_SYSTEM, user=details)
    except Exception as e:
        logger.warning("Summary LLM call failed: %s", e)
        status = "successfully fixed" if success else "could not fix"
        return f"The agent {status} the issue after {retry_count} retry attempt(s)."


def reporter_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: produce the FinalReport.

    Reads: all state fields
    Writes: state["final_report"]
    """
    test_result = state.get("test_result")
    patch_apply = state.get("patch_apply_result")
    success = bool(test_result and test_result.success)

    final_diff = (patch_apply.diff if patch_apply else "") or ""
    final_test_output = ""
    if test_result:
        final_test_output = (test_result.stdout + "\n" + test_result.stderr).strip()

    plan = state.get("plan")
    planned_files = plan.likely_files if plan else []
    retrieved_files = state.get("retrieved_files", [])

    logger.info("Building final report (success=%s)…", success)
    summary = _build_summary(state, success)

    report = FinalReport(
        success=success,
        retry_count=state.get("retry_count", 0),
        planned_files=planned_files,
        retrieved_files=retrieved_files,
        final_diff=final_diff,
        final_test_output=final_test_output,
        summary=summary,
        sandbox_path=state.get("sandbox_path", ""),
    )

    return {"final_report": report}