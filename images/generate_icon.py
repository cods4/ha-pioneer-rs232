#!/usr/bin/env python3
"""Generate the integration icon/thumbnail.

Renders an original AV-receiver glyph (not the Pioneer trademark) at high
resolution and downscales for smooth, anti-aliased edges. Produces:

  icon.png        512x512  app-icon style (filled rounded square)
  icon-256.png    256x256  same, smaller
  logo.png        ~512 wide transparent glyph (for HA brands / light pages)

Run: uv run python images/generate_icon.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

SS = 3                      # supersampling factor
OUT = 512
W = OUT * SS               # working canvas size

# Palette
BG_TOP = (38, 45, 58)      # slate, top of gradient
BG_BOT = (17, 20, 28)      # slate, bottom
PANEL = (244, 247, 250)    # off-white receiver body
PANEL_EDGE = (210, 216, 224)
DISPLAY = (24, 28, 36)     # dark display window
WAVE = (88, 196, 168)      # teal waveform
RED = (228, 0, 43)         # accent (knob ring, power LED, base bar)
KNOB = (38, 45, 58)        # knob face
KNOB_EDGE = (15, 18, 24)


def vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    """A vertical top->bottom gradient image."""
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)),
        )
    return grad.resize((size, size))


def draw_receiver(
    d: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    w: int,
    h: int,
    panel: tuple = PANEL,
    panel_edge: tuple = PANEL_EDGE,
) -> None:
    """Draw the receiver glyph centred on (cx, cy)."""
    left, top = cx - w // 2, cy - h // 2
    right, bottom = cx + w // 2, cy + h // 2
    r = int(h * 0.16)

    # Body with a subtle outline.
    d.rounded_rectangle([left, top, right, bottom], radius=r,
                        fill=panel, outline=panel_edge, width=max(2, W // 340))

    pad = int(h * 0.20)
    # Display window (left two-thirds).
    disp_l, disp_r = left + pad, left + int(w * 0.60)
    disp_t, disp_b = top + pad, bottom - pad
    dr = int((disp_b - disp_t) * 0.18)
    d.rounded_rectangle([disp_l, disp_t, disp_r, disp_b], radius=dr, fill=DISPLAY)

    # Waveform inside the display: symmetric vertical bars.
    bars = [0.30, 0.62, 0.95, 0.55, 0.78, 0.40, 0.66, 0.28]
    span = disp_r - disp_l
    inner = span * 0.86
    bw = inner / (len(bars) * 1.7)
    gap = bw * 0.7
    midy = (disp_t + disp_b) / 2
    maxh = (disp_b - disp_t) * 0.62
    x = disp_l + (span - (len(bars) * bw + (len(bars) - 1) * gap)) / 2
    for frac in bars:
        bh = maxh * frac
        d.rounded_rectangle(
            [x, midy - bh / 2, x + bw, midy + bh / 2],
            radius=bw / 2, fill=WAVE,
        )
        x += bw + gap

    # Volume knob (right third).
    kcx = int(left + w * 0.80)
    kcy = cy
    kr = int(h * 0.30)
    d.ellipse([kcx - kr, kcy - kr, kcx + kr, kcy + kr],
              fill=RED)                                     # red ring
    ir = int(kr * 0.74)
    d.ellipse([kcx - ir, kcy - ir, kcx + ir, kcy + ir],
              fill=KNOB, outline=KNOB_EDGE, width=max(2, W // 340))
    # Knob indicator notch pointing up.
    nw = max(3, kr // 7)
    d.rounded_rectangle(
        [kcx - nw // 2, kcy - ir + int(kr * 0.10), kcx + nw // 2, kcy - int(kr * 0.18)],
        radius=nw // 2, fill=PANEL,
    )

    # Power LED.
    led = max(4, int(h * 0.05))
    d.ellipse([disp_l, disp_t - led * 0, disp_l + led, disp_t + led], fill=RED)


def build_icon() -> Image.Image:
    """The filled app-icon."""
    base = vertical_gradient(W, BG_TOP, BG_BOT).convert("RGBA")

    # Rounded-square mask.
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, W - 1, W - 1], radius=int(W * 0.22), fill=255
    )
    icon = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    icon.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(icon)
    draw_receiver(d, W // 2, W // 2, int(W * 0.66), int(W * 0.36))
    return icon


def build_logo() -> Image.Image:
    """Transparent glyph for light/dark pages and HA brands."""
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Dark slate body so the glyph reads on white pages and HA cards.
    draw_receiver(
        d, W // 2, W // 2, int(W * 0.78), int(W * 0.42),
        panel=BG_TOP, panel_edge=(96, 106, 121),
    )
    bbox = img.getbbox()
    return img.crop(bbox)


def save(img: Image.Image, name: str, size: int | None) -> None:
    out = img
    if size is not None:
        out = img.resize((size, size), Image.LANCZOS)
    else:
        # logo: scale longest side to OUT, keep aspect.
        scale = OUT / max(img.size)
        out = img.resize(
            (round(img.width * scale), round(img.height * scale)), Image.LANCZOS
        )
    path = os.path.join(HERE, name)
    out.save(path)
    print(f"wrote {name}  {out.size}")


def save_brand(icon: Image.Image) -> None:
    """Emit home-assistant/brands assets (custom_integrations/pioneer_rs232).

    Requires square icons, exactly 256 and 512 px, trimmed (non-transparent
    pixels touch all four edges) and optimized.
    """
    brand_dir = os.path.normpath(
        os.path.join(HERE, "..", "brands", "custom_integrations", "pioneer_rs232")
    )
    os.makedirs(brand_dir, exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        out = icon.resize((size, size), Image.LANCZOS)
        bbox = out.getbbox()
        assert out.size == (size, size), out.size
        assert bbox == (0, 0, size, size), f"{name} not trimmed: bbox={bbox}"
        path = os.path.join(brand_dir, name)
        out.save(path, optimize=True)
        print(f"wrote brands/.../{name}  {out.size}  trimmed={bbox == (0, 0, size, size)}")


def main() -> None:
    icon = build_icon()
    save(icon, "icon.png", OUT)
    save(icon, "icon-256.png", 256)
    save(build_logo(), "logo.png", None)
    save_brand(icon)


if __name__ == "__main__":
    main()
