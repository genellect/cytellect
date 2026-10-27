#!/usr/bin/env bash
# Public dependencies only. API credentials are unavailable during setup.
# Provisions the installation-equivalent stack for `scripts/dev.py serve`: pinned
# Node.js, pnpm and uv, the Japanese figure font and Fiji (nuclei). Cellpose runs on
# the cloud GPU and proposals on the Worker; their credentials come from the
# environment's variables at run time (CONTRIBUTING.md).
set -euo pipefail
cd "$(dirname "$0")/.."
runtime="$HOME/.local/share/cytellect-cloud"
mkdir -p "$runtime"
case "$(uname -m)" in
  x86_64) arch=x64 uv_target=x86_64-unknown-linux-gnu uv_sha256=d66e96b5f1ca3b99806eee283a8125d33a0bd669e6e6d9bc4ab7ffda63c41bf4 ;;
  aarch64) arch=arm64 uv_target=aarch64-unknown-linux-gnu uv_sha256=19b7f1f66895261fbaa07f8ea91da0f86337ad4e47efa594e87641c1718ffc52 ;;
  *) echo "Unsupported Linux architecture" >&2; exit 1 ;;
esac
node_version=24.18.0
node_dir="$runtime/node-v$node_version-linux-$arch"
if [ ! -x "$node_dir/bin/node" ]; then
  archive="node-v$node_version-linux-$arch.tar.xz"
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 "https://nodejs.org/dist/v$node_version/$archive" -o "$runtime/$archive"
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 "https://nodejs.org/dist/v$node_version/SHASUMS256.txt" -o "$runtime/SHASUMS256.txt"
  (cd "$runtime"; awk -v file="$archive" '$2 == file { print; found=1 } END { if (!found) exit 1 }' SHASUMS256.txt | sha256sum --check --strict)
  tar -xJf "$runtime/$archive" -C "$runtime"
fi
# The uv that CI pins; a preinstalled uv of another version is left untouched but shadowed.
uv_version=0.12.2
uv_dir="$runtime/uv-$uv_version"
if [ ! -x "$uv_dir/uv" ]; then
  archive="$runtime/uv-$uv_target.tar.gz"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    "https://github.com/astral-sh/uv/releases/download/$uv_version/uv-$uv_target.tar.gz" -o "$archive"
  echo "$uv_sha256  $archive" | sha256sum --check --strict
  mkdir -p "$uv_dir"
  tar -xzf "$archive" -C "$uv_dir" --strip-components=1
  rm "$archive"
fi
export PATH="$uv_dir:$node_dir/bin:$HOME/.local/bin:$PATH"
node -e 'if(process.versions.node!=="24.18.0")process.exit(1)'
[ "$(uv --version | cut -d' ' -f2)" = "$uv_version" ]
if ! command -v pnpm >/dev/null 2>&1 || [ "$(pnpm --version)" != "11.19.0" ]; then npm install --global pnpm@11.19.0; fi
if ! fc-list :lang=ja family 2>/dev/null | grep -q .; then bash scripts/install_figure_font.sh; fi
# Fiji outside the checkout; `.codex/setup.sh` provisions it and runs the real-Fiji tests.
export CYTELLECT_SETUP_FIJI="${CYTELLECT_SETUP_FIJI:-1}"
export CYTELLECT_FIJI_EXECUTABLE="${CYTELLECT_FIJI_EXECUTABLE:-$runtime/fiji}"
# Replace only this script's block, so lines the environment itself keeps in env.sh survive.
begin='# >>> cytellect .claude/cloud-setup.sh >>>' end='# <<< cytellect .claude/cloud-setup.sh <<<'
touch "$runtime/env.sh"
awk -v b="$begin" -v e="$end" '$0 == b {skip=1} !skip {print} $0 == e {skip=0}' "$runtime/env.sh" > "$runtime/env.sh.new"
{
  echo "$begin"
  printf 'export PATH=%q:%q:%q:$PATH\n' "$uv_dir" "$node_dir/bin" "$HOME/.local/bin"
  printf 'export CYTELLECT_FIJI_EXECUTABLE=%q\n' "$CYTELLECT_FIJI_EXECUTABLE"
  if [ -x /opt/pw-browsers/chromium ]; then printf 'export CYTELLECT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium\n'; fi
  # The Modal proxy token as the engine's bearer value (ID.secret) and the deployed server; explicit values win.
  cat <<'EOS'
if [ -z "${CYTELLECT_CELLPOSE_REMOTE_TOKEN:-}" ] && [ -n "${CYTELLECT_MODAL_PROXY_KEY:-}" ] && [ -n "${CYTELLECT_MODAL_PROXY_SECRET:-}" ]; then
  export CYTELLECT_CELLPOSE_REMOTE_TOKEN="$CYTELLECT_MODAL_PROXY_KEY.$CYTELLECT_MODAL_PROXY_SECRET"
fi
if [ -n "${CYTELLECT_CELLPOSE_REMOTE_TOKEN:-}" ] && [ -z "${CYTELLECT_CELLPOSE_REMOTE_URL:-}" ] && [ -n "${CYTELLECT_MODAL_PROXY_KEY:-}" ]; then
  export CYTELLECT_CELLPOSE_REMOTE_URL=https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct
fi
EOS
  echo "$end"
} >> "$runtime/env.sh.new"
mv "$runtime/env.sh.new" "$runtime/env.sh"
bash .codex/setup.sh
pnpm --filter @cytellect/proposal-worker check
pnpm --filter @cytellect/proposal-worker test
echo 'In subsequent commands: source "$HOME/.local/share/cytellect-cloud/env.sh"; then python3 scripts/dev.py doctor'
