"""Share previews for the Hiring Radar.

1. site/og/<slug>.png: a 1200x630 Deploy-branded card per company (+ site/og/radar.png), rebuilt daily in CI and
   served from GitHub Pages (/og/). Needs Pillow.
2. With --pages DIR: writes DIR/<slug>/index.html + DIR/index.html, the short share links for deploytlv.com/radar/.
   Each page carries the og:image and forwards to /db/radar/#c=<slug>. Run it only when companies are added:
     python3 share_cards.py --pages "../../Deploy Website/radar"
"""
import html, json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OG_BASE = "https://myrondoesnotcode.github.io/hiring-radar/og/"
PAPER, INK, ORANGE, MUTED = (243, 238, 223), (17, 16, 13), (255, 90, 24), (107, 101, 88)
F = lambda name, size: ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
slug = lambda s: re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", s.lower()))

report = json.load(open(os.path.join(HERE, "data", "report.json")))
T = report["totals"]
cos = [c for c in report["companies"] if c["israel"] > 0]
imgmeta = {}
mp = os.path.join(HERE, "data", "images", "images.json")
if os.path.exists(mp):
    imgmeta = json.load(open(mp))


def fit(draw, text, font_name, size, max_w):
    while size > 30:
        f = F(font_name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return F(font_name, size)


def base():
    im = Image.new("RGB", (1200, 630), PAPER)
    d = ImageDraw.Draw(im)
    d.text((64, 52), "DEPLOY.", font=F("Silkscreen-Regular.ttf", 34), fill=INK)
    d.text((1136, 60), "HIRING RADAR", font=F("IBMPlexMono-SemiBold.ttf", 24), fill=MUTED, anchor="ra")
    d.rectangle((0, 586, 1200, 630), fill=INK)
    d.text((64, 608), "deploytlv.com/radar", font=F("IBMPlexMono-SemiBold.ttf", 22), fill=PAPER, anchor="lm")
    d.text((1136, 608), f"Live from company job boards · {T['date']}", font=F("IBMPlexMono-SemiBold.ttf", 20), fill=(190, 184, 170), anchor="rm")
    return im, d


def card(c):
    im, d = base()
    x = 64
    logo = (imgmeta.get(c["name"]) or {}).get("logo")
    if logo and os.path.exists(os.path.join(HERE, "data", "images", logo)):
        tile = Image.new("RGB", (132, 132), (255, 255, 255))
        lg = Image.open(os.path.join(HERE, "data", "images", logo)).convert("RGBA")
        lg.thumbnail((104, 104))
        tile.paste(lg, ((132 - lg.width) // 2, (132 - lg.height) // 2), lg)
        mask = Image.new("L", (132, 132), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 131, 131), 26, fill=255)
        im.paste(tile, (x, 150), mask)
        d.rounded_rectangle((x, 150, x + 131, 281), 26, outline=INK, width=3)
        nx = x + 160
    else:
        nx = x
    d.text((nx, 215), c["name"], font=fit(d, c["name"], "ArchivoBlack-Regular.ttf", 84, 1136 - nx), fill=INK, anchor="lm")
    num = f"+{c['israel_new30']}"
    fn = F("ArchivoBlack-Regular.ttf", 150)
    d.text((x, 450), num, font=fn, fill=ORANGE, anchor="ls")
    w = d.textlength(num, font=fn)
    d.text((x + w + 28, 392), "new roles in Israel", font=F("ArchivoBlack-Regular.ttf", 46), fill=INK, anchor="ls")
    d.text((x + w + 30, 440), "in the last 30 days", font=F("IBMPlexMono-SemiBold.ttf", 28), fill=MUTED, anchor="ls")
    d.text((x, 520), f"{c['israel']:,} open in Israel" + (f"  ·  {c['ai_israel']} AI/ML" if c["ai_israel"] else ""),
           font=F("IBMPlexMono-SemiBold.ttf", 30), fill=INK, anchor="ls")
    return im


def overview():
    im, d = base()
    d.text((64, 250), f"{T['israel_new30']:,}", font=F("ArchivoBlack-Regular.ttf", 170), fill=ORANGE, anchor="ls")
    d.text((64, 340), "new tech jobs in Israel", font=F("ArchivoBlack-Regular.ttf", 64), fill=INK, anchor="ls")
    d.text((64, 410), "this month. One company per screen.", font=F("ArchivoBlack-Regular.ttf", 44), fill=INK, anchor="ls")
    d.text((64, 500), f"{T['israel']:,} open roles across {T['companies']} companies", font=F("IBMPlexMono-SemiBold.ttf", 30), fill=MUTED, anchor="ls")
    return im


def page(title, desc, img, target):
    e = html.escape
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}"><meta name="robots" content="noindex">
<meta property="og:type" content="website"><meta property="og:site_name" content="DeployTLV">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{img}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{img}">
<meta http-equiv="refresh" content="0;url=/db/radar/?ref=share{target}">
<script>location.replace("/db/radar/" + (location.search || "?ref=share") + "{target}");</script>
</head><body style="background:#0B0A08"><a href="/db/radar/{target}" style="color:#fff">Open the Deploy Hiring Radar</a></body></html>
"""


def main():
    out = os.path.join(HERE, "site", "og")
    os.makedirs(out, exist_ok=True)
    for c in cos:
        card(c).save(os.path.join(out, slug(c["name"]) + ".png"), optimize=True)
    overview().save(os.path.join(out, "radar.png"), optimize=True)
    print(f"share_cards: {len(cos) + 1} cards in site/og/")
    if "--pages" in sys.argv:
        d = sys.argv[sys.argv.index("--pages") + 1]
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page(
            "Deploy Hiring Radar: who's hiring in Israel right now",
            "Israeli tech companies hiring now, one per screen, live from their job boards. Updated daily.",
            OG_BASE + "radar.png", ""))
        for c in cos:
            s = slug(c["name"])
            os.makedirs(os.path.join(d, s), exist_ok=True)
            open(os.path.join(d, s, "index.html"), "w").write(page(
                f"{c['name']} is hiring in Israel",
                f"See {c['name']}'s open roles in Israel on the Deploy Hiring Radar. Live from their job board, updated daily.",
                OG_BASE + s + ".png", "#c=" + s))
        print(f"share pages: {len(cos) + 1} in {d}")


if __name__ == "__main__":
    main()
