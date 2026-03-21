"""
Create and manage sandboxed copies of the repository.
The agent operates exclusively on the sandbox so the original repo is untouched.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from app.config import settings


def create_sandbox(repo_path: str) -> str:
    """
    Copy *repo_path* to a fresh temporary directory.
    Returns the absolute path to the sandbox root.
    """
    sandbox_base = Path(settings.sandbox_base_dir)
    sandbox_base.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    dest = sandbox_base / f"sandbox_{ts}"

    shutil.copytree(
        src=repo_path,
        dst=str(dest),
        symlinks=False,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
        ),
    )
    return str(dest)


def cleanup_sandbox(sandbox_path: str) -> None:
    """Remove the sandbox directory (call after the run if desired)."""
    try:
        shutil.rmtree(sandbox_path, ignore_errors=True)
    except Exception:
        pass