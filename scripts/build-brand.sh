#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
# Derive every icon asset from the single master docs/brand/nivora-icon.svg.
# Needs macOS tools only: rsvg-convert (brew install librsvg), sips, iconutil. Outputs are checked in.
#   ./scripts/build-brand.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MASTER="$ROOT/docs/brand/nivora-icon.svg"
command -v rsvg-convert >/dev/null || { echo "rsvg-convert not found (brew install librsvg)" >&2; exit 1; }
TMP="$(mktemp -d "${TMPDIR:-/tmp}/nivora-brand.XXXXXX")"; trap 'rm -rf "$TMP"' EXIT

# 1. macOS icon (.icns): the standard 16..512 @1x/@2x set
SET="$TMP/Nivora.iconset"; mkdir -p "$SET"
for base in 16 32 128 256 512; do
  rsvg-convert -w "$base" -h "$base" "$MASTER" -o "$SET/icon_${base}x${base}.png"
  rsvg-convert -w "$((base * 2))" -h "$((base * 2))" "$MASTER" -o "$SET/icon_${base}x${base}@2x.png"
done
iconutil -c icns "$SET" -o "$ROOT/native/Nivora.icns"

# 2. web: SVG favicon + apple-touch-icon (square, full-bleed: iOS applies its own mask)
cp "$MASTER" "$ROOT/web/favicon.svg"
sed 's/ rx="230"//' "$MASTER" > "$TMP/square.svg"
rsvg-convert -w 180 -h 180 "$TMP/square.svg" -o "$ROOT/web/apple-touch-icon.png"

# 3. share image 1200x630 (og:image / GitHub social preview)
ICON_B64="$(rsvg-convert -w 360 -h 360 "$MASTER" | base64 | tr -d '\n')"
cat > "$TMP/og.svg" <<SVG
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="630" viewBox="0 0 1200 630">
<defs><radialGradient id="b" cx="22%" cy="0%" r="90%"><stop offset="0" stop-color="#14263d"/><stop offset="1" stop-color="#000"/></radialGradient></defs>
<rect width="1200" height="630" fill="url(#b)"/>
<image x="110" y="135" width="360" height="360" xlink:href="data:image/png;base64,$ICON_B64"/>
<text x="540" y="290" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="96" font-weight="700" fill="#f5f5f7" letter-spacing="-3">Nivora</text>
<text x="544" y="352" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="38" fill="#64d2ff">See every connection on your Mac.</text>
<text x="544" y="420" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="26" fill="#a1a1a6">Apps, flows, DNS, routes, VPNs. Local-first.</text>
</svg>
SVG
rsvg-convert "$TMP/og.svg" -o "$ROOT/docs/social/og.png"
echo "wrote native/Nivora.icns, web/favicon.svg, web/apple-touch-icon.png, docs/social/og.png"
