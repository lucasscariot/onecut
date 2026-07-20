#!/bin/bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
FIXTURE="$ROOT_DIR/tests/fixtures/20260720_120000.mp4"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/onecut-test.XXXXXX")"

cleanup() {
  rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT INT TERM

cp "$FIXTURE" "$WORK_DIR/20260720_120000.mp4"
ONECUT_DIR="$WORK_DIR" EXPORT_QUALITY=youtube-1080 "$ROOT_DIR/bin/onecut" comments
perl -0pi -e 's/TITLE: /TITLE: OneCut smoke test/; s/- 00:00 \n/- 00:00 Caption test\n/' "$WORK_DIR/comments.txt"
ONECUT_DIR="$WORK_DIR" EXPORT_QUALITY=youtube-1080 "$ROOT_DIR/bin/onecut" output.mp4

ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK_DIR/output.mp4" >/dev/null
echo "Smoke test passed"
