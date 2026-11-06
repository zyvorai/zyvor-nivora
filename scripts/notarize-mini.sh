#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# Developer ID sign, notarize and staple the Nivora DMG on the Mac mini (`ssh mini`).
#
#   ./scripts/build-native.sh && ./scripts/notarize-mini.sh [--dry-run] [--gui] [path/to/Nivora.app]
#
# What it does: copies the built (unsigned) app to the mini, signs nested code then the app with the
# Developer ID Application identity and the hardened runtime, builds and signs the DMG, submits it with
# `notarytool --keychain-profile Macora-Notary --wait`, staples, checks with spctl, and copies the DMG and
# its .sha256 back to the repo root. The App Store Connect API key (.p8) stays on the mini; it is never copied.
#
# Scope: the app is signed WITHOUT the restricted NetworkExtension/system-extension entitlements, because
# those need a provisioning profile from Apple. The result is a notarized app that opens without a Gatekeeper
# warning; the content filter and capture helper still need a provisioned build (docs/NETWORKEXTENSION.md).
#
# --gui  run the remote steps from the mini's logged-in GUI session (Terminal) instead of plain ssh. Use it if
#        codesign fails over ssh with a keychain error; click "Always Allow" once on the mini.
# --dry-run  print what would run; touch nothing.
set -euo pipefail

HOST="${NIVORA_MINI_HOST:-mini}"
APP_ID="Developer ID Application: ZYVORAI LABS PRIVATE LIMITED (NX667LTDQ2)"
PROFILE="Macora-Notary"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0; GUI=0; APP=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --gui) GUI=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) APP="$a" ;;
  esac
done
APP="${APP:-$ROOT/native/build/Build/Products/Release/Nivora.app}"
VER="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT/package.json")"
WORK="nivora-notarize/$VER"           # relative to the mini's home directory
OUT="$ROOT/Nivora-$VER.dmg"

# The remote half, written to a file so --gui can run it from Terminal and ssh can pipe it.
remote_script() {
cat <<REMOTE
#!/usr/bin/env bash
set -euo pipefail
cd "\$HOME/$WORK"
APP_ID="$APP_ID"; PROFILE="$PROFILE"; VER="$VER"
sign() { codesign --force --timestamp --options runtime --sign "\$APP_ID" "\$@"; }

# Sign nested code first, deepest paths first; avoid --deep (it applies one set of options to everything).
while IFS= read -r p; do sign "\$p"; done < <(
  { find Nivora.app/Contents \( -name '*.systemextension' -o -name '*.appex' -o -name '*.xpc' -o -name '*.framework' -o -name '*.dylib' \) -print
    find Nivora.app/Contents/Library/LaunchServices -type f -perm -u+x -print 2>/dev/null
    find Nivora.app/Contents/MacOS -type f -perm -u+x ! -name Nivora -print 2>/dev/null
  } | awk '{ print length(\$0) "\t" \$0 }' | sort -rn | cut -f2-)
sign Nivora.app
codesign --verify --deep --strict --verbose=2 Nivora.app

rm -rf stage Nivora-\$VER.dmg && mkdir stage
cp -R Nivora.app stage/Nivora.app && ln -s /Applications stage/Applications
hdiutil create -volname Nivora -srcfolder stage -ov -format UDZO Nivora-\$VER.dmg
codesign --force --timestamp --sign "\$APP_ID" Nivora-\$VER.dmg

xcrun notarytool submit Nivora-\$VER.dmg --keychain-profile "\$PROFILE" --wait
xcrun stapler staple Nivora-\$VER.dmg
xcrun stapler validate Nivora-\$VER.dmg
spctl --assess --type open --context context:primary-signature --verbose=2 Nivora-\$VER.dmg
shasum -a 256 Nivora-\$VER.dmg > Nivora-\$VER.dmg.sha256
REMOTE
}

say() { printf '==> %s\n' "$*"; }

if [[ $DRY -eq 1 ]]; then
  say "dry run: nothing is copied or executed"
  say "host: $HOST   app: $APP   version: $VER"
  say "identity: $APP_ID   notary profile: $PROFILE"
  say "would rsync the app to $HOST:~/$WORK, run the signing/notarization steps below, and fetch Nivora-$VER.dmg to $OUT"
  echo '--- remote script ---'; remote_script
  exit 0
fi

[[ -d "$APP" ]] || { echo "missing app: $APP (run ./scripts/build-native.sh)" >&2; exit 1; }
[[ "$(basename "$APP")" == "Nivora.app" ]] || { echo "expected a Nivora.app, got $APP" >&2; exit 1; }
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" true || { echo "cannot reach '$HOST' over ssh" >&2; exit 1; }

say "copying the app to $HOST:~/$WORK"
ssh "$HOST" "rm -rf ~/$WORK && mkdir -p ~/$WORK"
rsync -a --delete "$APP/" "$HOST:$WORK/Nivora.app/"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
remote_script > "$TMP/run.sh"
if [[ $GUI -eq 1 ]]; then
  say "running in the mini's GUI session (watch Terminal there; click Always Allow if asked)"
  { echo '#!/usr/bin/env bash'
    echo "cd \"\$HOME/$WORK\""
    echo "rm -f .done .failed"
    echo "if bash ./run.sh > run.log 2>&1; then touch .done; else touch .failed; fi"
  } > "$TMP/run.command"
  scp -q "$TMP/run.sh" "$TMP/run.command" "$HOST:$WORK/"
  ssh "$HOST" "chmod +x ~/$WORK/run.command && open -a Terminal ~/$WORK/run.command"
  for _ in $(seq 1 360); do   # up to 30 minutes
    if ssh "$HOST" "test -e ~/$WORK/.done"; then break; fi
    if ssh "$HOST" "test -e ~/$WORK/.failed"; then ssh "$HOST" "tail -40 ~/$WORK/run.log" >&2; echo "remote steps failed" >&2; exit 1; fi
    sleep 5
  done
  ssh "$HOST" "test -e ~/$WORK/.done" || { echo "timed out waiting for the mini" >&2; exit 1; }
  ssh "$HOST" "cat ~/$WORK/run.log" | tail -15
else
  say "signing and notarizing over ssh (this can take several minutes)"
  ssh "$HOST" "bash -s" < "$TMP/run.sh"
fi

say "fetching the notarized DMG"
rsync -a "$HOST:$WORK/Nivora-$VER.dmg" "$OUT"
( cd "$ROOT" && shasum -a 256 "Nivora-$VER.dmg" > "Nivora-$VER.dmg.sha256" )
say "done: $OUT"
cat "$ROOT/Nivora-$VER.dmg.sha256"
