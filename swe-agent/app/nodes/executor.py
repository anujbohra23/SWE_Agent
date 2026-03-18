"""
Executor node: creates (or resets) the sandbox, applies the current patch,
and runs the test suite.
"""
from __future__ import annotations

import logging
import shutil
from typing import Any, Dict

from app.state import AgentState
from app.tools.sandbox import create_sandbox
from app.tools.patch_apply import apply_patch
from app.tools.test_runner import run_tests

logger = logging.getLogger(__name__)


def executor_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node:
    1. On first attempt: create a fresh sandbox copy of the repo.
       On retry: reset the sandbox from the original repo.
    2. Apply the current patch.
    3. Run tests.

    Reads:  state["repo_path"], state["current_patch"], state["test_command"],
            state["sandbox_path"] (may not exist yet), state["retry_count"]
    Writes: state["sandbox_path"], state["patch_apply_result"], state["test_result"]
    """
    repo_path = state["repo_path"]
    test_command = state["test_command"]
    current_patch = state.get("current_patch")
    retry_count = state.get("retry_count", 0)

    # --- Manage sandbox ---
    existing_sandbox = state.get("sandbox_path", "")
    if existing_sandbox:
        # Reset sandbox to a clean copy of the original repo for this retry
        logger.info("Resetting sandbox for retry %d…", retry_count)
        try:
            shutil.rmtree(existing_sandbox, ignore_errors=True)
        except Exception:
            pass

    logger.info("Creating fresh sandbox from %s…", repo_path)
    sandbox_path = create_sandbox(repo_path)
    logger.info("Sandbox at: %s", sandbox_path)

    # --- Apply patch ---
    if current_patch is None:
        logger.error("No patch available — skipping apply.")
        return {
            "sandbox_path": sandbox_path,
            "patch_apply_result": None,
            "test_result": None,
        }

    logger.info("Applying patch (%d edit(s))…", len(current_patch.edits))
    apply_result = apply_patch(sandbox_path, current_patch)

    failed_edits = [r for r in apply_result.edit_results if not r.success]
    if failed_edits:
        logger.warning(
            "%d edit(s) failed to apply: %s",
            len(failed_edits),
            [(r.file_path, r.error) for r in failed_edits],
        )

    # --- Run tests ---
    logger.info("Running tests: %s", test_command)
    test_result = run_tests(sandbox_path, test_command)
    logger.info(
        "Tests finished: success=%s exit_code=%d duration=%.1fs",
        test_result.success,
        test_result.exit_code,
        test_result.duration_seconds,
    )

    return {
        "sandbox_path": sandbox_path,
        "patch_apply_result": apply_result,
        "test_result": test_result,
    }