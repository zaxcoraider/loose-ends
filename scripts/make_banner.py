"""Render the App Home banner to PNG.

    .venv/Scripts/python.exe -u scripts/make_banner.py

Block Kit has no styling hooks — an `image` block is the one genuinely graphical element
you get. Slack fetches it over the public internet, and this app has no `files:write`
scope and no host, so we serve it from the public repo via raw.githubusercontent.com
(see BANNER_URL in src/home.py).

Composites assets/logo-512.png rather than redrawing the mark, so the banner and the app
icon can never drift apart.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

S = 2                       # supersample, then downscale for crisp text
W, H = 1200, 300

BG_FROM = (76, 42, 133)     # #4C2A85
BG_TO = (124, 92, 255)      # #7C5CFF
GOLD = (255, 209, 102)      # #FFD166
FONTS = "C:/Windows/Fonts/"


def gradient(w: int, h: int) -> Image.Image:
    g = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(g)
    for x in range(w):
        t = x / max(w - 1, 1)
        d.line(
            [(x, 0), (x, h)],
            fill=tuple(round(BG_FROM[i] + (BG_TO[i] - BG_FROM[i]) * t) for i in range(3)),
        )
    return g


def main() -> None:
    w, h = W * S, H * S
    img = gradient(w, h)
    d = ImageDraw.Draw(img)

    # the mark, lifted straight from the app icon
    try:
        logo = Image.open("assets/logo-512.png").convert("RGBA")
    except FileNotFoundError:
        print("! assets/logo-512.png missing — run scripts/make_logo.py first")
        return sys.exit(1)

    mark = 200 * S
    logo = logo.resize((mark, mark), Image.LANCZOS)
    img.paste(logo, (72 * S, (h - mark) // 2), logo)

    x = 72 * S + mark + 56 * S
    title = ImageFont.truetype(FONTS + "segoeuib.ttf", 76 * S)
    tag = ImageFont.truetype(FONTS + "segoeui.ttf", 31 * S)

    d.text((x, h // 2 - 52 * S), "Loose Ends", font=title, fill=(255, 255, 255),
           anchor="lm")
    d.text((x, h // 2 + 18 * S), "The promises that scroll away — caught, tracked, closed.",
           font=tag, fill=(222, 212, 255), anchor="lm")

    # a gold thread trailing off the right edge: the loose end that never got tied
    y = h // 2 + 62 * S
    d.line([(x, y), (w - 150 * S, y)], fill=(160, 128, 255), width=3 * S)
    d.ellipse(
        [w - 150 * S - 9 * S, y - 9 * S, w - 150 * S + 9 * S, y + 9 * S], fill=GOLD
    )

    img.resize((W, H), Image.LANCZOS).save("assets/banner.png")
    print("wrote assets/banner.png")


if __name__ == "__main__":
    sys.exit(main())
