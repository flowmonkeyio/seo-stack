#!/usr/bin/env bash
#
# Generate (or refresh) the launchd plist that auto-starts the daemon
# on macOS login. Substitutes `__UV_PATH__`, `__REPO_ROOT__`, `__HOME__`
# at install time so the plist is portable across users.
#
# Idempotency (audit B-24): if an existing plist already matches the
# generated content, the script is a no-op. If it differs, the user is
# prompted unless `--force` is supplied. `--uninstall` boots out the
# job and deletes the plist.

set -euo pipefail

ACTION="install"
FORCE=0
for arg in "$@"; do
    case "${arg}" in
        --force) FORCE=1 ;;
        --uninstall) ACTION="uninstall" ;;
        *) echo "unknown flag: ${arg}" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CONTENT_STACK_HOME:-${HOME}}"
PLIST_DIR="${HOME_DIR}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/com.content-stack.daemon.plist"
LABEL="com.content-stack.daemon"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not on PATH — cannot resolve plist ProgramArguments[0]." >&2
    exit 1
fi
UV_PATH="$(command -v uv)"

uid="$(id -u)"

bootstrap() {
    if launchctl bootstrap "gui/${uid}" "${PLIST_PATH}" 2>/dev/null; then
        return 0
    fi
    # Older launchctl versions (Catalina and earlier) accept `load -w`.
    launchctl load -w "${PLIST_PATH}"
}

bootout() {
    if launchctl print "gui/${uid}/${LABEL}" >/dev/null 2>&1; then
        launchctl bootout "gui/${uid}/${LABEL}" 2>/dev/null || true
        return 0
    fi
    launchctl unload "${PLIST_PATH}" 2>/dev/null || true
}

if [[ "${ACTION}" == "uninstall" ]]; then
    if [[ -f "${PLIST_PATH}" ]]; then
        bootout
        rm -f "${PLIST_PATH}"
        echo "Removed launchd plist ${PLIST_PATH}"
    else
        echo "No launchd plist at ${PLIST_PATH}; nothing to do"
    fi
    exit 0
fi

mkdir -p "${PLIST_DIR}"

# Build the plist into a temp file first so we can diff against any
# existing copy before overwriting.
NEW=$(mktemp)
trap 'rm -f "${NEW}"' EXIT

cat >"${NEW}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${UV_PATH}</string>
    <string>run</string>
    <string>--directory</string>
    <string>${REPO_ROOT}</string>
    <string>python</string>
    <string>-m</string>
    <string>content_stack</string>
    <string>serve</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>${HOME_DIR}/.local/state/content-stack/daemon.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME_DIR}/.local/state/content-stack/daemon.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME_DIR}</string>
  </dict>
</dict>
</plist>
EOF

if [[ -f "${PLIST_PATH}" ]] && cmp -s "${NEW}" "${PLIST_PATH}"; then
    echo "launchd plist already current at ${PLIST_PATH}; no-op"
    # Make sure the job is loaded — re-running `make install-launchd` after
    # a manual `launchctl bootout` should bring it back.
    bootstrap || true
    exit 0
fi

if [[ -f "${PLIST_PATH}" ]] && [[ "${FORCE}" -eq 0 ]]; then
    if [[ -t 0 ]]; then
        read -r -p "launchd plist at ${PLIST_PATH} differs from the generated one. Overwrite? [y/N] " ans
        case "${ans}" in
            y|Y|yes|YES) ;;
            *)
                echo "Aborted; plist left unchanged. Re-run with --force to skip the prompt."
                exit 1
                ;;
        esac
    else
        echo "launchd plist at ${PLIST_PATH} differs and stdin is not a TTY." >&2
        echo "Re-run with --force to overwrite (a .bak will be retained)." >&2
        exit 1
    fi
fi

# Keep a backup so a manual rollback is one rename away.
if [[ -f "${PLIST_PATH}" ]]; then
    cp "${PLIST_PATH}" "${PLIST_PATH}.bak"
    bootout
fi

mv "${NEW}" "${PLIST_PATH}"
trap - EXIT

bootstrap

echo "Installed launchd plist at ${PLIST_PATH}"
