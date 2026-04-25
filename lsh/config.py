"""Capability configuration for lsh."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

CONFIG_DIR = ".lsh"
CONFIG_FILE = "config.json"


class Capabilities(BaseModel):
    max_auto_risk: str = Field(
        default="low",
        description="Maximum risk level that can execute without confirmation: low, medium",
    )
    allowed_commands: List[str] = Field(
        default_factory=lambda: [
            "git", "make", "cargo", "grep", "find", "cat", "head", "tail",
            "wc", "sort", "uniq", "diff", "tr", "cut", "awk", "sed",
            "python", "python3", "node", "npm", "go", "rustc",
        ],
        description="Commands treated as low-risk when not modifying system paths",
    )
    blocked_commands: List[str] = Field(
        default_factory=lambda: [
            "rm", "sudo", "chmod", "chown", "mkfs", "dd", "eval",
        ],
        description="Commands always rejected",
    )
    max_timeout_seconds: int = Field(
        default=30,
        description="Maximum execution timeout in seconds",
    )


class LshConfig(BaseModel):
    capabilities: Capabilities = Field(default_factory=Capabilities)


def config_path(base_dir: Any = ".") -> Path:
    return Path(base_dir) / CONFIG_DIR / CONFIG_FILE


def load_config(base_dir: Any = ".") -> LshConfig:
    path = config_path(base_dir)
    if not path.exists():
        return LshConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LshConfig.model_validate(data)
    except Exception:
        return LshConfig()


def save_config(config: LshConfig, base_dir: Any = ".") -> Path:
    path = config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
