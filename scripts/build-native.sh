#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/native"
"$ROOT/scripts/generate-xcode.sh"
TEAM="${DEVELOPMENT_TEAM:-}"
EXTRA=()
if [[ -n "$TEAM" ]]; then EXTRA+=("DEVELOPMENT_TEAM=$TEAM"); else EXTRA+=("CODE_SIGNING_ALLOWED=NO"); fi
xcodebuild -project Nivora.xcodeproj -scheme Nivora -configuration Release -derivedDataPath build "${EXTRA[@]}" build
APP=$(find build/Build/Products/Release -maxdepth 1 -name 'Nivora.app' -print -quit)
[[ -n "$APP" ]] && echo "$APP"
