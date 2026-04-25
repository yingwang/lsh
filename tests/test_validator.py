from lsh.schema import Plan, Risk, RunCommandArgs, RunCommandStep
from lsh.validator import validate_plan


def _command_plan(command: str) -> Plan:
    return Plan(
        intent="run_command",
        risk=Risk.MEDIUM,
        requires_confirmation=True,
        steps=[RunCommandStep(action="run_command", args=RunCommandArgs(command=command))],
    )


def test_validator_rejects_rm() -> None:
    result = validate_plan(_command_plan("rm -rf ."))

    assert not result.ok
    assert "dangerous command: rm" in result.errors
    assert "destructive operation is not allowed in v1" in result.errors


def test_validator_rejects_sudo() -> None:
    result = validate_plan(_command_plan("sudo ls"))

    assert not result.ok
    assert "dangerous command: sudo" in result.errors


def test_validator_allows_ls() -> None:
    result = validate_plan(_command_plan("ls -la"))

    assert result.ok
    assert result.risk == Risk.LOW
    assert result.errors == []
