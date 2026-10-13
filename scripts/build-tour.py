#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Build docs/social/nivora-tour.gif: a pane-by-pane tour from the real native screenshots in docs/ux/.

Frames are the captured window images (simulated telemetry), not a screen recording.
"""
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PANES = ["overview", "flows", "applications", "health", "timeline", "capture", "security"]
W = 960

frames = []
for pane in PANES:
    im = Image.open(ROOT / "docs/ux" / f"native-light-{pane}.png").convert("RGB")
    im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    frames.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))

out = ROOT / "docs/social/nivora-tour.gif"
frames[0].save(out, save_all=True, append_images=frames[1:], duration=2200, loop=0, optimize=True)
print(out, f"{out.stat().st_size // 1024} KB")
