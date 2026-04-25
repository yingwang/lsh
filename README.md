# lsh - Safe LLM Shell

`lsh` is a minimal safe shell assistant. It turns natural language into a structured execution plan, validates that plan, and only then runs low-risk actions through a controlled executor.

## Project Goal

The goal is to make an LLM-powered shell that is useful without giving the model direct control over the operating system. The architecture separates planning, validation, execution, context collection, and history. With a Gemini API key the planner uses real natural language understanding; without one it falls back to a keyword-based mock planner.

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
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## LLM Setup

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey), then:

```bash
export GEMINI_API_KEY="your-key-here"
```

Without the key, lsh falls back to a keyword-based mock planner.

## Usage

Show a plan without executing it:

```bash
lsh ask "list all files in src/"
```

Example output:

```text
Intent: list files in src directory
Risk: low
Steps:
1. list_files(path="src/", recursive=false)

Execute? no, because --execute was not provided.
```

Execute a low-risk plan:

```bash
lsh ask "what git branch am I on" --execute
```

Find files:

```bash
lsh ask "find all python files" --execute
```

Read a file:

```bash
lsh ask "show me the README" --execute
```

Dangerous commands are rejected:

```bash
lsh ask "delete everything" --execute
```

```text
Rejected by validator:
- high risk plans are not allowed in v1
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

Initialize capabilities config:

```bash
lsh init
# Edit .lsh/config.json to customize allowed/blocked commands, risk threshold, timeout
```

View audit log:

```bash
lsh audit
lsh audit -n 20
```

## Architecture

The first version uses these modules:

- `lsh.schema`: Pydantic models for `Plan`, plan steps, action args, and validation results.
- `lsh.planner`: planner interface and mock planner.
- `lsh.gemini_planner`: Gemini Flash planner (free-tier LLM integration).
- `lsh.config`: capability configuration (`.lsh/config.json`).
- `lsh.validator`: policy checks using capability config.
- `lsh.executor`: controlled execution for validated plans.
- `lsh.context`: current working directory, OS, file preview, and recent history.
- `lsh.history`: JSONL execution history.
- `lsh.audit`: JSONL audit log for all plan evaluations.
- `lsh.cli`: command-line interface.

## Roadmap

v0.2:

- ~~Real LLM integration~~ ✓ (Gemini Flash)
- ~~JSON schema constrained output~~ ✓
- ~~Automatic repair suggestions for failed commands~~ ✓ (LLM-powered explain-error & repair)
- ~~Finer-grained capability system~~ ✓ (`.lsh/config.json`)

v0.3:

- Semantic file search
- Embedding index
- Shell history semantic search

v0.4:

- ~~Audit log~~ ✓ (`.lsh/audit.jsonl`)
- Policy engine
- Reversible operations
