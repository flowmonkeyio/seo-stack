#!/usr/bin/env bash
#
# content-stack procedure installer for the Claude Code runtime.
#
# TBD pending Claude Code procedure-discovery contract: as of the M9
# strip-map review, Claude Code does not yet document a stable
# `~/.claude/procedures/` discovery path. We ship the mirror anyway so
# the install pipeline is symmetric with Codex; the directory is
# harmless if Claude Code never reads it. Once the discovery contract
# lands, the daemon's procedure-runner reaches into the DB directly so
# this filesystem mirror is purely for visibility / authoring loops.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CONTENT_STACK_HOME:-${HOME}}"
TARGET="${HOME_DIR}/.claude/procedures/content-stack"

mkdir -p "${TARGET}"
rsync -a --delete \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '_template' \
    "${REPO_ROOT}/procedures/" "${TARGET}/"

count=$(find "${TARGET}" -name PROCEDURE.md -type f | wc -l | tr -d ' ')
echo "Installed ${count} procedures to ${TARGET}"
