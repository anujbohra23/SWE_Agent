"""
Planner node: given the issue and retrieved chunks, decide which files
to target and write a short fix plan.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from app.state import AgentState
from app.schemas import PlannerOutput
from app.tools.llm import chat_structured

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_chunks(state: AgentState) -> str:
    """Format retrieved chunks into a readable context block."""
    lines = []
    for chunk in state.get("retrieved_chunks", []):
        lines.append(f"### {chunk.file_path} (lines {chunk.start_line}–{chunk.end_line})")
        lines.append("```python")
        lines.append(chunk.content.rstrip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: produce a structured plan.

    Reads:  state["issue_text"], state["retrieved_chunks"]
    Writes: state["plan"]
    """
    issue = state["issue_text"]
    chunks_context = _format_chunks(state)

    system_prompt = _load_prompt()
    user_message = (
        f"## Issue\n{issue}\n\n"
        f"## Retrieved Code Chunks\n{chunks_context}\n\n"
        "Based on the issue and the code above, produce a structured plan."
    )

    logger.info("Calling LLM for plan…")
    plan: PlannerOutput = chat_structured(
        system=system_prompt,
        user=user_message,
        response_model=PlannerOutput,
    )
    logger.info("Plan: target files = %s", plan.likely_files)

    return {"plan": plan}