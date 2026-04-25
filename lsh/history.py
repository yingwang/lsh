"""JSONL history storage for command execution records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HISTORY_DIR = ".lsh"
HISTORY_FILE = "history.jsonl"


@dataclass(frozen=True)
class ExecutionRecord:
    command: str
    stdout: str
    stderr: str
    returncode: int
    cwd: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timed_out: bool = False


def history_path(base_dir: Path | str = ".") -> Path:
    return Path(base_dir) / HISTORY_DIR / HISTORY_FILE


def append_record(record: ExecutionRecord, base_dir: Path | str = ".") -> Path:
    path = history_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return path


def read_recent_history(base_dir: Path | str = ".", limit: int = 10) -> list[dict[str, Any]]:
    path = history_path(base_dir)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def last_record(base_dir: Path | str = ".") -> dict[str, Any] | None:
    records = read_recent_history(base_dir=base_dir, limit=1)
    return records[0] if records else None
