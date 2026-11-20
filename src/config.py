"""Config loading and repo-relative path resolution (no absolute paths in code)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_config(name: str = "eda") -> dict:
    """Load ``configs/<name>.yaml`` and resolve every entry of ``paths`` to an absolute Path."""
    with open(REPO_ROOT / "configs" / f"{name}.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["paths"] = {k: REPO_ROOT / v for k, v in cfg.get("paths", {}).items()}
    return cfg
