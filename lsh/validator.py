"""Safety validator for structured plans."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import List, Tuple

from lsh.schema import Plan, Risk, ValidationResult


DANGEROUS_COMMANDS = {
    "rm",
    "sudo",
    "chmod",
    "chown",
    "mkfs",
    "dd",
    "eval",
}

PACKAGE_MANAGERS = {
    "apt",
    "apt-get",
    "brew",
    "dnf",
    "yum",
    "pacman",
    "apk",
    "pip",
    "pip3",
    "python",
    "python3",
    "npm",
    "pnpm",
    "yarn",
}

SYSTEM_DIRS = ("/etc", "/usr", "/bin", "/sbin", "/var")

LOW_RISK_COMMANDS = {"ls", "pwd", "whoami", "date", "echo"}

FORK_BOMB_PATTERNS = (
    re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?\s*:"),
    re.compile(r"\$\(\s*:\s*\|\s*:\s*&\s*\)"),
)


def validate_plan(plan: Plan) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    computed_risk = Risk.LOW

    if plan.risk is Risk.HIGH:
        errors.append("high risk plans are not allowed in v1")

    for step in plan.steps:
        if step.action == "run_command":
            command_errors, command_warnings, command_risk = _validate_command(step.args.command)
            errors.extend(command_errors)
            warnings.extend(command_warnings)
            computed_risk = _max_risk(computed_risk, command_risk)
        elif step.action in {"list_files", "find_files", "read_file"}:
            path = Path(step.args.path)
            if _is_system_path(path) and step.action != "read_file":
                warnings.append(f"system path access: {path}")
        elif step.action == "explain_error":
            computed_risk = _max_risk(computed_risk, Risk.LOW)
        else:
            errors.append(f"unsupported action: {step.action}")

    if errors:
        computed_risk = _max_risk(computed_risk, Risk.HIGH)

    return ValidationResult(
        ok=not errors,
        risk=computed_risk,
        errors=errors,
        warnings=warnings,
    )


def _validate_command(command: str) -> Tuple[List[str], List[str], Risk]:
    errors: List[str] = []
    warnings: List[str] = []
    risk = Risk.MEDIUM
    stripped = command.strip()
    lowered = stripped.lower()

    for pattern in FORK_BOMB_PATTERNS:
        if pattern.search(lowered):
            errors.append("fork bomb pattern is not allowed")
            errors.append("destructive operation is not allowed in v1")
            return errors, warnings, Risk.HIGH

    installer_pipeline = re.search(r"\b(curl|wget)\b.*\|\s*(sh|bash)\b", lowered)
    if installer_pipeline:
        errors.append(f"dangerous command: {installer_pipeline.group(1)} | {installer_pipeline.group(2)}")
        errors.append("network installer pipelines are not allowed in v1")

    if re.search(r">\s*/(?:etc|usr|bin|sbin|var)(?:/|\b)", stripped):
        errors.append("redirection into system paths is not allowed")

    if re.search(r"\b(scp|sftp|rsync)\b", lowered):
        errors.append("network upload commands are not allowed in v1")

    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return [f"invalid command syntax: {exc}"], warnings, Risk.HIGH

    if not parts:
        return ["command must not be empty"], warnings, Risk.HIGH

    program = Path(parts[0]).name
    if program in DANGEROUS_COMMANDS:
        errors.append(f"dangerous command: {program}")
        errors.append("destructive operation is not allowed in v1")

    if _is_package_install(parts):
        errors.append("package manager install is not allowed in v1")

    for token in parts[1:]:
        if _is_system_path(Path(token)) and _looks_like_write_command(program):
            errors.append(f"modifying system path is not allowed: {token}")

    if program in LOW_RISK_COMMANDS and not errors:
        risk = Risk.LOW

    return errors, warnings, risk


def _is_package_install(parts: List[str]) -> bool:
    if not parts:
        return False
    program = Path(parts[0]).name
    if program in {"python", "python3"}:
        return len(parts) >= 4 and parts[1:3] == ["-m", "pip"] and "install" in parts[3:]
    return program in PACKAGE_MANAGERS and "install" in parts[1:]


def _looks_like_write_command(program: str) -> bool:
    return program in {"cp", "mv", "touch", "tee", "install", "mkdir", "ln", "sed"}


def _is_system_path(path: Path) -> bool:
    text = path.as_posix()
    return any(text == system_dir or text.startswith(f"{system_dir}/") for system_dir in SYSTEM_DIRS)


def _max_risk(left: Risk, right: Risk) -> Risk:
    order = {Risk.LOW: 0, Risk.MEDIUM: 1, Risk.HIGH: 2}
    return left if order[left] >= order[right] else right
