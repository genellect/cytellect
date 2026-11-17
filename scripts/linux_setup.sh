#!/usr/bin/env bash
# The base Linux development stack for Claude Code cloud sessions and WSL Ubuntu (CONTRIBUTING.md):
# pinned Node.js, pnpm and uv, locked dependencies and the test browser, plus env.sh, which puts them
# first. Fiji and the Japanese figure font are installed on first use by `scripts/dev.py` (serve, check,
# e2e), so a fresh container starts quickly. Public downloads only: keys are read when env.sh is sourced,
# from the environment or from ~/.config/cytellect/dev.env. Running it again changes nothing.
set -euo pipefail
cd "$(dirname "$0")/.."
runtime="$HOME/.local/share/cytellect-dev"
# Setups before 2026-11 used cytellect-cloud: keep its downloads and Fiji, and keep the old path working.
legacy="$HOME/.local/share/cytellect-cloud"
if [ -d "$legacy" ] && [ ! -L "$legacy" ] && [ ! -e "$runtime" ]; then
  mv "$legacy" "$runtime"
  ln -s "$runtime" "$legacy"
fi
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
node -e "if(process.versions.node!==\"$node_version\")process.exit(1)"
[ "$(uv --version | cut -d' ' -f2)" = "$uv_version" ]
pnpm_version=$(node -p 'require("./package.json").packageManager.split("@")[1]')
if ! command -v pnpm >/dev/null 2>&1 || [ "$(pnpm --version)" != "$pnpm_version" ]; then npm install --global "pnpm@$pnpm_version"; fi
fiji="${CYTELLECT_FIJI_EXECUTABLE:-$runtime/fiji}"
# Replace only this script's block (and the block earlier setups wrote), so other lines in env.sh survive.
begin='# >>> cytellect scripts/linux_setup.sh >>>' end='# <<< cytellect scripts/linux_setup.sh <<<'
old_begin='# >>> cytellect .claude/cloud-setup.sh >>>' old_end='# <<< cytellect .claude/cloud-setup.sh <<<'
touch "$runtime/env.sh"
awk -v b="$begin" -v e="$end" -v ob="$old_begin" -v oe="$old_end" \
  '$0 == b || $0 == ob {skip=1} !skip {print} $0 == e || $0 == oe {skip=0}' "$runtime/env.sh" > "$runtime/env.sh.new"
{
  echo "$begin"
  printf 'export PATH=%q:%q:%q:$PATH\n' "$uv_dir" "$node_dir/bin" "$HOME/.local/bin"
  printf 'export CYTELLECT_FIJI_EXECUTABLE=%q\n' "$fiji"
  if [ -x /opt/pw-browsers/chromium ]; then printf 'export CYTELLECT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium\n'; fi
  # Keys kept on this machine (CONTRIBUTING.md, 外部サービス): KEY=value lines, mode 600, outside the checkout.
  # The Modal proxy token becomes the engine's bearer value (ID.secret) for the deployed server; explicit values win.
  cat <<'EOS'
if [ -f "$HOME/.config/cytellect/dev.env" ]; then set -a; . "$HOME/.config/cytellect/dev.env"; set +a; fi
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
# Locked Python and Web dependencies; Fiji ($fiji) and the figure font follow on first use.
python3 scripts/dev.py setup
# Cloud sessions provide Chromium and forbid browser downloads; elsewhere Playwright also needs Ubuntu's libraries.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && [ "${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-}" != "1" ]; then
  pnpm --filter @cytellect/web exec playwright install --with-deps chromium
fi
echo "Linux development stack ready in $runtime"
