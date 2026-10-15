#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# Builds Nivora.app with the WidgetKit extension through native/widgets.yml (needs xcodegen).
# Ad-hoc signed: the sandboxed extension must be signed to load. scripts/build-native.sh builds the plain app.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/native"
[[ "$(uname -s)" == Darwin ]] || { echo "Build on macOS." >&2; exit 1; }
command -v xcodegen >/dev/null || { echo "xcodegen is required (brew install xcodegen)." >&2; exit 1; }
OUT="build/widgets"
rm -rf "$OUT" NivoraWidgetsApp.xcodeproj
mkdir -p "$OUT"
# The project lives beside project.yml so its relative paths (sources, Config/*.plist) resolve.
xcodegen generate --spec widgets.yml --quiet
xcodebuild -project NivoraWidgetsApp.xcodeproj -scheme Nivora -configuration Release -derivedDataPath "$OUT/dd" \
  CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES CODE_SIGN_INJECT_BASE_ENTITLEMENTS=NO build -quiet
rm -rf NivoraWidgetsApp.xcodeproj
APP="$OUT/dd/Build/Products/Release/Nivora.app"
[[ -d "$APP/Contents/PlugIns/NivoraWidgets.appex" ]] || { echo "The widget extension was not embedded." >&2; exit 1; }
echo "$APP"
