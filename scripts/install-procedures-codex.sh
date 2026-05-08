#!/usr/bin/env bash
#
# content-stack procedure installer for the Codex CLI runtime.
#
# Mirrors `procedures/` (excluding the `_template/` authoring scaffold,
# audit A-MINOR-39) into `${HOME}/.codex/procedures/content-stack/`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CONTENT_STACK_HOME:-${HOME}}"
TARGET="${HOME_DIR}/.codex/procedures/content-stack"

mkdir -p "${TARGET}"
rsync -a --delete \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '_template' \
    "${REPO_ROOT}/procedures/" "${TARGET}/"

count=$(find "${TARGET}" -name PROCEDURE.md -type f | wc -l | tr -d ' ')
echo "Installed ${count} procedures to ${TARGET}"
