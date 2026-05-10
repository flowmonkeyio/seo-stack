#!/usr/bin/env bash
# Regenerate ui/src/api.ts from the daemon's OpenAPI spec.
#
# Boots the daemon if it's not already serving, waits for /api/v1/health to
# return 200, then runs the openapi-typescript pass via pnpm. Used by
# `make gen-types` and the release gen-types parity check.
#
# We never want to clobber an existing daemon — if /health responds, we
# reuse it; otherwise we start one in the background, wait, run, then kill
# our spawned process on exit.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

HEALTH_URL="http://127.0.0.1:5180/api/v1/health"
DAEMON_PID=""

cleanup() {
    if [[ -n "$DAEMON_PID" ]]; then
        echo "[gen-types] stopping spawned daemon (pid=$DAEMON_PID)"
        kill "$DAEMON_PID" 2>/dev/null || true
        wait "$DAEMON_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Probe — already running?
if curl -sf -o /dev/null --max-time 2 "$HEALTH_URL"; then
    echo "[gen-types] reusing already-running daemon"
else
    echo "[gen-types] starting daemon in background"
    # Use a temporary state dir so we don't tread on the operator's token.
    GEN_STATE=$(mktemp -d)
    GEN_DATA=$(mktemp -d)
    CONTENT_STACK_STATE_DIR="$GEN_STATE" \
        CONTENT_STACK_DATA_DIR="$GEN_DATA" \
        uv run python -m content_stack serve > /tmp/content-stack-gen-types.log 2>&1 &
    DAEMON_PID=$!
    echo "[gen-types] spawned daemon pid=$DAEMON_PID; state=$GEN_STATE"

    # Wait up to 30s for liveness.
    for _ in $(seq 1 60); do
        if curl -sf -o /dev/null --max-time 1 "$HEALTH_URL"; then
            break
        fi
        sleep 0.5
    done
    if ! curl -sf -o /dev/null --max-time 1 "$HEALTH_URL"; then
        echo "[gen-types] daemon never reached healthy state; tail of log:"
        tail -50 /tmp/content-stack-gen-types.log
        exit 1
    fi
fi

echo "[gen-types] regenerating ui/src/api.ts"
BEFORE_LINES=$(wc -l < ui/src/api.ts || echo 0)
pnpm --dir ui run gen-types
AFTER_LINES=$(wc -l < ui/src/api.ts)
echo "[gen-types] ui/src/api.ts: $BEFORE_LINES -> $AFTER_LINES lines"

if git diff --quiet -- ui/src/api.ts; then
    echo "[gen-types] no changes — types already in sync."
else
    echo "[gen-types] ui/src/api.ts updated; review and commit."
fi
