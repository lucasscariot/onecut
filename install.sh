#!/bin/bash

set -Eeuo pipefail

ONECUT_REPO="${ONECUT_REPO:-lucasscariot/onecut}"
BIN_DIR="${ONECUT_BIN_DIR:-$HOME/.local/bin}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to install OneCut." >&2
  exit 1
fi

mkdir -p -- "$BIN_DIR"
base_url="https://raw.githubusercontent.com/$ONECUT_REPO/main/bin"

for command_name in onecut onecut-comments; do
  destination="$BIN_DIR/$command_name"
  temporary="$destination.tmp"
  curl --fail --location --silent --show-error "$base_url/$command_name" -o "$temporary"
  chmod 755 "$temporary"
  mv -f -- "$temporary" "$destination"
done

echo "Installed OneCut in $BIN_DIR"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add $BIN_DIR to your PATH to run 'onecut' from any folder." ;;
esac
