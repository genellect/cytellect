#!/bin/bash
# Claude Code sessions (cloud and WSL): apply env.sh to every command, so the pinned Node.js and uv, Fiji,
# the test Chromium and the cloud GPU key are in place without a manual `source`. env.sh comes from
# scripts/linux_setup.sh; where it has not run, this hook does nothing. It installs nothing.
set -euo pipefail
[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
env_sh="$HOME/.local/share/cytellect-dev/env.sh"
[ -f "$env_sh" ] || exit 0
line=". $(printf '%q' "$env_sh")"
grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null || printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE"
