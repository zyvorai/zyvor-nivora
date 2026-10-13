#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# Assemble the GitHub Pages site into _site/:
#   /        site/ (landing) + shared images from docs/ux and docs/social
#   /demo/   the real dashboard (web/) running on simulated telemetry in the browser (web/demo.js)
# Same command locally:  ./scripts/build-site.sh && node scripts/site-check.mjs && (cd _site && python3 -m http.server 8080)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/_site}"
rm -rf "$OUT" && mkdir -p "$OUT/ux" "$OUT/social" "$OUT/demo"
cp -R "$ROOT"/site/. "$OUT/"
cp "$ROOT/web/favicon.svg" "$ROOT/web/apple-touch-icon.png" "$OUT/"
cp "$ROOT"/docs/ux/native-*.png "$OUT/ux/"
cp "$ROOT"/docs/social/og.png "$OUT/social/"
# dashboard: the same files the collector serves, flagged as the static demo
cp "$ROOT"/web/{index.html,app.js,lib.js,demo.js,styles.css,demo-snapshot.json,favicon.svg,apple-touch-icon.png} "$OUT/demo/"
python3 - "$OUT/demo/index.html" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
s = s.replace('<html lang="en"', '<html lang="en" data-demo', 1) if 'data-demo' not in s else s
p.write_text(s)
PY
touch "$OUT/.nojekyll"
echo "site built in $OUT"
