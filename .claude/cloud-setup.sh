#!/usr/bin/env bash
# Claude Code cloud environments (CONTRIBUTING.md, クラウド開発): the shared Linux setup, then the checks a
# fresh container runs once. Public dependencies only: API credentials are unavailable during setup, and
# Cellpose (cloud GPU) and proposals (Worker) read theirs from the environment's variables at run time.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/linux_setup.sh
. "$HOME/.local/share/cytellect-dev/env.sh"
uv run pytest -m fiji
uv run python -m compileall -q packages services
pnpm check
pnpm --filter @cytellect/proposal-worker check
pnpm --filter @cytellect/proposal-worker test
# Claude Code sessions load env.sh through .claude/hooks/session-start.sh.
echo 'In other shells: source "$HOME/.local/share/cytellect-dev/env.sh"; then python3 scripts/dev.py doctor'
