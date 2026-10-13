#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# Capture README/site screenshots of the REAL native app on simulated telemetry (--demo).
# Window-only captures (screencapture -l <window id>): nothing else on the desktop is recorded.
#   ./scripts/build-native.sh && ./scripts/shots-native.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${APP:-$ROOT/native/build/Build/Products/Release/Nivora.app}"
OUT="$ROOT/docs/ux"
[[ -d "$APP" ]] || { echo "missing $APP (run ./scripts/build-native.sh)" >&2; exit 1; }
mkdir -p "$OUT"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nivora-shots.XXXXXX")"; trap 'rm -rf "$TMP"; pkill -x Nivora 2>/dev/null || true; pkill -f "nivora.py" 2>/dev/null || true' EXIT
cat > "$TMP/winid.swift" <<'SWIFT'
import CoreGraphics
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
for w in list where (w[kCGWindowOwnerName as String] as? String) == "Nivora" && (w[kCGWindowLayer as String] as? Int) == 0 {
    print(w[kCGWindowNumber as String] as? Int ?? 0); break
}
SWIFT
shoot() { # appearance pane   (file key; --section matches the pane title, case-insensitive)
  local section="$2"; [[ "$2" == timeline ]] && section="time machine"
  pkill -x Nivora 2>/dev/null || true; pkill -f "nivora.py" 2>/dev/null || true; sleep 1
  open -n "$APP" --args --demo --no-welcome --appearance "$1" --section "$section"
  local id=""
  for _ in $(seq 1 20); do sleep 1; id="$(swift "$TMP/winid.swift" 2>/dev/null | head -1 || true)"; [[ -n "$id" ]] && break; done
  [[ -n "$id" ]] || { echo "no window for $1/$2" >&2; return 1; }
  sleep 7   # let a few samples accumulate so charts have shape
  screencapture -l "$id" -o "$TMP/raw.png"
  sips -Z 1800 "$TMP/raw.png" --out "$OUT/native-$1-$2.png" >/dev/null
  echo "native-$1-$2.png"
}
for mode in light dark; do
  for pane in ${PANES:-overview flows applications health capture security timeline}; do shoot "$mode" "$pane"; done
done
