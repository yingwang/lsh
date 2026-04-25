from lsh.executor import Executor
from lsh.schema import ListFilesArgs, ListFilesStep, Plan, ReadFileArgs, ReadFileStep, Risk


def test_executor_list_files(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    plan = Plan(
        intent="list_files",
        risk=Risk.LOW,
        requires_confirmation=False,
        steps=[ListFilesStep(action="list_files", args=ListFilesArgs(path=".", recursive=False))],
    )

    result = Executor(base_dir=tmp_path).execute(plan)

    assert result.ok
    assert result.steps[0].output == ["a.txt", "b.txt"]


def test_executor_read_file_limited(tmp_path) -> None:
    (tmp_path / "README.md").write_text("abcdef", encoding="utf-8")
    plan = Plan(
        intent="read_readme",
        risk=Risk.LOW,
        requires_confirmation=False,
        steps=[ReadFileStep(action="read_file", args=ReadFileArgs(path="README.md", max_bytes=3))],
    )

    result = Executor(base_dir=tmp_path).execute(plan)

    assert result.ok
    assert result.steps[0].output == "abc"
