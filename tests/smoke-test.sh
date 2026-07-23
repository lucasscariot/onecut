#!/bin/bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
FIXTURE="$ROOT_DIR/tests/fixtures/20260720_120000.mp4"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/onecut-test.XXXXXX")"

if [[ -n "${ONECUT_BIN:-}" ]]; then
  ONECUT=("$ONECUT_BIN")
else
  export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
  ONECUT=(python3 -m onecut)
fi

cleanup() {
  rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT INT TERM

cp "$FIXTURE" "$WORK_DIR/20260720_120000.mp4"
ONECUT_DIR="$WORK_DIR" "${ONECUT[@]}" captions
perl -0pi -e 's/TITLE: /TITLE: OneCut smoke test/; s/- 00:00 \n/- 00:00 Caption test\n/' "$WORK_DIR/captions.txt"
ONECUT_DIR="$WORK_DIR" EXPORT_QUALITY=youtube-1080 "${ONECUT[@]}" render output.mp4

ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK_DIR/output.mp4" >/dev/null

if [[ "$(uname -s)" == "Darwin" ]]; then
  original_mtime="$(stat -f %m "$WORK_DIR/20260720_120000.mp4")"
else
  original_mtime="$(stat -c %Y "$WORK_DIR/20260720_120000.mp4")"
fi
"${ONECUT[@]}" keep-first 0.5 "$WORK_DIR/20260720_120000.mp4"
if [[ "$(uname -s)" == "Darwin" ]]; then
  trimmed_mtime="$(stat -f %m "$WORK_DIR/20260720_120000.mp4")"
else
  trimmed_mtime="$(stat -c %Y "$WORK_DIR/20260720_120000.mp4")"
fi
test "$original_mtime" = "$trimmed_mtime"
echo "Smoke test passed"
