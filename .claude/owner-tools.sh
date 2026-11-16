#!/usr/bin/env bash
# The owner's environments only, cloud and WSL (CONTRIBUTING.md, オーナーの環境): CLIs for the services
# the owner operates, at pinned versions. Run after scripts/linux_setup.sh (or .claude/cloud-setup.sh). wrangler comes from the
# lockfile (services/proposal-worker); Modal deploys through GitHub Actions. Credentials are not
# read here: the environment's network secrets reach the services through its proxy.
set -euo pipefail
cd "$(dirname "$0")/.."
runtime="$HOME/.local/share/cytellect-dev"
. "$runtime/env.sh"
vercel_version=65.16.0
huggingface_hub_version=2.4.0
tools="$runtime/owner-tools"
mkdir -p "$tools" "$HOME/.local/bin"
if ! "$tools/vercel/node_modules/.bin/vercel" --version 2>/dev/null | grep -qx "$vercel_version"; then
  npm install --silent --no-fund --no-audit --prefix "$tools/vercel" "vercel@$vercel_version"
fi
ln -sf "$tools/vercel/node_modules/.bin/vercel" "$HOME/.local/bin/vercel"
uv tool install --quiet --python 3.12 "huggingface_hub==$huggingface_hub_version"
# Match the version line only: a freshly installed CLI may add hints to its output.
vercel --version 2>/dev/null | grep -qx "$vercel_version"
hf version 2>/dev/null | grep -qx "version=$huggingface_hub_version"
echo "Owner tools: Vercel CLI $vercel_version, Hugging Face CLI $huggingface_hub_version"
