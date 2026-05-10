#!/usr/bin/env bash
#
# Wrapper around `content-stack doctor` (audit P-G3 / A-MINOR-29).
#
# Defaults to human-readable output. `--json` emits the machine-readable
# envelope `{ok, code, checks, info}`. The Python implementation owns
# the exit-code contract documented at PLAN.md L1271.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCTOR_ARGS=(-m content_stack doctor)

if [[ "${1:-}" == "--json" ]]; then
    DOCTOR_ARGS+=(--json)
fi

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    exec "${REPO_ROOT}/.venv/bin/python" "${DOCTOR_ARGS[@]}"
fi

exec "${UV:-uv}" run --directory "${REPO_ROOT}" python "${DOCTOR_ARGS[@]}"
