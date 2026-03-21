"""
Apply structured search/replace edits to files in the sandbox.

Each edit specifies:
  - file_path  (relative to sandbox root)
  - search_text
  - replace_text

The function validates the file exists, finds the exact search_text,
replaces the first occurrence, and records success/failure per edit.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.schemas import PatcherOutput, PatchApplyResult, EditResult, SearchReplaceEdit
from app.tools.diff_utils import generate_diff


def apply_patch(sandbox_path: str, patch: PatcherOutput) -> PatchApplyResult:
    """
    Apply all edits in *patch* to files inside *sandbox_path*.
    Returns a PatchApplyResult with per-edit outcomes and a unified diff.
    """
    sandbox = Path(sandbox_path)
    edit_results: List[EditResult] = []

    # Keep original contents for diff generation
    originals: dict[str, str] = {}
    modified: dict[str, str] = {}

    for edit in patch.edits:
        result = _apply_single_edit(sandbox, edit, originals, modified)
        edit_results.append(result)

    # Generate a combined diff
    diff_parts: List[str] = []
    for fp, orig in originals.items():
        new = modified.get(fp, orig)
        diff_parts.append(generate_diff(orig, new, fp))
    combined_diff = "\n".join(diff_parts)

    any_failed = any(not r.success for r in edit_results)
    return PatchApplyResult(
        edit_results=edit_results,
        diff=combined_diff,
        any_failed=any_failed,
    )


def _apply_single_edit(
    sandbox: Path,
    edit: SearchReplaceEdit,
    originals: dict[str, str],
    modified: dict[str, str],
) -> EditResult:
    """
    Apply one SearchReplaceEdit.  Mutates *originals* and *modified* dicts.
    Returns an EditResult indicating success or failure.
    """
    target = sandbox / edit.file_path

    if not target.exists():
        return EditResult(
            file_path=edit.file_path,
            success=False,
            error=f"File not found: {edit.file_path}",
        )

    # Cache original content
    if edit.file_path not in originals:
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return EditResult(file_path=edit.file_path, success=False, error=str(e))
        originals[edit.file_path] = content
        # Start modified from original (or previous successful edit in same file)
        modified[edit.file_path] = content

    current_content = modified[edit.file_path]

    if edit.search_text not in current_content:
        # Try a whitespace-normalised match as fallback
        normalised_search = _normalise_whitespace(edit.search_text)
        normalised_content = _normalise_whitespace(current_content)
        if normalised_search in normalised_content:
            # Reconstruct: find the line range and do a line-level replacement
            new_content = _line_level_replace(current_content, edit.search_text, edit.replace_text)
            if new_content is None:
                return EditResult(
                    file_path=edit.file_path,
                    success=False,
                    error="search_text not found in file (even after whitespace normalisation).",
                )
            modified[edit.file_path] = new_content
            target.write_text(new_content, encoding="utf-8")
            return EditResult(file_path=edit.file_path, success=True)
        else:
            return EditResult(
                file_path=edit.file_path,
                success=False,
                error="search_text not found in file.",
            )

    # Exact match — replace first occurrence
    new_content = current_content.replace(edit.search_text, edit.replace_text, 1)
    modified[edit.file_path] = new_content
    try:
        target.write_text(new_content, encoding="utf-8")
    except OSError as e:
        return EditResult(file_path=edit.file_path, success=False, error=str(e))

    return EditResult(file_path=edit.file_path, success=True)


def _normalise_whitespace(text: str) -> str:
    """Collapse all whitespace sequences to a single space."""
    import re
    return re.sub(r"\s+", " ", text).strip()


def _line_level_replace(content: str, search: str, replacement: str) -> str | None:
    """
    Fallback: try to match search stripped of leading/trailing blank lines,
    then replace those lines in the original content.
    """
    search_lines = search.strip().splitlines()
    content_lines = content.splitlines(keepends=True)

    for i in range(len(content_lines) - len(search_lines) + 1):
        window = [l.rstrip() for l in content_lines[i : i + len(search_lines)]]
        if window == [l.rstrip() for l in search_lines]:
            new_lines = (
                content_lines[:i]
                + [replacement if replacement.endswith("\n") else replacement + "\n"]
                + content_lines[i + len(search_lines) :]
            )
            return "".join(new_lines)
    return None