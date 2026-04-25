"""Typed schemas for structured LLM shell plans."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListFilesArgs(StrictModel):
    path: str = "."
    recursive: bool = False


class FindFilesArgs(StrictModel):
    path: str = "."
    pattern: str = "*.py"
    min_size_mb: float | None = None
    max_size_mb: float | None = None


class ReadFileArgs(StrictModel):
    path: str = "README.md"
    max_bytes: int = Field(default=20_000, ge=1, le=1_000_000)


class RunCommandArgs(StrictModel):
    command: str

    @field_validator("command")
    @classmethod
    def command_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("command must not be empty")
        return value


class ExplainErrorArgs(StrictModel):
    command: str
    stderr: str


class ListFilesStep(StrictModel):
    action: Literal["list_files"]
    args: ListFilesArgs = Field(default_factory=ListFilesArgs)


class FindFilesStep(StrictModel):
    action: Literal["find_files"]
    args: FindFilesArgs = Field(default_factory=FindFilesArgs)


class ReadFileStep(StrictModel):
    action: Literal["read_file"]
    args: ReadFileArgs = Field(default_factory=ReadFileArgs)


class RunCommandStep(StrictModel):
    action: Literal["run_command"]
    args: RunCommandArgs


class ExplainErrorStep(StrictModel):
    action: Literal["explain_error"]
    args: ExplainErrorArgs


PlanStep = Annotated[
    ListFilesStep | FindFilesStep | ReadFileStep | RunCommandStep | ExplainErrorStep,
    Field(discriminator="action"),
]


class Plan(StrictModel):
    intent: str
    risk: Risk
    requires_confirmation: bool = True
    steps: list[PlanStep]

    @field_validator("intent")
    @classmethod
    def intent_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("intent must not be empty")
        return value

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_empty(cls, value: list[PlanStep]) -> list[PlanStep]:
        if not value:
            raise ValueError("plan must contain at least one step")
        return value


class ValidationResult(StrictModel):
    ok: bool
    risk: Risk
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlanAdapter(RootModel[Plan]):
    """Compatibility wrapper for tests that want to validate raw dictionaries."""


def parse_plan(data: dict[str, Any]) -> Plan:
    """Parse untrusted plan data into a typed Plan."""

    return Plan.model_validate(data)
