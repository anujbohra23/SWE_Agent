"""
Pydantic schemas used as structured outputs for LLM calls and as
shared data structures across the pipeline.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Retrieval / ingestion
# ---------------------------------------------------------------------------

class CodeChunk(BaseModel):
    """A chunk of source code with provenance metadata."""
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str


# ---------------------------------------------------------------------------
# Planner output
# ---------------------------------------------------------------------------

class PlannerOutput(BaseModel):
    """Structured plan produced by the Planner node."""
    likely_files: List[str] = Field(
        description="Files most likely to need changes."
    )
    reasoning: str = Field(
        description="Short explanation of why those files are targeted."
    )
    approach: str = Field(
        description="High-level description of how to fix the issue."
    )


# ---------------------------------------------------------------------------
# Patch generation
# ---------------------------------------------------------------------------

class SearchReplaceEdit(BaseModel):
    """A single search-and-replace edit for one file."""
    file_path: str = Field(description="Relative path from repo root.")
    search_text: str = Field(
        description="Exact verbatim text to find in the file."
    )
    replace_text: str = Field(
        description="Text that replaces the matched search_text."
    )
    reasoning: str = Field(
        description="Why this change fixes the issue."
    )


class PatcherOutput(BaseModel):
    """All edits needed to fix the issue."""
    edits: List[SearchReplaceEdit] = Field(
        description="One or more search/replace edits."
    )
    overall_reasoning: str = Field(
        description="Summary of the fix strategy."
    )


# ---------------------------------------------------------------------------
# Reflector output
# ---------------------------------------------------------------------------

class ReflectorOutput(BaseModel):
    """Revised patch produced by the Reflector after a test failure."""
    edits: List[SearchReplaceEdit] = Field(
        description="Revised search/replace edits."
    )
    failure_analysis: str = Field(
        description="Analysis of what went wrong in the previous attempt."
    )
    revised_reasoning: str = Field(
        description="Why the new edits should work."
    )


# ---------------------------------------------------------------------------
# Patch application result
# ---------------------------------------------------------------------------

class EditResult(BaseModel):
    """Outcome of applying a single SearchReplaceEdit."""
    file_path: str
    success: bool
    error: Optional[str] = None


class PatchApplyResult(BaseModel):
    """Outcome of applying all edits in a patch."""
    edit_results: List[EditResult]
    diff: str  # unified diff of all changes
    any_failed: bool


# ---------------------------------------------------------------------------
# Test run result
# ---------------------------------------------------------------------------

class TestResult(BaseModel):
    """Outcome of a pytest run."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------

class FinalReport(BaseModel):
    """Structured final output returned to the caller."""
    success: bool
    retry_count: int
    planned_files: List[str]
    retrieved_files: List[str]
    final_diff: str
    final_test_output: str
    summary: str
    sandbox_path: str