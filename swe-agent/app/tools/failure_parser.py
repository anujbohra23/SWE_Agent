"""
Parse pytest output to extract a concise failure summary.
Feeds into the Reflector node so the LLM knows what went wrong.
"""
from __future__ import annotations

import re
from typing import List


# Patterns that mark the start of useful failure sections in pytest output
_FAILURE_HEADER = re.compile(r"^(FAILED|ERROR|_+\s*(FAILURES|ERRORS)\s*_+)", re.MULTILINE)
_SHORT_TEST_SUMMARY = re.compile(r"=+ short test summary info =+", re.MULTILINE)
_TRACEBACK_LINE = re.compile(r"^\s*(File \".*\", line \d+|E\s+.+|AssertionError|.*Error:.*)", re.MULTILINE)


def extract_failure_summary(stdout: str, stderr: str, max_chars: int = 3000) -> str:
    """
    Return a condensed failure summary from pytest stdout/stderr.
    Tries to include:
    - The "short test summary info" block
    - The last traceback / error section
    - Any AssertionError lines
    """
    combined = stdout + "\n" + stderr
    lines = combined.splitlines()

    # --- Grab short test summary block ---
    summary_lines: List[str] = []
    in_summary = False
    for line in lines:
        if _SHORT_TEST_SUMMARY.match(line):
            in_summary = True
        if in_summary:
            summary_lines.append(line)
            if len(summary_lines) > 30:
                break

    # --- Grab last FAILED/ERROR section ---
    section_starts = [i for i, l in enumerate(lines) if _FAILURE_HEADER.match(l)]
    last_section: List[str] = []
    if section_starts:
        start_idx = section_starts[-1]
        last_section = lines[start_idx : start_idx + 60]

    # Combine unique lines
    seen: set[str] = set()
    result_lines: List[str] = []
    for line in (last_section + summary_lines):
        if line not in seen:
            seen.add(line)
            result_lines.append(line)

    # Fallback: just return the tail of combined output
    if not result_lines:
        tail_lines = lines[-80:]
        result_lines = tail_lines

    summary = "\n".join(result_lines)

    # Truncate to max_chars, keeping the end (most recent info is most useful)
    if len(summary) > max_chars:
        summary = "...(truncated)...\n" + summary[-(max_chars - 20):]

    return summary.strip()