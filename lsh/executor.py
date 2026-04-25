"""Controlled execution engine for validated plans."""

from __future__ import annotations

import fnmatch
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from lsh.history import ExecutionRecord, append_record
from lsh.schema import Plan
from lsh.validator import validate_plan


DEFAULT_TIMEOUT_SECONDS = 10


@dataclass
class StepResult:
    action: str
    ok: bool
    output: Any = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    ok: bool
    steps: List[StepResult] = field(default_factory=list)


class Executor:
    def __init__(self, base_dir: Any = ".", timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_dir = Path(base_dir)
        self.timeout_seconds = timeout_seconds

    def execute(self, plan: Plan) -> ExecutionResult:
        validation = validate_plan(plan)
        if not validation.ok:
            return ExecutionResult(
                ok=False,
                steps=[
                    StepResult(
                        action="validate_plan",
                        ok=False,
                        error="; ".join(validation.errors),
                    )
                ],
            )

        results: list[StepResult] = []
        for step in plan.steps:
            if step.action == "list_files":
                results.append(self._list_files(step.args.path, step.args.recursive))
            elif step.action == "find_files":
                results.append(
                    self._find_files(
                        path=step.args.path,
                        pattern=step.args.pattern,
                        min_size_mb=step.args.min_size_mb,
                        max_size_mb=step.args.max_size_mb,
                    )
                )
            elif step.action == "read_file":
                results.append(self._read_file(step.args.path, step.args.max_bytes))
            elif step.action == "run_command":
                results.append(self._run_command(step.args.command))
            elif step.action == "explain_error":
                results.append(
                    StepResult(
                        action="explain_error",
                        ok=True,
                        output=_simple_error_explanation(step.args.command, step.args.stderr),
                    )
                )
        return ExecutionResult(ok=all(result.ok for result in results), steps=results)

    def _resolve(self, path: str) -> Path:
        target = (self.base_dir / path).resolve()
        root = self.base_dir.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"path escapes working directory: {path}")
        return target

    def _list_files(self, path: str, recursive: bool) -> StepResult:
        try:
            target = self._resolve(path)
            if recursive:
                files = sorted(str(item.relative_to(target)) for item in target.rglob("*"))
            else:
                files = sorted(item.name for item in target.iterdir())
            return StepResult(action="list_files", ok=True, output=files)
        except Exception as exc:
            return StepResult(action="list_files", ok=False, error=str(exc))

    def _find_files(
        self,
        path: str,
        pattern: str,
        min_size_mb: Optional[float],
        max_size_mb: Optional[float],
    ) -> StepResult:
        try:
            target = self._resolve(path)
            matches: list[str] = []
            for item in target.rglob("*"):
                if not item.is_file() or not fnmatch.fnmatch(item.name, pattern):
                    continue
                size_mb = item.stat().st_size / (1024 * 1024)
                if min_size_mb is not None and size_mb < min_size_mb:
                    continue
                if max_size_mb is not None and size_mb > max_size_mb:
                    continue
                matches.append(str(item.relative_to(target)))
            return StepResult(action="find_files", ok=True, output=sorted(matches))
        except Exception as exc:
            return StepResult(action="find_files", ok=False, error=str(exc))

    def _read_file(self, path: str, max_bytes: int) -> StepResult:
        try:
            target = self._resolve(path)
            data = target.read_bytes()[:max_bytes]
            return StepResult(
                action="read_file",
                ok=True,
                output=data.decode("utf-8", errors="replace"),
            )
        except Exception as exc:
            return StepResult(action="read_file", ok=False, error=str(exc))

    def _run_command(self, command: str) -> StepResult:
        try:
            args = shlex.split(command)
            completed = subprocess.run(
                args,
                cwd=self.base_dir,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            append_record(
                ExecutionRecord(
                    command=command,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    returncode=completed.returncode,
                    cwd=str(self.base_dir.resolve()),
                ),
                base_dir=self.base_dir,
            )
            return StepResult(
                action="run_command",
                ok=completed.returncode == 0,
                output={
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "returncode": completed.returncode,
                },
                error=completed.stderr if completed.returncode else None,
            )
        except subprocess.TimeoutExpired as exc:
            append_record(
                ExecutionRecord(
                    command=command,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or f"command timed out after {self.timeout_seconds}s",
                    returncode=124,
                    cwd=str(self.base_dir.resolve()),
                    timed_out=True,
                ),
                base_dir=self.base_dir,
            )
            return StepResult(
                action="run_command",
                ok=False,
                error=f"command timed out after {self.timeout_seconds}s",
            )
        except Exception as exc:
            append_record(
                ExecutionRecord(
                    command=command,
                    stdout="",
                    stderr=str(exc),
                    returncode=127,
                    cwd=str(self.base_dir.resolve()),
                ),
                base_dir=self.base_dir,
            )
            return StepResult(action="run_command", ok=False, error=str(exc))


def _simple_error_explanation(command: str, stderr: str) -> str:
    lowered = stderr.lower()
    if "no such file or directory" in lowered:
        return f"The command `{command}` referenced a path or executable that does not exist."
    if "permission denied" in lowered:
        return f"The command `{command}` failed because the current user lacks permission."
    if "command not found" in lowered:
        return f"The executable in `{command}` could not be found on PATH."
    return f"The command `{command}` failed with stderr: {stderr.strip()}"
