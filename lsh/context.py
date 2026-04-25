"""Lightweight context collection for planners."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from lsh.history import read_recent_history


def collect_context(base_dir: Path | str = ".") -> dict[str, Any]:
    root = Path(base_dir)
    files_preview = sorted(path.name for path in root.iterdir())[:50] if root.exists() else []
    return {
        "cwd": str(root.resolve()),
        "os": platform.platform(),
        "shell": os.environ.get("SHELL", ""),
        "files_preview": files_preview,
        "recent_history": read_recent_history(base_dir=root, limit=10),
    }
