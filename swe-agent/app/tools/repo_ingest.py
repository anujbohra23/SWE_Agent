"""
Repository ingestion: recursively walk the repo and collect
file paths that are worth indexing, skipping noise directories.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Directories to skip entirely
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".tox",
    "*.egg-info",
    "htmlcov",
    ".coverage",
}

# File extensions to include
INCLUDE_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".cfg",
    ".ini",
    ".rst",
}

# Hard size limit per file (bytes) — skip huge generated files
MAX_FILE_SIZE = 500_000


def should_ignore_dir(dirname: str) -> bool:
    """Return True if this directory name should be skipped."""
    return dirname in IGNORE_DIRS or dirname.endswith(".egg-info")


def ingest_repo(repo_path: str) -> List[str]:
    """
    Walk *repo_path* and return a list of relative file paths
    (relative to repo_path) that should be indexed.
    """
    repo_root = Path(repo_path).resolve()
    result: List[str] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune ignored directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if not should_ignore_dir(d)]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext not in INCLUDE_EXTENSIONS:
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            if size > MAX_FILE_SIZE:
                continue

            # Store as path relative to repo root
            relative = str(filepath.relative_to(repo_root))
            result.append(relative)

    return sorted(result)