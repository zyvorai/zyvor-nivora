#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Compose the README / social hero from a real native screenshot (needs Pillow; dev-only).

    python3 scripts/build-hero.py            # writes docs/social/nivora-hero.jpg (2400x1260)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
W, H = 2400, 1260
bg = Image.new("RGB", (W, H), (0, 0, 0))
px = bg.load()
for y in range(H):  # soft blue glow from the top-left, same as the site
    for x in range(0, W, 4):
        d = ((x - 480) ** 2 / 1.2e6 + y ** 2 / 4.5e5) ** 0.5
        k = max(0.0, 1 - d)
        c = (int(0 + 12 * k), int(0 + 38 * k), int(0 + 66 * k))
        for dx in range(4):
            if x + dx < W:
                px[x + dx, y] = c

shot = Image.open(ROOT / "docs/ux/native-dark-overview.png").convert("RGBA")
tw = 1700
th = int(shot.height * tw / shot.width)
shot = shot.resize((tw, th), Image.LANCZOS)
mask = Image.new("L", shot.size, 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, shot.width, shot.height), 28, fill=255)
shadow = Image.new("RGBA", (tw + 160, th + 160), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((80, 100, 80 + tw, 100 + th), 28, fill=(0, 0, 0, 200))
shadow = shadow.filter(ImageFilter.GaussianBlur(36))
x0, y0 = W - tw - 90, 410
bg.paste(shadow, (x0 - 80, y0 - 80), shadow)
bg.paste(shot, (x0, y0), mask)

import subprocess, io
png = subprocess.run(["rsvg-convert", "-w", "300", "-h", "300", str(ROOT / "docs/brand/nivora-icon.svg")], capture_output=True, check=True).stdout
icon = Image.open(io.BytesIO(png)).convert("RGBA").resize((150, 150), Image.LANCZOS)
bg.paste(icon, (110, 110), icon)
d = ImageDraw.Draw(bg)
try:
    from PIL import ImageFont
    big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 92, index=1)
    mid = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
except OSError:
    big = mid = small = None
d.text((290, 118), "Zyvor Nivora", font=big, fill=(245, 245, 247))
d.text((292, 232), "See every connection on your Mac.", font=mid, fill=(100, 210, 255))
d.text((112, 290), "© 2026 Zyvor AI Labs Private Limited · BUSL-1.1 · simulated telemetry", font=small, fill=(130, 130, 136))
out = ROOT / "docs/social/nivora-hero.jpg"
bg.save(out, "JPEG", quality=90)
print("wrote", out)
