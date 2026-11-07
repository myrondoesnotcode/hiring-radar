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
print(out, f"{len(html) / 1e6:.1f} MB, images for {len(imgs)} companies")
