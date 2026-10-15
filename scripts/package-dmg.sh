#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/native/build/Build/Products/Release/Nivora.app}"
VER="${VERSION:-$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT/package.json")}"
OUT="$ROOT/Nivora-$VER.dmg"
[[ -d "$APP" ]] || { echo "missing app: $APP" >&2; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp -R "$APP" "$TMP/Nivora.app"
# xcodebuild with CODE_SIGNING_ALLOWED=NO leaves only the linker's ad-hoc signature, which does not seal
# the bundle's resources ("code has no resources but signature indicates they must be present").
# Seal them with a real ad-hoc signature. This is not Developer ID signing or notarisation.
codesign --force --deep --sign - "$TMP/Nivora.app"
codesign --verify --deep --strict "$TMP/Nivora.app"
ln -s /Applications "$TMP/Applications"
hdiutil create -volname Nivora -srcfolder "$TMP" -ov -format UDZO "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "$OUT"
