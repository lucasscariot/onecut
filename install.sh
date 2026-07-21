#!/bin/bash

set -Eeuo pipefail

ONECUT_REPO="${ONECUT_REPO:-lucasscariot/onecut}"
BIN_DIR="${ONECUT_BIN_DIR:-$HOME/.local/bin}"
INSTALL_DIR="${ONECUT_INSTALL_DIR:-$HOME/.local/share/onecut}"
VERSION="${ONECUT_VERSION:-latest}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to install OneCut." >&2
  exit 1
fi

system="$(uname -s)"
architecture="$(uname -m)"
case "$system/$architecture" in
  Darwin/arm64) asset="onecut-darwin-arm64.tar.gz" ;;
  *)
    echo "ERROR: no packaged OneCut binary is available for $system/$architecture yet." >&2
    exit 1
    ;;
esac

if [[ "$VERSION" == "latest" ]]; then
  base_url="https://github.com/$ONECUT_REPO/releases/latest/download"
else
  base_url="https://github.com/$ONECUT_REPO/releases/download/$VERSION"
fi

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/onecut-install.XXXXXX")"
cleanup() {
  rm -rf -- "$work_dir"
}
trap cleanup EXIT INT TERM

curl --fail --location --silent --show-error "$base_url/$asset" -o "$work_dir/$asset"
curl --fail --location --silent --show-error "$base_url/$asset.sha256" -o "$work_dir/$asset.sha256"
(cd "$work_dir" && shasum -a 256 -c "$asset.sha256")
tar -xzf "$work_dir/$asset" -C "$work_dir"
if [[ ! -x "$work_dir/onecut/onecut" ]]; then
  echo "ERROR: the OneCut release archive is invalid." >&2
  exit 1
fi

mkdir -p -- "$BIN_DIR"
mkdir -p -- "$(dirname -- "$INSTALL_DIR")"
staged_install="${INSTALL_DIR}.new.$$"
old_install="${INSTALL_DIR}.old.$$"
mv -- "$work_dir/onecut" "$staged_install"
if [[ -e "$INSTALL_DIR" ]]; then
  mv -- "$INSTALL_DIR" "$old_install"
fi
if ! mv -- "$staged_install" "$INSTALL_DIR"; then
  if [[ -e "$old_install" ]]; then
    mv -- "$old_install" "$INSTALL_DIR"
  fi
  exit 1
fi
if [[ -e "$old_install" ]]; then
  rm -rf -- "$old_install"
fi
ln -sfn "$INSTALL_DIR/onecut" "$BIN_DIR/onecut"
ln -sfn onecut "$BIN_DIR/onecut-comments"

echo "Installed the self-contained OneCut CLI in $INSTALL_DIR"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add $BIN_DIR to your PATH to run 'onecut' from any folder." ;;
esac
