#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/native/build/Build/Products/Release/Nivora.app}"
VER="${VERSION:-0.2.0}"
OUT="$ROOT/Nivora-$VER.dmg"
[[ -d "$APP" ]] || { echo "missing app: $APP" >&2; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp -R "$APP" "$TMP/Nivora.app"
ln -s /Applications "$TMP/Applications"
hdiutil create -volname Nivora -srcfolder "$TMP" -ov -format UDZO "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "$OUT"
