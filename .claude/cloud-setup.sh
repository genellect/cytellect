#!/usr/bin/env bash
# Claude Code cloud environments (CONTRIBUTING.md, クラウド開発): the base Linux setup only, so a fresh
# container starts quickly. Fiji and the figure font are installed on first use by `scripts/dev.py`, and
# checks run in pull-request CI and `scripts/dev.py check`. Public dependencies only: API credentials are
# unavailable during setup; Cellpose (cloud GPU) and proposals (Worker) read theirs at run time.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/linux_setup.sh
# Claude Code sessions load env.sh through .claude/hooks/session-start.sh.
echo 'In other shells: source "$HOME/.local/share/cytellect-dev/env.sh"; then python3 scripts/dev.py doctor'
