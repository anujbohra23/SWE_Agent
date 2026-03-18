"""
Patcher node: generates structured search/replace edits that fix the issue.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from app.state import AgentState
from app.schemas import PatcherOutput
from app.tools.llm import chat_structured

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "patcher.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_chunks(state: AgentState) -> str:
    lines = []
    for chunk in state.get("retrieved_chunks", []):
        lines.append(f"### {chunk.file_path} (lines {chunk.start_line}–{chunk.end_line})")
        lines.append("```")
        lines.append(chunk.content.rstrip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def patcher_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: produce a PatcherOutput (list of search/replace edits).

    Reads:  state["issue_text"], state["plan"], state["retrieved_chunks"]
    Writes: state["current_patch"]
    """
    issue = state["issue_text"]
    plan = state.get("plan")
    chunks_context = _format_chunks(state)

    plan_text = ""
    if plan:
        plan_text = (
            f"## Plan\nTarget files: {', '.join(plan.likely_files)}\n"
            f"Approach: {plan.approach}\n"
            f"Reasoning: {plan.reasoning}\n"
        )

    system_prompt = _load_prompt()
    user_message = (
        f"## Issue\n{issue}\n\n"
        f"{plan_text}\n"
        f"## Relevant Source Code\n{chunks_context}\n\n"
        "Generate the search/replace edits to fix this issue."
    )

    logger.info("Calling LLM for patch generation…")
    patch: PatcherOutput = chat_structured(
        system=system_prompt,
        user=user_message,
        response_model=PatcherOutput,
    )
    logger.info(
        "Patch generated: %d edit(s) across files: %s",
        len(patch.edits),
        [e.file_path for e in patch.edits],
    )

    return {"current_patch": patch}