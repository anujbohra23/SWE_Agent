"""
Typed state for the LangGraph workflow.
Every node receives the full state dict and returns a partial update.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

from app.schemas import (
    CodeChunk,
    PlannerOutput,
    PatcherOutput,
    PatchApplyResult,
    TestResult,
    FinalReport,
)


class AgentState(TypedDict, total=False):
    # ---- inputs ----
    repo_path: str            # absolute path to the original repo
    issue_text: str           # raw issue / bug description
    test_command: str         # e.g. "pytest tests/ -v"
    max_retries: int          # max patch-retry cycles

    # ---- retrieval ----
    chunks: List[CodeChunk]              # all indexed chunks
    retrieved_chunks: List[CodeChunk]    # top-k relevant chunks
    retrieved_files: List[str]           # deduplicated file paths

    # ---- planning ----
    plan: Optional[PlannerOutput]

    # ---- patching ----
    current_patch: Optional[PatcherOutput]

    # ---- execution ----
    sandbox_path: str                    # path to sandbox copy
    patch_apply_result: Optional[PatchApplyResult]
    test_result: Optional[TestResult]

    # ---- retry loop ----
    retry_count: int
    retry_history: List[Dict[str, Any]]  # list of {patch, test_result} per attempt

    # ---- output ----
    final_report: Optional[FinalReport]
    error: Optional[str]                 # set if something fatal goes wrong