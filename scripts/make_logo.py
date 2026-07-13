"""Render the Loose Ends app icon to PNG (Slack wants >=512x512 PNG/JPG).

    .venv/Scripts/python.exe -u scripts/make_logo.py

Draws directly with Pillow rather than rasterizing assets/logo.svg — the pure-Python
SVG rasterizers on Windows choke on the rounded-rect clip + drop-shadow filter, and
fighting that toolchain isn't worth it for one icon.

The mark: a loop of thread that never got tied off, with one strand trailing away to
a frayed gold tip. Legible at 32px in a Slack sidebar.
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
RADIUS = 116          # badge corner radius
CX, CY, R = 230, 262, 100   # the loop
STROKE = 34
GAP_START, GAP_END = 18, 62  # degrees; the opening the loose end escapes through

BG_FROM = (76, 42, 133)    # #4C2A85
BG_TO = (124, 92, 255)     # #7C5CFF
GOLD = (255, 209, 102)     # #FFD166


def gradient() -> Image.Image:
    """Diagonal gradient, corner to corner."""
    g = Image.new("RGB", (SIZE, SIZE))
    px = g.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * (SIZE - 1))
            px[x, y] = tuple(
                round(BG_FROM[i] + (BG_TO[i] - BG_FROM[i]) * t) for i in range(3)
            )
    return g


def rounded_mask() -> Image.Image:
    m = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], RADIUS, fill=255)
    return m


def bezier(p0, p1, p2, steps=60):
    """Quadratic bezier -> polyline."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append(
            (
                u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
            )
        )
    return out


def draw_thread(d: ImageDraw.ImageDraw, color) -> None:
    # the loop: an arc with a gap at the lower right
    d.arc(
        [CX - R, CY - R, CX + R, CY + R],
        start=GAP_END, end=GAP_START + 360,
        fill=color, width=STROKE,
    )
    # the loose end: leaves through the gap and trails away. It never comes back.
    # Stamped as overlapping dots rather than a wide polyline — Pillow's `joint="curve"`
    # leaves hatching artifacts on thick strokes.
    start = (CX + R * math.cos(math.radians(GAP_END)),
             CY + R * math.sin(math.radians(GAP_END)))
    rr = STROKE / 2
    for x, y in bezier(start, (330, 400), (398, 392), steps=240):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=color)
    # frayed tip
    d.ellipse([398 - 19, 392 - 19, 398 + 19, 392 + 19], fill=GOLD)


def main() -> None:
    badge = gradient()
    badge.putalpha(rounded_mask())

    # soft drop shadow under the thread, so it lifts off the gradient
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    draw_thread(sd, (27, 11, 59, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    shadow = Image.alpha_composite(
        Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)),
        shadow.transform(
            (SIZE, SIZE), Image.AFFINE, (1, 0, 0, 0, 1, -5), resample=Image.BILINEAR
        ),
    )

    out = Image.alpha_composite(badge.convert("RGBA"), shadow)
    draw_thread(ImageDraw.Draw(out), (255, 255, 255, 255))

    out.save("assets/logo-512.png")
    out.resize((192, 192), Image.LANCZOS).save("assets/logo-192.png")
    out.resize((32, 32), Image.LANCZOS).save("assets/logo-32.png")  # sidebar legibility check
    print("wrote assets/logo-512.png, logo-192.png, logo-32.png")


if __name__ == "__main__":
    sys.exit(main())
