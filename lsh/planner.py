"""Planner interfaces and a small mock planner for v0.1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from lsh.schema import (
    FindFilesArgs,
    FindFilesStep,
    ListFilesArgs,
    ListFilesStep,
    Plan,
    ReadFileArgs,
    ReadFileStep,
    Risk,
    RunCommandArgs,
    RunCommandStep,
)


class Planner(ABC):
    @abstractmethod
    def plan(self, user_input: str, context: Dict[str, Any]) -> Plan:
        """Convert natural language into a structured execution plan."""


class MockPlanner(Planner):
    def plan(self, user_input: str, context: Dict[str, Any]) -> Plan:
        text = user_input.strip()
        lowered = text.lower()

        if "find python files" in lowered:
            return Plan(
                intent="find_python_files",
                risk=Risk.LOW,
                requires_confirmation=False,
                steps=[
                    FindFilesStep(
                        action="find_files",
                        args=FindFilesArgs(path=".", pattern="*.py"),
                    )
                ],
            )

        if "show readme" in lowered or "read readme" in lowered:
            return Plan(
                intent="read_readme",
                risk=Risk.LOW,
                requires_confirmation=False,
                steps=[
                    ReadFileStep(
                        action="read_file",
                        args=ReadFileArgs(path="README.md", max_bytes=20_000),
                    )
                ],
            )

        if lowered.startswith("run "):
            command = text[4:].strip()
            return Plan(
                intent="run_command",
                risk=Risk.MEDIUM,
                requires_confirmation=True,
                steps=[
                    RunCommandStep(
                        action="run_command",
                        args=RunCommandArgs(command=command),
                    )
                ],
            )

        if "list files" in lowered or lowered in {"ls", "list"}:
            return Plan(
                intent="list_files",
                risk=Risk.LOW,
                requires_confirmation=False,
                steps=[
                    ListFilesStep(
                        action="list_files",
                        args=ListFilesArgs(path=".", recursive=False),
                    )
                ],
            )

        return Plan(
            intent="list_files",
            risk=Risk.LOW,
            requires_confirmation=False,
            steps=[
                ListFilesStep(
                    action="list_files",
                    args=ListFilesArgs(path=".", recursive=False),
                )
            ],
        )


