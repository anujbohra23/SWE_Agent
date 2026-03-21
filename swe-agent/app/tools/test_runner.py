"""
Run a test command inside the sandbox directory and capture the outcome.

Strategy:
- Run `pip install -e .` to pull the package's dependencies into the venv.
- Set PYTHONPATH=sandbox/src:sandbox so the patched sandbox source takes
  priority over the installed package (PYTHONPATH beats site-packages).
- This means deps (markupsafe, werkzeug, etc.) come from the venv,
  but the actual package source comes from the patched sandbox.
"""
from __future__ import annotations

import os
import subprocess
import time
import logging
from pathlib import Path

from app.config import settings
from app.schemas import TestResult

logger = logging.getLogger(__name__)


def _install_deps(sandbox: Path, timeout: int) -> None:
    """
    Install the package (and its dependencies) into the current venv.
    This ensures all third-party deps like markupsafe, werkzeug, etc. are present.
    We don't care that it also installs the package itself — PYTHONPATH will
    override it with the sandbox source at import time.
    """
    has_pyproject = (sandbox / "pyproject.toml").exists()
    has_setup = (sandbox / "setup.py").exists()
    logger.info("Installing dependencies from sandbox into venv…")
    # Install from requirements/*.txt files if present
    req_dir = sandbox / "requirements"
    if req_dir.is_dir():
        for req_file in req_dir.glob("*.txt"):
            logger.info(f"Installing dependencies from {req_file}…")
            result = subprocess.run(
                f"{__import__('sys').executable} -m pip install -r {req_file}",
                shell=True,
                cwd=str(sandbox),
                capture_output=True,
                text=True,
                timeout=min(timeout, 180),
            )
            if result.returncode != 0:
                logger.warning(
                    f"pip install failed for {req_file} (exit %d):\n%s\n%s",
                    result.returncode,
                    result.stdout[-500:],
                    result.stderr[-500:],
                )
            else:
                logger.info(f"Dependencies from {req_file} installed.")
    # Install from setup.py or pyproject.toml if present
    if has_pyproject or has_setup:
        result = subprocess.run(
            f"{__import__('sys').executable} -m pip install -e . -q",
            shell=True,
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=min(timeout, 180),
        )
        if result.returncode != 0:
            logger.warning(
                "pip install failed (exit %d):\n%s\n%s",
                result.returncode,
                result.stdout[-500:],
                result.stderr[-500:],
            )
        else:
            logger.info("Dependencies installed.")


def _build_env(sandbox: Path) -> dict:
    """
    Return env with PYTHONPATH pointing at sandbox source.
    PYTHONPATH has higher priority than site-packages, so the patched
    sandbox files override whatever pip just installed.
    """
    env = os.environ.copy()
    extra = []
    src_dir = sandbox / "src"
    if src_dir.is_dir():
        extra.append(str(src_dir))
    extra.append(str(sandbox))

    existing = env.get("PYTHONPATH", "")
    if existing:
        extra.append(existing)

    env["PYTHONPATH"] = ":".join(extra)
    logger.info("PYTHONPATH → %s", env["PYTHONPATH"])
    return env


def run_tests(sandbox_path: str, test_command: str, timeout: int | None = None) -> TestResult:
    """
    Install deps, set PYTHONPATH, run tests.
    """
    timeout = timeout or settings.test_timeout
    sandbox = Path(sandbox_path)
    _install_deps(sandbox, timeout)
    env = _build_env(sandbox)
    return _run_subprocess(sandbox_path, test_command, timeout, env)


def _run_subprocess(
    sandbox_path: str,
    test_command: str,
    timeout: int,
    env: dict,
) -> TestResult:
    start = time.monotonic()
    timed_out = False

    try:
        proc = subprocess.run(
            test_command,
            shell=True,
            cwd=sandbox_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        timed_out = True
        exit_code = -1
        stdout = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = f"Test run timed out after {timeout}s.\n"
    except Exception as e:
        exit_code = -1
        stdout = ""
        stderr = f"Failed to run test command: {e}\n"

    duration = time.monotonic() - start
    success = (exit_code == 0) and not timed_out

    return TestResult(
        success=success,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=round(duration, 2),
        timed_out=timed_out,
    )