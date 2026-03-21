"""
Split source files into line-based chunks suitable for embedding.

Strategy:
- For .py files: split on top-level function/class boundaries when possible,
  otherwise fall back to fixed-size windows.
- For all other files: fixed-size line windows with overlap.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import List

from app.schemas import CodeChunk

# Default window sizes (lines)
CHUNK_SIZE = 60
CHUNK_OVERLAP = 15

# Regex that matches a Python top-level def / class (no leading spaces)
TOP_LEVEL_DEF = re.compile(r"^(def |class )", re.MULTILINE)


def _make_chunk(file_path: str, lines: List[str], start: int, end: int) -> CodeChunk:
    """Build a CodeChunk from a slice of lines (1-indexed start/end)."""
    content = "".join(lines[start - 1 : end])
    chunk_id = str(uuid.uuid4())[:8]
    return CodeChunk(
        chunk_id=f"{file_path}:{start}-{end}:{chunk_id}",
        file_path=file_path,
        start_line=start,
        end_line=end,
        content=content,
    )


def _chunk_by_window(file_path: str, lines: List[str]) -> List[CodeChunk]:
    """Fixed-size sliding-window chunking."""
    chunks: List[CodeChunk] = []
    total = len(lines)
    start = 1
    while start <= total:
        end = min(start + CHUNK_SIZE - 1, total)
        chunks.append(_make_chunk(file_path, lines, start, end))
        if end == total:
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _chunk_python(file_path: str, lines: List[str]) -> List[CodeChunk]:
    """
    Attempt to split a Python file at top-level def/class boundaries.
    Falls back to window chunking if the file is very small or has
    no top-level definitions.
    """
    # Find indices (0-based) of top-level def/class lines
    boundary_indices = [
        i for i, line in enumerate(lines)
        if TOP_LEVEL_DEF.match(line)
    ]

    if len(boundary_indices) < 2:
        return _chunk_by_window(file_path, lines)

    chunks: List[CodeChunk] = []
    total = len(lines)

    for idx, boundary in enumerate(boundary_indices):
        start = boundary + 1  # convert to 1-indexed
        if idx + 1 < len(boundary_indices):
            end = boundary_indices[idx + 1]  # exclusive next boundary (0-based) → 1-indexed end
        else:
            end = total

        # If the logical block is too big, subdivide it
        block_lines = lines[start - 1 : end]
        if len(block_lines) <= CHUNK_SIZE * 2:
            chunks.append(_make_chunk(file_path, lines, start, end))
        else:
            # Window-chunk within this block
            sub_chunks = _chunk_by_window(file_path, block_lines)
            for sc in sub_chunks:
                # Re-offset line numbers to the file's coordinate space
                offset = start - 1
                chunks.append(
                    CodeChunk(
                        chunk_id=sc.chunk_id,
                        file_path=sc.file_path,
                        start_line=sc.start_line + offset,
                        end_line=sc.end_line + offset,
                        content=sc.content,
                    )
                )

    # Include any lines before the first boundary (module-level code / imports)
    if boundary_indices[0] > 0:
        preamble = _make_chunk(file_path, lines, 1, boundary_indices[0])
        chunks.insert(0, preamble)

    return chunks


def chunk_file(repo_path: str, relative_path: str) -> List[CodeChunk]:
    """
    Read *relative_path* inside *repo_path* and return chunks.
    Returns an empty list if the file cannot be read.
    """
    full_path = Path(repo_path) / relative_path
    try:
        text = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    if relative_path.endswith(".py"):
        return _chunk_python(relative_path, lines)
    else:
        return _chunk_by_window(relative_path, lines)


def chunk_all_files(repo_path: str, file_paths: List[str]) -> List[CodeChunk]:
    """Chunk every file in *file_paths* and return a flat list of chunks."""
    all_chunks: List[CodeChunk] = []
    for fp in file_paths:
        all_chunks.extend(chunk_file(repo_path, fp))
    return all_chunks