# lsh - Safe LLM Shell

`lsh` is a minimal safe shell assistant. It turns natural language into a structured execution plan, validates that plan, and only then runs low-risk actions through a controlled executor.

## Project Goal

The goal is to make an LLM-powered shell that is useful without giving the model direct control over the operating system. In v0.1, the planner is a mock planner, but the architecture already separates planning, validation, execution, context collection, and history.

## Why Not Direct Shell Generation

Letting an LLM produce arbitrary shell commands is fragile and unsafe. A model can hallucinate flags, misunderstand the current directory, or generate destructive commands such as `rm`, `sudo`, or installer pipelines. `lsh` instead asks the planner for a typed `Plan`, validates that plan against explicit policy, and executes only supported actions.

## Safety Model

The v0.1 safety boundary is intentionally small:

- The planner only returns structured plans.
- Plans are parsed with Pydantic models before execution.
- The validator rejects dangerous commands including `rm`, `sudo`, `chmod`, `chown`, `mkfs`, `dd`, `eval`, fork bomb patterns, `curl | sh`, `wget | sh`, package-manager installs, network upload commands, and writes to system paths.
- `list_files`, `find_files`, and `read_file` are implemented with the Python standard library.
- `run_command` uses `subprocess.run` with `shell=False`, `shlex.split`, a timeout, and captured stdout/stderr.
- Command execution records are appended to `.lsh/history.jsonl`.
- CLI execution is opt-in with `--execute`; the default behavior is dry-run.

## Installation

From the project root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Usage

Show a plan without executing it:

```bash
lsh ask "list files"
```

Example output:

```text
Intent: list_files
Risk: low
Steps:
1. list_files(path=".", recursive=false)

Execute? no, because --execute was not provided.
```

Execute a low-risk plan:

```bash
lsh ask "list files" --execute
```

Find Python files:

```bash
lsh ask "find python files" --dry-run
```

Read the README:

```bash
lsh ask "show readme" --execute
```

Reject a dangerous command:

```bash
lsh ask "run rm -rf ." --execute
```

Example output:

```text
Rejected by validator:
- dangerous command: rm
- destructive operation is not allowed in v1
```

Explain the most recent stderr:

```bash
lsh explain-error
```

Suggest a repair for the most recent failed command:

```bash
lsh repair
```

## Architecture

The first version uses these modules:

- `lsh.schema`: Pydantic models for `Plan`, plan steps, action args, and validation results.
- `lsh.planner`: planner interface plus a mock planner.
- `lsh.validator`: policy checks for actions and command strings.
- `lsh.executor`: controlled execution for validated plans.
- `lsh.context`: current working directory, OS, file preview, and recent history.
- `lsh.history`: JSONL execution history.
- `lsh.cli`: command-line interface.

## Roadmap

v0.2:

- Real LLM integration
- JSON schema constrained output
- Automatic repair suggestions for failed commands
- Finer-grained capability system

v0.3:

- Semantic file search
- Embedding index
- Shell history semantic search

v0.4:

- Policy engine
- Audit log
- Reversible operations
