#!/usr/bin/env bash
#
# Register `content-stack` with the Codex CLI as an MCP server.
#
# Idempotent (audit B-24): if Codex already lists a `content-stack`
# server we treat the script as a no-op. The token rotates only on
# explicit `make rotate-token`, so re-running `make install` does NOT
# need to re-register.
#
# `--remove` unregisters the server (used by `make uninstall`).
# `--force` re-registers even if already present (used after rotation).

set -euo pipefail

ACTION="register"
for arg in "$@"; do
    case "${arg}" in
        --remove) ACTION="remove" ;;
        --force) ACTION="force" ;;
        *) echo "unknown flag: ${arg}" >&2; exit 2 ;;
    esac
done

if ! command -v codex >/dev/null 2>&1; then
    echo "Codex CLI not on PATH — skipping MCP registration."
    echo "  Install Codex CLI then re-run \`bash scripts/register-mcp-codex.sh\`."
    exit 0
fi

HOME_DIR="${CONTENT_STACK_HOME:-${HOME}}"
TOKEN_PATH="${HOME_DIR}/.local/state/content-stack/auth.token"
PORT="${CONTENT_STACK_PORT:-5180}"

already_registered() {
    codex mcp list 2>/dev/null | grep -q '^content-stack[[:space:]]'
}

if [[ "${ACTION}" == "remove" ]]; then
    if already_registered; then
        codex mcp remove content-stack
        echo "Unregistered MCP 'content-stack' from Codex CLI"
    else
        echo "MCP 'content-stack' not registered with Codex CLI; nothing to remove"
    fi
    exit 0
fi

if [[ "${ACTION}" == "register" ]] && already_registered; then
    echo "MCP 'content-stack' already registered with Codex CLI"
    exit 0
fi

if [[ ! -f "${TOKEN_PATH}" ]]; then
    echo "auth token missing at ${TOKEN_PATH} — run \`make install\` or \`content-stack init\` first." >&2
    exit 1
fi
# Codex CLI's HTTP MCP server resolves the bearer token via an environment
# variable name (rather than a literal header), so we register the server
# with `--bearer-token-env-var CONTENT_STACK_TOKEN`. Operators must export
# the variable in their shell before launching Codex; the install
# documentation calls this out explicitly.
TOKEN_ENV_VAR="${CONTENT_STACK_TOKEN_ENV_VAR:-CONTENT_STACK_TOKEN}"

# `--force` removes-then-adds so the registration refreshes after rotation.
if [[ "${ACTION}" == "force" ]] && already_registered; then
    codex mcp remove content-stack
fi

codex mcp add content-stack \
    --url "http://127.0.0.1:${PORT}/mcp" \
    --bearer-token-env-var "${TOKEN_ENV_VAR}"

echo "Registered MCP 'content-stack' with Codex CLI (port ${PORT})"
echo "Note: export ${TOKEN_ENV_VAR}=\$(cat ${TOKEN_PATH}) in your shell rc"
echo "      so Codex picks up the token on launch."
