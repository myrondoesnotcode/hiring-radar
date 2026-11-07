"""Fetch a logo and a cover image for each company from its own website.

Cover = the site's og:image / twitter:image (the picture the company chose for link previews).
Logo = apple-touch-icon from the site, else Google's favicon service at 128px.
Writes data/images/<key>-cover.jpg, <key>-logo.png and data/images/images.json.
Run when companies change: python3 images.py
"""
import json, os, re, subprocess, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "images")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}

DOMAINS = {
    "Nebius": "nebius.com", "Cato Networks": "catonetworks.com", "Taboola": "taboola.com", "AppsFlyer": "appsflyer.com",
    "Wiz": "wiz.io", "Similarweb": "similarweb.com", "Moon Active": "moonactive.com", "JFrog": "jfrog.com",
    "Lemonade": "lemonade.com", "Payoneer": "payoneer.com", "SentinelOne": "sentinelone.com", "Wonderful": "wonderful.ai",
    "Navan": "navan.com", "Riskified": "riskified.com", "NICE": "nice.com", "Via": "ridewithvia.com", "Gong": "gong.io",
    "Island": "island.io", "Forter": "forter.com", "Tavily": "tavily.com", "Mixtiles": "mixtiles.com", "WalkMe": "walkme.com",
    "Axonius": "axonius.com", "Simply": "hellosimply.com", "Transmit Security": "transmitsecurity.com", "Yotpo": "yotpo.com",
    "HoneyBook": "honeybook.com", "Apiiro": "apiiro.com", "Orca Security": "orca.security", "Windward": "windward.ai",
    "DoorLoop": "doorloop.com", "Duda": "duda.co", "QuantHealth": "quanthealth.ai", "Salt Security": "salt.security",
    "Sisense": "sisense.com", "Lightrun": "lightrun.com", "Snyk": "snyk.io", "Torq": "torq.io", "Unit": "unit.co",
    "NVIDIA": "nvidia.com", "Mobileye": "mobileye.com", "Check Point": "checkpoint.com", "Wix": "wix.com",
    "VAST Data": "vastdata.com", "Cyera": "cyera.com", "Upwind": "upwind.io", "Aidoc": "aidoc.com", "AllCloud": "allcloud.io",
    "Kaltura": "kaltura.com", "Noma Security": "noma.security", "Coralogix": "coralogix.com", "Claroty": "claroty.com",
    "Fiverr": "fiverr.com", "Pentera": "pentera.io", "Sygnia": "sygnia.co", "Zenity": "zenity.io", "Port": "port.io",
    "Silverfort": "silverfort.com", "Oligo": "oligo.security", "Pagaya": "pagaya.com", "Guesty": "guesty.com",
    "Novee Security": "novee.security", "Playtika": "playtika.com", "IRONSCALES": "ironscales.com", "Lusha": "lusha.com",
    "OX Security": "ox.security", "Papaya Global": "papayaglobal.com", "Tipalti": "tipalti.com", "Viz.ai": "viz.ai",
    "Melio": "meliopayments.com", "Natural Intelligence": "naturalint.com", "Gloat": "gloat.com",
    "Legit Security": "legitsecurity.com", "Onyx Security": "onyx.security", "Aqua Security": "aquasec.com",
    "Checkmarx": "checkmarx.com", "Glassbox": "glassbox.com", "Overwolf": "overwolf.com", "Tailor Brands": "tailorbrands.com",
    "AI21 Labs": "ai21.com", "Cycode": "cycode.com", "D-ID": "d-id.com", "Komodor": "komodor.com", "Mend": "mend.io",
    "Qodo": "qodo.ai", "Bizzabo": "bizzabo.com", "Lasso Security": "lasso.security", "Zesty": "zesty.co",
    "Elementor": "elementor.com", "Optibus": "optibus.com", "Zencity": "zencity.io",
}


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.read()


def meta(html, *names):
    for n in names:
        for pat in (rf'<meta[^>]+(?:property|name)=["\']{n}["\'][^>]*content=["\']([^"\']+)',
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{n}["\']'):
            m = re.search(pat, html, re.I)
            if m:
                return m.group(1).replace("&amp;", "&")
    return None


def icon(html):
    for m in re.finditer(r'<link[^>]+>', html, re.I):
        tag = m.group(0)
        if re.search(r'rel=["\'][^"\']*apple-touch-icon', tag, re.I):
            h = re.search(r'href=["\']([^"\']+)', tag)
            if h:
                return h.group(1)
    return None


def key(name):
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def save(data, path, kind):
    tmp = path + ".src"
    open(tmp, "wb").write(data)
    if kind == "cover":  # 720px wide JPEG, enough for a phone background behind dark overlays
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "62", "--resampleWidth", "720", tmp, "--out", path],
                           capture_output=True)
    else:
        r = subprocess.run(["sips", "-s", "format", "png", "-Z", "128", tmp, "--out", path], capture_output=True)
    os.remove(tmp)
    return r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 500


def one(name):
    dom, k = DOMAINS[name], key(name)
    res = {"name": name, "domain": dom, "cover": None, "logo": None}
    html, base = "", f"https://{dom}/"
    try:
        base, raw = get(base)
        html = raw[:600000].decode("utf-8", "ignore")
    except Exception as e:
        res["error"] = str(e)[:80]
    og = meta(html, "og:image", "og:image:url", "twitter:image", "twitter:image:src") if html else None
    if og:
        try:
            _, data = get(urllib.parse.urljoin(base, og))
            p = os.path.join(OUT, f"{k}-cover.jpg")
            if save(data, p, "cover"):
                res["cover"] = os.path.basename(p)
        except Exception as e:
            res["cover_error"] = str(e)[:80]
    for src in ([urllib.parse.urljoin(base, icon(html))] if html and icon(html) else []) + \
               [f"https://www.google.com/s2/favicons?sz=128&domain={dom}"]:
        try:
            _, data = get(src)
            p = os.path.join(OUT, f"{k}-logo.png")
            if save(data, p, "logo"):
                res["logo"] = os.path.basename(p)
                break
        except Exception:
            continue
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(one, DOMAINS))
    json.dump({r["name"]: r for r in results}, open(os.path.join(OUT, "images.json"), "w"), indent=1)
    for r in results:
        print(f"{r['name']:20} cover={'Y' if r['cover'] else '-'} logo={'Y' if r['logo'] else '-'} {r.get('error', '') or r.get('cover_error', '')}")


if __name__ == "__main__":
    main()
