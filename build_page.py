"""Build the Hiring Radar page (feed + ranking) from data/report.json -> site/hiring-radar.html

Logos and cover images from images.py are embedded as data URIs (the published page can't load outside images).
"""
import base64, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
report = json.load(open(os.path.join(HERE, "data", "report.json")))
tpl = open(os.path.join(HERE, "page_template.html")).read()

imgdir = os.path.join(HERE, "data", "images")
imgs = {}
meta_path = os.path.join(imgdir, "images.json")
if os.path.exists(meta_path):
    for name, r in json.load(open(meta_path)).items():
        e = {}
        for kind, mime in (("cover", "image/jpeg"), ("logo", "image/png")):
            if r.get(kind):
                e[kind] = f"data:{mime};base64," + base64.b64encode(open(os.path.join(imgdir, r[kind]), "rb").read()).decode()
        if e:
            imgs[name] = e

os.makedirs(os.path.join(HERE, "site"), exist_ok=True)
out = os.path.join(HERE, "site", "hiring-radar.html")
html = tpl.replace("__DATA__", json.dumps(report).replace("</", "<\\/")).replace("__IMAGES__", json.dumps(imgs))
open(out, "w").write(html)
# GitHub Pages copy: a full document (the artifact version gets its head from the artifact wrapper)
head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="robots" content="noindex"></head><body>')
open(os.path.join(HERE, "site", "index.html"), "w").write(head + html + "</body></html>")

# Deploy DB copy (deploytlv.com/db/radar/index.html): no data inside. db_boot.html loads it from Supabase
# (radar_public / radar_for_me) and the images from GitHub Pages (_site/img/), then runs the page script.
MAIN = "<script>\nconst R = "
assert tpl.count(MAIN) == 1
db = tpl.replace("__DATA__", "null").replace("__IMAGES__", "{}").replace(MAIN, '<script type="text/plain" id="radar-main">\nconst R = ')
db_head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
           '<meta name="description" content="Israeli tech companies hiring right now, one per screen, live from their job boards. Free with the Deploy Log.">'
           '<meta name="robots" content="noindex"></head><body>')
open(os.path.join(HERE, "site", "db-radar.html"), "w").write(db_head + db + open(os.path.join(HERE, "db_boot.html")).read() + "</body></html>")
print(out, f"{len(html) / 1e6:.1f} MB, images for {len(imgs)} companies; site/db-radar.html for the Deploy DB")
