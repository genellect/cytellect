#!/bin/bash
# Claude Code cloud sessions: apply env.sh to every command, so the pinned Node.js and uv, Fiji, the
# test Chromium and the cloud GPU key are in place without a manual `source`. env.sh comes from
# .claude/cloud-setup.sh (the environment's setup script); this hook installs nothing.
set -euo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] || [ -z "${CLAUDE_ENV_FILE:-}" ]; then exit 0; fi
env_sh="$HOME/.local/share/cytellect-cloud/env.sh"
[ -f "$env_sh" ] || exit 0
line=". $(printf '%q' "$env_sh")"
grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null || printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE"
