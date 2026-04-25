"""Audit log for all plan evaluations — accepted and rejected."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

AUDIT_DIR = ".lsh"
AUDIT_FILE = "audit.jsonl"


@dataclass(frozen=True)
class AuditEntry:
    intent: str
    risk: str
    accepted: bool
    user_input: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def audit_path(base_dir: Any = ".") -> Path:
    return Path(base_dir) / AUDIT_DIR / AUDIT_FILE


def log_audit(entry: AuditEntry, base_dir: Any = ".") -> None:
    path = audit_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def read_audit(base_dir: Any = ".", limit: int = 20) -> List[dict]:
    path = audit_path(base_dir)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
