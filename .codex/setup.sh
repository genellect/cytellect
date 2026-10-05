#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Public packages/datasets only. Complete provisioning before disabling Internet.
if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user "uv==0.12.2"
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v node >/dev/null 2>&1 || ! node -e "if(process.versions.node.split('.')[0]!=='24')process.exit(1)"; then
  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    . "$HOME/.nvm/nvm.sh"
    nvm install 24.18.0
    nvm use 24.18.0
  else
    echo "Provision Node.js24 before setup; do not start an offline task with incomplete dependencies." >&2
    exit 1
  fi
fi
command -v pnpm >/dev/null || npm install --global pnpm@11.19.0
uv sync --locked --dev --python 3.12
pnpm install --frozen-lockfile
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || [ "${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-}" = "1" ]; then
  # Hosted environments provide Chromium and forbid browser downloads; tests use
  # CYTELLECT_CHROMIUM_EXECUTABLE (see apps/web/playwright.config.ts).
  echo "Skipping Playwright browser download; set CYTELLECT_CHROMIUM_EXECUTABLE for browser tests."
else
  pnpm --filter @cytellect/web exec playwright install chromium
fi
if [ "${CYTELLECT_SETUP_FIJI:-0}" = "1" ]; then
  : "${CYTELLECT_FIJI_EXECUTABLE:?Set an absolute runtime directory outside checkout}"
  if [ ! -d "$CYTELLECT_FIJI_EXECUTABLE" ]; then
    uv run python scripts/fiji_setup.py "$CYTELLECT_FIJI_EXECUTABLE" --platform linux-x64
  fi
  uv run pytest -m fiji
fi
uv run python -m compileall -q packages services
pnpm check
echo "Provisioned Python/Web/browser. Fiji only verified when CYTELLECT_SETUP_FIJI=1. Task dispatch is not completion."
