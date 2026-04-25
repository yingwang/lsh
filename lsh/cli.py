"""Command line interface for lsh."""

from __future__ import annotations

import argparse
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from lsh.context import collect_context
from lsh.executor import Executor
from lsh.history import last_record
from lsh.planner import MockPlanner
from lsh.schema import Plan, Risk, ValidationResult
from lsh.validator import validate_plan


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ask":
        return _handle_ask(args)
    if args.command == "explain-error":
        return _handle_explain_error()
    if args.command == "repair":
        return _handle_repair()

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lsh", description="Safe LLM Shell")
    subparsers = parser.add_subparsers(dest="command")

    ask = subparsers.add_parser("ask", help="Generate a structured plan from natural language")
    ask.add_argument("task", help="Natural language task")
    ask.add_argument("--execute", action="store_true", help="Execute the plan after validation")
    ask.add_argument("--dry-run", action="store_true", help="Show the plan and intended actions only")

    subparsers.add_parser("explain-error", help="Explain stderr from the most recent command")
    subparsers.add_parser("repair", help="Suggest a repair for the most recent failed command")

    return parser


def _handle_ask(args: argparse.Namespace) -> int:
    if args.execute and args.dry_run:
        print("Use either --execute or --dry-run, not both.")
        return 2

    planner = MockPlanner()
    try:
        plan = planner.plan(args.task, collect_context())
    except PydanticValidationError as exc:
        print("Planner produced an invalid plan:")
        print(exc)
        return 1

    print(format_plan(plan))

    validation = validate_plan(plan)
    if validation.warnings:
        print("\nWarnings:")
        for warning in validation.warnings:
            print(f"- {warning}")

    if not args.execute:
        print("\nExecute? no, because --execute was not provided.")
        return 0

    if not validation.ok:
        print_rejection(validation)
        return 1

    if validation.risk is not Risk.LOW:
        print("Rejected by validator:")
        print(f"- only low risk plans can be executed in v1; validator risk: {validation.risk.value}")
        return 1

    result = Executor().execute(plan)
    print_execution_result(result)
    return 0 if result.ok else 1


def _handle_explain_error() -> int:
    record = last_record()
    if not record:
        print("No command history found.")
        return 1
    stderr = str(record.get("stderr", ""))
    command = str(record.get("command", ""))
    if not stderr:
        print("The most recent command has no stderr.")
        return 0
    print(_explain_error(command, stderr))
    return 0


def _handle_repair() -> int:
    record = last_record()
    if not record:
        print("No command history found.")
        return 1
    if int(record.get("returncode", 0)) == 0:
        print("The most recent command succeeded; no repair is needed.")
        return 0

    command = str(record.get("command", ""))
    stderr = str(record.get("stderr", ""))
    stdout = str(record.get("stdout", ""))
    print("Repair suggestion:")
    print(_repair_suggestion(command, stdout, stderr))
    return 0


def format_plan(plan: Plan) -> str:
    lines = [
        f"Intent: {plan.intent}",
        f"Risk: {plan.risk.value}",
        "Steps:",
    ]
    for index, step in enumerate(plan.steps, start=1):
        args = step.args.model_dump()
        rendered_args = ", ".join(f"{key}={_format_value(value)}" for key, value in args.items())
        lines.append(f"{index}. {step.action}({rendered_args})")
    return "\n".join(lines)


def print_rejection(validation: ValidationResult) -> None:
    print("\nRejected by validator:")
    for error in validation.errors:
        print(f"- {error}")


def print_execution_result(result: Any) -> None:
    for step in result.steps:
        if not step.ok:
            print(f"{step.action} failed: {step.error}")
            continue
        if step.action in {"list_files", "find_files"}:
            for item in step.output:
                print(item)
        elif step.action == "read_file":
            print(step.output)
        elif step.action == "run_command":
            stdout = step.output.get("stdout", "")
            stderr = step.output.get("stderr", "")
            if stdout:
                print(stdout, end="" if stdout.endswith("\n") else "\n")
            if stderr:
                print(stderr, end="" if stderr.endswith("\n") else "\n")
        else:
            print(step.output)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).lower() if value is None else str(value)


def _explain_error(command: str, stderr: str) -> str:
    lowered = stderr.lower()
    if "no such file or directory" in lowered:
        return f"`{command}` failed because a referenced file, directory, or executable was not found."
    if "permission denied" in lowered:
        return f"`{command}` failed because the current user does not have permission."
    if "command not found" in lowered:
        return f"`{command}` failed because the executable is not available on PATH."
    return f"`{command}` failed with stderr: {stderr.strip()}"


def _repair_suggestion(command: str, stdout: str, stderr: str) -> str:
    lowered = stderr.lower()
    if "no such file or directory" in lowered:
        return "Check the path or executable name, then rerun the command with an existing target."
    if "permission denied" in lowered:
        return "Use a path you own or adjust file permissions outside lsh after reviewing the safety impact."
    if "command not found" in lowered:
        return "Install or activate the missing tool outside lsh, or use an available equivalent command."
    if stdout:
        return "Review stdout and stderr together, then retry with a narrower command."
    return "Inspect the stderr message and retry with corrected arguments."


if __name__ == "__main__":
    raise SystemExit(main())
