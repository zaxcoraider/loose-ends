"""Render the Loose Ends architecture diagram to PNG (for the README + Devpost).

    .venv/Scripts/python.exe -u scripts/make_arch.py

Drawn with Pillow for the same reason as the logo: no SVG toolchain to fight, and the
output is a plain PNG that can be dropped straight into a submission form.

Reads top to bottom: Slack sends message events down, cards and answers come back up;
the two required challenge technologies (RTS, MCP) hang off the bottom.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

S = 2                      # supersample factor; the canvas is drawn at 2x and downscaled
W, H = 1500, 1010

INK = (32, 22, 56)         # near-black text
MUTED = (122, 112, 150)    # labels on arrows
LINE = (176, 166, 205)     # arrow + hairline colour
PAPER = (247, 245, 255)    # page background
CARD = (255, 255, 255)
PURPLE = (76, 42, 133)     # #4C2A85 — the core
VIOLET = (124, 92, 255)    # #7C5CFF — inner stages
GOLD = (255, 209, 102)     # #FFD166 — the loose end / the tech anchors

FONTS = "C:/Windows/Fonts/"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS + name, size * S)


def px(v: int) -> int:
    return v * S


class Canvas:
    def __init__(self) -> None:
        self.img = Image.new("RGB", (px(W), px(H)), PAPER)
        self.d = ImageDraw.Draw(self.img)

    def box(self, xy, fill, radius=16, border=None, width=2):
        x0, y0, x1, y1 = (px(v) for v in xy)
        self.d.rounded_rectangle(
            [x0, y0, x1, y1], px(radius), fill=fill,
            outline=border, width=px(width) if border else 0,
        )

    def text(self, x, y, s, f, fill=INK, anchor="mm"):
        self.d.text((px(x), px(y)), s, font=f, fill=fill, anchor=anchor, align="center")

    def arrow(self, x0, y0, x1, y1, color=LINE, width=3, head=11):
        """Straight arrow; vertical or horizontal only."""
        self.d.line([px(x0), px(y0), px(x1), px(y1)], fill=color, width=px(width))
        h = px(head)
        tx, ty = px(x1), px(y1)
        if x0 == x1:                       # vertical
            sign = 1 if y1 > y0 else -1
            pts = [(tx, ty), (tx - h * 0.6, ty - sign * h), (tx + h * 0.6, ty - sign * h)]
        else:                              # horizontal
            sign = 1 if x1 > x0 else -1
            pts = [(tx, ty), (tx - sign * h, ty - h * 0.6), (tx - sign * h, ty + h * 0.6)]
        self.d.polygon(pts, fill=color)


def main() -> None:
    c = Canvas()

    title = font("segoeuib.ttf", 30)
    sub = font("segoeui.ttf", 17)
    head = font("segoeuib.ttf", 21)
    body = font("segoeui.ttf", 16)
    small = font("segoeui.ttf", 14)
    mono = font("consola.ttf", 15)
    step = font("segoeuib.ttf", 17)

    # ── title ────────────────────────────────────────────────────────────────
    c.text(750, 44, "Loose Ends", title, PURPLE)
    c.text(750, 78, "message events → extract → store → nudge → act", sub, MUTED)

    # ── Slack ────────────────────────────────────────────────────────────────
    c.box((250, 120, 1250, 224), CARD, border=VIOLET, width=2)
    c.text(750, 155, "SLACK WORKSPACE", head, PURPLE)
    c.text(750, 190, "channels  ·  threads  ·  App Home  ·  slash commands", body, MUTED)

    # events down / responses up
    c.arrow(520, 224, 520, 300)
    c.text(508, 262, "message events", small, MUTED, anchor="rm")
    c.arrow(980, 300, 980, 224)
    c.text(992, 262, "nudge cards · dashboard · answers", small, MUTED, anchor="lm")

    # ── the app ──────────────────────────────────────────────────────────────
    c.box((120, 300, 1380, 700), PURPLE, radius=20)
    c.text(750, 338, "LOOSE ENDS  ·  Bolt for Python (Socket Mode)", head, (255, 255, 255))

    # pipeline row
    stages = [
        ("Extractor", "LLM → type · owner · due"),
        ("Store", "SQLite (stdlib)"),
        ("Scheduler", "APScheduler · overdue/stale"),
        ("Nudge card", "Block Kit · private DM"),
    ]
    gap, left, right = 46, 156, 1344
    w = (right - left - gap * 3) / 4
    for i, (name, note) in enumerate(stages):
        x0 = left + i * (w + gap)
        c.box((x0, 380, x0 + w, 470), VIOLET, radius=14)
        c.text(x0 + w / 2, 410, name, step, (255, 255, 255))
        c.text(x0 + w / 2, 440, note, small, (226, 218, 255))
        if i:
            c.arrow(x0 - gap + 6, 425, x0 - 8, 425, color=(178, 158, 255), width=3, head=10)

    # surfaces row
    surfaces = [
        ("/looseends ask", "grounded + cited"),
        ("App Home dashboard", "every open loose end"),
        ("Done · Snooze · Reassign · Escalate", "human in the loop"),
    ]
    w2 = (right - left - gap * 2) / 3
    for i, (name, note) in enumerate(surfaces):
        x0 = left + i * (w2 + gap)
        c.box((x0, 530, x0 + w2, 620), (95, 60, 158), radius=14, border=(146, 118, 232), width=2)
        c.text(x0 + w2 / 2, 560, name, step if i else mono, (255, 255, 255))
        c.text(x0 + w2 / 2, 590, note, small, (206, 196, 240))

    c.text(750, 664, "degrades, never breaks  ·  RTS down → answers from the DB and says so"
                     "  ·  MCP down → the item stays open  ·  LLM down → a plain tracked list",
           small, (186, 172, 226))

    # ── the two required technologies ────────────────────────────────────────
    c.arrow(420, 700, 420, 800)
    c.text(408, 750, "user token", small, MUTED, anchor="rm")
    c.arrow(1080, 700, 1080, 800)
    c.text(1092, 750, "tool call", small, MUTED, anchor="lm")

    c.box((190, 800, 650, 940), CARD, border=GOLD, width=3)
    c.text(420, 833, "Real-Time Search API", head, PURPLE)
    c.text(420, 866, "assistant.search.context", mono, INK)
    c.text(420, 900, "answers grounded in what was said,\nwith permalink citations",
           small, MUTED, anchor="mm")

    c.box((850, 800, 1310, 940), CARD, border=GOLD, width=3)
    c.text(1080, 833, "Loose Ends MCP Server", head, PURPLE)
    c.text(1080, 866, "create_ticket()", mono, INK)
    c.text(1080, 900, "our own, open-sourced in this repo —\nnot just a consumer", small,
           MUTED, anchor="mm")

    c.text(750, 976, "REQUIRED TECHNOLOGIES", small, MUTED)
    c.d.line([px(230), px(976), px(560), px(976)], fill=LINE, width=px(1))
    c.d.line([px(940), px(976), px(1270), px(976)], fill=LINE, width=px(1))

    out = c.img.resize((W, H), Image.LANCZOS)
    out.save("assets/architecture.png")
    print("wrote assets/architecture.png")


if __name__ == "__main__":
    sys.exit(main())
