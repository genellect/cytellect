#!/usr/bin/env bash
# Install the Japanese figure font (fonts-noto-cjk) on a Linux CI runner.
#
# The package is about 61 MB. A slow Ubuntu mirror has served it at under 50 kB/s,
# spending more than 20 minutes of a 30-minute job before any test ran. Each mirror
# therefore gets a bounded attempt that stops when the transfer stays slow, and the
# downloaded file must match the SHA-256 in the signed apt index before it is
# installed, so every mirror yields the same package. The package has no dependencies,
# so dpkg installs the verified file directly.
set -euo pipefail

package=fonts-noto-cjk
mirrors=(
  http://azure.archive.ubuntu.com/ubuntu
  http://archive.ubuntu.com/ubuntu
  http://mirrors.edge.kernel.org/ubuntu
)

sudo apt-get update
record=$(apt-cache show --no-all-versions "$package")
filename=$(sed -n 's/^Filename: //p' <<<"$record")
size=$(sed -n 's/^Size: //p' <<<"$record")
sha256=$(sed -n 's/^SHA256: //p' <<<"$record")
if [[ -z $filename || -z $size || -z $sha256 ]]; then
  echo "The apt index has no candidate for $package." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"  # apt reads the file as its own unprivileged user
deb=$work/$(basename "$filename")

for round in 1 2; do
  for mirror in "${mirrors[@]}"; do
    if [[ -f $deb && $(stat -c %s "$deb") -gt $size ]]; then
      rm -f "$deb"
    fi
    # Resume a partial file from the previous mirror; the hash check below covers it.
    if [[ ! -f $deb || $(stat -c %s "$deb") -lt $size ]]; then
      echo "Downloading $package from $mirror (round $round)"
      curl --fail --location --silent --show-error --continue-at - \
        --connect-timeout 15 --speed-limit 500000 --speed-time 20 --max-time 300 \
        --output "$deb" "$mirror/$filename" || true
    fi
    if [[ -f $deb && $(stat -c %s "$deb") -eq $size ]]; then
      if sha256sum --check --status <<<"$sha256  $deb"; then
        # dpkg installs this file itself; apt would fetch the same version again from the slow mirror.
        sudo dpkg -i "$deb"
        exit 0
      fi
      echo "The file from $mirror does not match the apt index; discarding it." >&2
      rm -f "$deb"
    fi
  done
done

echo "Could not download $package from any mirror." >&2
exit 1
