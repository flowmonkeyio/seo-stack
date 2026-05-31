#!/usr/bin/env bash
#
# StackOS skill installer for the Claude Code runtime.
#
# Mirrors the canonical StackOS skill into `${HOME}/.claude/skills/stackos/`.
# The Python installer owns source resolution so clone-mode scripts and
# package-mode `stackos install` stay in sync.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${STACKOS_HOME:-${HOME}}"
INSTALL_PYTHON="${STACKOS_INSTALL_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "${INSTALL_PYTHON}" ]]; then
    INSTALL_PYTHON="$(command -v python3)"
fi

PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" "${INSTALL_PYTHON}" - \
    "${HOME_DIR}" <<'PYEOF'
import sys
from pathlib import Path

from stackos import install as installer

target, count = installer.copy_skills("claude", home=Path(sys.argv[1]))
print(f"Installed {count} skills to {target}")
PYEOF
