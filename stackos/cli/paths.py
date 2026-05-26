"""Local path helpers for CLI install/doctor flows."""

from __future__ import annotations

import os
from pathlib import Path


def _doctor_home() -> Path:
    """Return the install home used by scripts and pipx install helpers."""
    return Path(os.environ.get("STACKOS_HOME") or Path.home()).expanduser()


__all__ = ["_doctor_home"]
