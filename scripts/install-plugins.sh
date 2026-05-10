#!/usr/bin/env bash
#
# content-stack plugin installer.
#
# Mirrors `plugins/content-stack/` into `${HOME}/plugins/content-stack/`, hydrates
# it with the skill/procedure catalog, and upserts a home-local Codex-compatible
# marketplace entry at `${HOME}/.agents/plugins/marketplace.json`.
# This keeps website repositories clean: the plugin is global/user-local, while
# repo/project binding lives in the content-stack daemon DB.

set -euo pipefail

ACTION="install"
for arg in "$@"; do
    case "${arg}" in
        --remove) ACTION="remove" ;;
        *) echo "unknown flag: ${arg}" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CONTENT_STACK_HOME:-${HOME}}"
TARGET="${HOME_DIR}/plugins/content-stack"
MARKETPLACE="${HOME_DIR}/.agents/plugins/marketplace.json"

mkdir -p "${TARGET}" "$(dirname "${MARKETPLACE}")"

if [[ "${ACTION}" == "install" ]]; then
    rsync -a --delete \
        --exclude '.DS_Store' \
        --exclude '__pycache__' \
        "${REPO_ROOT}/plugins/content-stack/" "${TARGET}/"
    mkdir -p "${TARGET}/skills/catalog" "${TARGET}/procedures"
    rsync -a --delete \
        --exclude '.DS_Store' \
        --exclude '__pycache__' \
        "${REPO_ROOT}/skills/" "${TARGET}/skills/catalog/"
    rsync -a --delete \
        --exclude '.DS_Store' \
        --exclude '__pycache__' \
        --exclude '_template' \
        "${REPO_ROOT}/procedures/" "${TARGET}/procedures/"
else
    rm -rf "${TARGET}"
fi

python3 - "${MARKETPLACE}" "${ACTION}" <<'PYEOF'
import json
import os
import sys
import tempfile

target, action = sys.argv[1:3]

existing = {
    "name": "local-content-stack",
    "interface": {"displayName": "Local content-stack Plugins"},
    "plugins": [],
}
if os.path.exists(target):
    with open(target, encoding="utf-8") as f:
        text = f.read().strip()
        if text:
            loaded = json.loads(text)
            if not isinstance(loaded, dict):
                print(f"existing {target} is not a JSON object", file=sys.stderr)
                sys.exit(1)
            existing = loaded

plugins = existing.setdefault("plugins", [])
if not isinstance(plugins, list):
    print(f"`plugins` in {target} must be a list", file=sys.stderr)
    sys.exit(1)

plugins[:] = [
    p for p in plugins
    if not (isinstance(p, dict) and p.get("name") == "content-stack")
]
if action == "install":
    plugins.append({
        "name": "content-stack",
        "source": {"source": "local", "path": "./plugins/content-stack"},
        "policy": {
            "installation": "INSTALLED_BY_DEFAULT",
            "authentication": "ON_USE",
        },
        "category": "Productivity",
    })

target_dir = os.path.dirname(os.path.abspath(target)) or "."
fd, tmp = tempfile.mkstemp(prefix=".marketplace.", dir=target_dir)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, target)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
PYEOF

if [[ -d "${TARGET}" ]]; then
    count=$(find "${TARGET}" -path '*/.codex-plugin/plugin.json' -type f | wc -l | tr -d ' ')
else
    count=0
fi
if [[ "${ACTION}" == "install" ]]; then
    echo "Installed ${count} plugins to ${TARGET}"
    echo "Registered content-stack plugin marketplace at ${MARKETPLACE}"
else
    echo "Removed content-stack plugin from ${TARGET}"
    echo "Unregistered content-stack plugin marketplace entry at ${MARKETPLACE}"
fi
