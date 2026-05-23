"""Workspace hook execution with timeout enforcement.

Implements SPEC §9.4 (Workspace Hooks):
- Execute hooks in shell context with workspace directory as cwd
- Apply hooks.timeout_ms timeout
- Log hook start, failures, and timeouts
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum bytes of hook output to include in error messages
_MAX_OUTPUT_BYTES = 1024


@dataclass
class HookResult:
    """Result of a hook execution.

    Attributes:
        success: Whether the hook completed successfully (return code 0).
        return_code: The process return code.
        stdout: Captured standard output.
        stderr: Captured standard error.
        timed_out: Whether the hook timed out.
    """

    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class HookTimeoutError(Exception):
    """Raised when a hook execution times out."""

    def __init__(self, timeout_ms: int, output: str) -> None:
        self.timeout_ms = timeout_ms
        # Truncate output for safe logging
        self.output = output[:_MAX_OUTPUT_BYTES] if output else ""
        super().__init__(f"Hook timed out after {timeout_ms}ms")


class HookExecutionError(Exception):
    """Raised when a hook execution fails (non-zero return code)."""

    def __init__(self, return_code: int, stdout: str, stderr: str) -> None:
        self.return_code = return_code
        # Truncate output for safe logging
        self.stdout = stdout[:_MAX_OUTPUT_BYTES] if stdout else ""
        self.stderr = stderr[:_MAX_OUTPUT_BYTES] if stderr else ""
        super().__init__(f"Hook failed with return code {return_code}")


def run_hook(
    script: str,
    cwd: Path,
    timeout_ms: int = 60000,
) -> HookResult:
    """Execute a shell script hook in the given working directory.

    Per SPEC §9.4:
    - Execute in local shell context with workspace directory as cwd
    - On POSIX systems, use `bash -lc <script>`
    - Apply timeout from hooks.timeout_ms

    Args:
        script: The shell script to execute.
        cwd: The working directory for the hook.
        timeout_ms: Timeout in milliseconds (default 60000).

    Returns:
        HookResult with success status, return code, and captured output.

    Raises:
        HookTimeoutError: If the hook exceeds the timeout.
        HookExecutionError: If the hook returns a non-zero exit code.
    """
    timeout_sec = timeout_ms / 1000.0

    logger.info("Running hook in %s (timeout=%dms)", cwd, timeout_ms)

    try:
        result = subprocess.run(
            ["bash", "-lc", script],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as e:
        output = ""
        if e.stdout:
            output += str(e.stdout)[:_MAX_OUTPUT_BYTES]
        if e.stderr:
            output += str(e.stderr)[:_MAX_OUTPUT_BYTES]
        logger.warning("Hook timed out after %dms in %s", timeout_ms, cwd)
        raise HookTimeoutError(timeout_ms, output) from e

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        logger.warning(
            "Hook failed in %s with return code %d: %s",
            cwd,
            result.returncode,
            stderr[:200],
        )
        raise HookExecutionError(result.returncode, stdout, stderr)

    return HookResult(
        success=True,
        return_code=result.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def run_hook_best_effort(
    script: str | None,
    cwd: Path,
    timeout_ms: int = 60000,
) -> HookResult | None:
    """Execute a hook, logging failures but not raising exceptions.

    Used for `after_run` and `before_remove` hooks where failure is
    logged but ignored per SPEC §9.4.

    Args:
        script: The shell script to execute, or None to skip.
        cwd: The working directory for the hook.
        timeout_ms: Timeout in milliseconds.

    Returns:
        HookResult on success, None on failure or if script is None.
    """
    if not script:
        return None

    try:
        return run_hook(script, cwd, timeout_ms)
    except (HookTimeoutError, HookExecutionError) as e:
        logger.warning("Hook failed (ignored): %s", e)
        return None
