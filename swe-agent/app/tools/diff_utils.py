"""
Generate unified diffs between original and modified content.
"""
from __future__ import annotations

import difflib


def generate_diff(original: str, modified: str, filepath: str = "file") -> str:
    """
    Return a unified diff string comparing *original* to *modified*.
    Returns an empty string if there are no differences.
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
            lineterm="",
        )
    )

    return "\n".join(diff)
