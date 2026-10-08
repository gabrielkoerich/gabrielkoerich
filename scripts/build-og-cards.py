"""Draw a 1200x630 card per post into static/images/og, only missing ones unless run with --all"""

import re
import sys
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "images" / "og"
FONTS = ROOT / "scripts" / "fonts"

W, H, LEFT, RIGHT = 1200, 630, 90, 1112
BG, GLOW, BLUE, WHITE, GREY, MUTED = "#0f1319", "#1d2a3a", "#4a9eff", "#eef1f5", "#9aa4b2", "#8b95a3"


def font(name, size, weight):
    f = ImageFont.truetype(str(FONTS / name), size)
    f.set_variation_by_axes([weight])
    return f


def wrap(draw, text, f, width):
    lines = [""]
    for word in text.split():
        line = f"{lines[-1]} {word}".strip()
        if draw.textlength(line, font=f) <= width or not lines[-1]:
            lines[-1] = line
        else:
            lines.append(word)

    return lines


def background():
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    ImageDraw.Draw(glow).ellipse((W - 700, -500, W + 700, 400), fill=GLOW)
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), 1)
    ImageDraw.Draw(img).rectangle((0, 0, 7, H), fill=BLUE)
    return img


def card(front):
    # "Question? Answer" and "Topic: detail" titles split into a headline and a blue subtitle
    title, subtitle = front["title"], ""
    for sep in ("? ", ": "):
        if sep in title:
            head, subtitle = title.split(sep, 1)
            title = head + sep.strip() if sep == "? " else head
            break

    img = background()
    draw = ImageDraw.Draw(img)

    site = font("JetBrainsMono.ttf", 22, 500)
    x = LEFT
    for ch in "GABRIELKOERICH.COM":
        draw.text((x, 88), ch, font=site, fill=BLUE)
        x += draw.textlength(ch, font=site) + 4

    size = 64 if len(title) > 40 else 76
    head = font("SchibstedGrotesk.ttf", size, 800)
    y = 150
    for line in wrap(draw, title, head, RIGHT - LEFT):
        draw.text((LEFT, y), line, font=head, fill=WHITE)
        y += int(size * 1.08)

    if subtitle:
        sub = font("SchibstedGrotesk.ttf", 48, 700)
        for line in wrap(draw, subtitle, sub, RIGHT - LEFT):
            draw.text((LEFT, y + 14), line, font=sub, fill=BLUE)
            y += 52

    # Footer: author and date on the left, tags on the right, on one baseline
    base = H - 84
    name, rest = font("SchibstedGrotesk.ttf", 26, 700), font("SchibstedGrotesk.ttf", 26, 400)
    draw.text((LEFT, base), "Gabriel Koerich", font=name, fill=WHITE, anchor="ls")
    draw.text((LEFT + draw.textlength("Gabriel Koerich", font=name), base),
              " · " + front["date"].strftime("%b %-d, %Y"), font=rest, fill=GREY, anchor="ls")

    mono = font("JetBrainsMono.ttf", 24, 500)
    tags = " · ".join(front.get("taxonomies", {}).get("tags", [])[:3])
    draw.text((RIGHT, base), tags, font=mono, fill=MUTED, anchor="rs")
    draw.text((RIGHT - draw.textlength(tags, font=mono), base), "~ › ", font=mono, fill=BLUE, anchor="rs")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0

    for path in sorted((ROOT / "content" / "posts").glob("*.md")):
        if path.name.startswith("_") or path.name.endswith(".pt.md"):
            continue

        front = tomllib.loads(path.read_text().split("+++", 2)[1])
        if front.get("draft") or not front.get("date") or front.get("extra", {}).get("image"):
            continue

        slug = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", path.stem)
        # CI draws only missing cards, so a different Pillow build does not rewrite committed ones
        if (OUT / f"{slug}.png").exists() and "--all" not in sys.argv:
            continue

        card(front).save(OUT / f"{slug}.png", optimize=True)
        count += 1

    print(f"drew {count} cards into {OUT}")


if __name__ == "__main__":
    main()
