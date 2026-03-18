"""
Reflector node: analyses the test failure and produces a revised patch.
Called only when tests failed and retries remain.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from app.state import AgentState
from app.schemas import PatcherOutput, ReflectorOutput, SearchReplaceEdit
from app.tools.llm import chat_structured
from app.tools.failure_parser import extract_failure_summary

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "reflector.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_previous_patch(patch: PatcherOutput) -> str:
    parts = [f"Overall reasoning: {patch.overall_reasoning}\n"]
    for i, edit in enumerate(patch.edits, 1):
        parts.append(f"Edit {i}: {edit.file_path}")
        parts.append(f"  Reasoning: {edit.reasoning}")
        parts.append(f"  search_text:\n    {edit.search_text!r}")
        parts.append(f"  replace_text:\n    {edit.replace_text!r}")
        parts.append("")
    return "\n".join(parts)


def _format_chunks(state: AgentState) -> str:
    lines = []
    for chunk in state.get("retrieved_chunks", []):
        lines.append(f"### {chunk.file_path} (lines {chunk.start_line}–{chunk.end_line})")
        lines.append("```")
        lines.append(chunk.content.rstrip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def reflector_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: produce a revised patch after test failure.

    Reads:  state["issue_text"], state["current_patch"], state["test_result"],
            state["retrieved_chunks"], state["retry_count"], state["retry_history"]
    Writes: state["current_patch"], state["retry_count"], state["retry_history"]
    """
    issue = state["issue_text"]
    current_patch = state["current_patch"]
    test_result = state["test_result"]
    retry_count = state.get("retry_count", 0)
    retry_history = list(state.get("retry_history", []))

    # Save current attempt to history before overwriting
    retry_history.append(
        {
            "attempt": retry_count,
            "patch": current_patch.model_dump() if current_patch else None,
            "test_result": test_result.model_dump() if test_result else None,
        }
    )

    # Parse failure output
    failure_summary = extract_failure_summary(
        stdout=test_result.stdout if test_result else "",
        stderr=test_result.stderr if test_result else "",
    )

    prev_patch_text = _format_previous_patch(current_patch) if current_patch else "(none)"
    chunks_context = _format_chunks(state)

    system_prompt = _load_prompt()
    user_message = (
        f"## Issue\n{issue}\n\n"
        f"## Previous Patch (attempt {retry_count})\n{prev_patch_text}\n\n"
        f"## Test Failure Summary\n{failure_summary}\n\n"
        f"## Original Source Code (unchanged)\n{chunks_context}\n\n"
        "Produce a corrected patch."
    )

    logger.info("Calling LLM for reflection (attempt %d)…", retry_count + 1)
    reflection: ReflectorOutput = chat_structured(
        system=system_prompt,
        user=user_message,
        response_model=ReflectorOutput,
    )
    logger.info("Reflection failure analysis: %s", reflection.failure_analysis[:200])

    # Convert ReflectorOutput → PatcherOutput so the rest of the graph is uniform
    revised_patch = PatcherOutput(
        edits=reflection.edits,
        overall_reasoning=reflection.revised_reasoning,
    )

    return {
        "current_patch": revised_patch,
        "retry_count": retry_count + 1,
        "retry_history": retry_history,
    }