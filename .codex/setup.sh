#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Public packages only. No research data or application secrets.
if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user "uv==0.12.2"
  export PATH="$HOME/.local/bin:$PATH"
fi
uv sync --locked --dev --python 3.12
uv run python -m compileall -q packages services
if [ -f apps/web/package.json ]; then
  test -f pnpm-lock.yaml || { echo "Web lockfile required"; exit 1; }
  command -v node >/dev/null
  node -e "if (process.versions.node.split('.')[0] !== '24') process.exit(1)"
  command -v pnpm >/dev/null || npm install --global pnpm@11.19.0
  pnpm install --frozen-lockfile
fi
echo "Python checkpoint installed; Web, worker and Fiji are separate open gates."
