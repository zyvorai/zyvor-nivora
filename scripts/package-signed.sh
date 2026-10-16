#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# The standard signed build: Developer ID signed, hardened runtime, notarized and stapled.
#
#   DEVELOPER_ID_APP="Developer ID Application: NAME (TEAMID)" \
#   NOTARY_PROFILE=vytrix-notary ./scripts/package-signed.sh
#
# This build leaves out the content-filter system extension and the capture helper: both need Apple's
# NetworkExtension entitlement and a provisioning profile, which a plain Developer ID signature cannot
# carry (macOS would refuse to launch the app). The unsigned developer build (package-dmg.sh) keeps them.
#
#   DEVELOPER_ID_APP  required   signing identity (never hard-code it)
#   NOTARY_PROFILE    optional   `xcrun notarytool store-credentials` profile; without it the DMG is signed
#                                but NOT notarized, and the script says so
#   SKIP_BUILD=1      optional   reuse native/build/.../Nivora.app
#   OUT_DIR           optional   default release-signed/ (git-ignored)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(uname -s)" == Darwin ]] || { echo "Run on macOS." >&2; exit 1; }
: "${DEVELOPER_ID_APP:?set DEVELOPER_ID_APP to the Developer ID Application identity}"
VER="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT/package.json")"
OUT_DIR="${OUT_DIR:-$ROOT/release-signed}"
NOTARY="${NOTARY_PROFILE:-}"
BUILT="$ROOT/native/build/Build/Products/Release/Nivora.app"
if [[ "${SKIP_BUILD:-0}" != 1 ]]; then ./scripts/build-native.sh >/dev/null; fi
[[ -d "$BUILT" ]] || { echo "missing $BUILT" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
APP="$WORK/Nivora.app"
ditto "$BUILT" "$APP"

# Leave out what a plain Developer ID signature cannot carry.
rm -rf "$APP/Contents/Library/SystemExtensions" "$APP/Contents/Library/LaunchServices" "$APP/Contents/Library/LaunchDaemons"
rmdir "$APP/Contents/Library" 2>/dev/null || true
[[ ! -e "$APP/Contents/Library" ]] || { echo "unexpected content left in Contents/Library" >&2; exit 1; }

# No entitlements file: this build needs none, and a restricted one would stop it launching.
codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APP" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
if codesign -d --entitlements - "$APP" 2>/dev/null | grep -q "com.apple.developer"; then
  echo "refusing: restricted entitlements found in the signed app" >&2; exit 1
fi

mkdir -p "$OUT_DIR" "$WORK/dmg"
DMG="$OUT_DIR/Nivora-$VER.dmg"
rm -f "$DMG" "$DMG.sha256"
ditto "$APP" "$WORK/dmg/Nivora.app"
ln -s /Applications "$WORK/dmg/Applications"
hdiutil create -volname "Nivora $VER" -srcfolder "$WORK/dmg" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null
codesign --force --timestamp --sign "$DEVELOPER_ID_APP" "$DMG"

status="Developer ID signed, NOT notarized (set NOTARY_PROFILE)"
if [[ -n "$NOTARY" ]]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY" --wait
  xcrun stapler staple "$DMG"
  xcrun stapler validate "$DMG"
  spctl -a -t open --context context:primary-signature -vv "$DMG"
  status="signed, notarized and stapled"
fi
(cd "$OUT_DIR" && shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256")
echo "wrote $DMG ($status)"
