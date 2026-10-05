#!/usr/bin/env bash
# Public dependencies only. API credentials are unavailable during setup.
set -euo pipefail
cd "$(dirname "$0")/.."
runtime="$HOME/.local/share/cytellect-cloud"
mkdir -p "$runtime"
case "$(uname -m)" in x86_64) arch=x64 ;; aarch64) arch=arm64 ;; *) echo "Unsupported Linux architecture" >&2; exit 1 ;; esac
node_version=24.18.0
node_dir="$runtime/node-v$node_version-linux-$arch"
if [ ! -x "$node_dir/bin/node" ]; then
  archive="node-v$node_version-linux-$arch.tar.xz"
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 "https://nodejs.org/dist/v$node_version/$archive" -o "$runtime/$archive"
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 "https://nodejs.org/dist/v$node_version/SHASUMS256.txt" -o "$runtime/SHASUMS256.txt"
  (cd "$runtime"; awk -v file="$archive" '$2 == file { print; found=1 } END { if (!found) exit 1 }' SHASUMS256.txt | sha256sum --check --strict)
  tar -xJf "$runtime/$archive" -C "$runtime"
fi
export PATH="$node_dir/bin:$HOME/.local/bin:$PATH"
node -e 'if(process.versions.node!=="24.18.0")process.exit(1)'
if ! command -v pnpm >/dev/null 2>&1 || [ "$(pnpm --version)" != "11.19.0" ]; then npm install --global pnpm@11.19.0; fi
printf 'export PATH=%q:%q:$PATH\n' "$node_dir/bin" "$HOME/.local/bin" > "$runtime/env.sh"
bash .codex/setup.sh
pnpm --filter @cytellect/proposal-worker check
pnpm --filter @cytellect/proposal-worker test
echo 'In subsequent commands: source "$HOME/.local/share/cytellect-cloud/env.sh"'
