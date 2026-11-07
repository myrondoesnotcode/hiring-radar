"""Weekly Hiring Radar alerts: new Israel roles (last 7 days) at the companies each subscriber follows.

Recipients: Supabase radar_alert_list() = active Deploy Log subscribers with at least one follow (deploytlv.com/db/radar/).
Only people with at least one new role at a followed company get an email. Sent with Resend.

  python3 alerts.py                 # dry run: prints who would get what, writes site/alerts-preview.html
  python3 alerts.py --to you@x.com  # one test email (uses the top 3 companies as follows)
  python3 alerts.py --send          # the real weekly send (CI, when the repo variable ALERTS_ON is true)

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, RESEND_API_KEY, RESEND_FROM.
"""
import datetime, html, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.environ.get
RADAR = "https://deploytlv.com/db/radar/"
slug = lambda s: re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", s.lower()))
esc = html.escape

report = json.load(open(os.path.join(HERE, "data", "report.json")))
T = report["totals"]
today = datetime.date.fromisoformat(T["date"])
BY = {c["name"]: c for c in report["companies"] if c["israel"] > 0}


def new_roles(c, days=7):
    out = []
    for j in c["latest_israel"]:
        try:
            d = datetime.date.fromisoformat(j["published"][:10])
        except Exception:
            continue
        if (today - d).days <= days:
            out.append(j)
    return out


def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def recipients():
    url, key = E("SUPABASE_URL", "").rstrip("/"), E("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        sys.exit("alerts: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing")
    return post(f"{url}/rest/v1/rpc/radar_alert_list", {}, {"apikey": key, "Authorization": f"Bearer {key}"}) or []


def email(name, follows):
    blocks, total = [], 0
    for co in follows:
        c = BY.get(co)
        if not c:
            continue
        roles = new_roles(c)
        if not roles:
            continue
        total += len(roles)
        items = "".join(
            f'<tr><td style="padding:10px 0;border-top:1px solid #D9D1BC"><a href="{esc(j["url"])}" style="color:#11100D;font-weight:600;text-decoration:none">{esc(j["title"])}</a>'
            f'<div style="color:#6B6558;font-size:13px">{esc(j.get("dept") or "")}{" · " if j.get("dept") else ""}{esc(j["location"])}</div></td>'
            f'<td style="padding:10px 0 10px 12px;border-top:1px solid #D9D1BC;text-align:right;white-space:nowrap"><a href="{esc(j["url"])}" style="color:#FF5A18;font-weight:700;text-decoration:none;font-size:13px">Apply ↗</a></td></tr>'
            for j in roles[:8])
        more = f'<p style="margin:6px 0 0;font-size:13px"><a href="{RADAR}?utm_source=alert#c={slug(co)}" style="color:#11100D">+{len(roles) - 8} more at {esc(co)}</a></p>' if len(roles) > 8 else ""
        blocks.append(f'<h2 style="font:900 20px Arial Black,Arial,sans-serif;margin:28px 0 4px">{esc(co)} <span style="color:#FF5A18">+{len(roles)}</span></h2>'
                      f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font:15px Arial,sans-serif">{items}</table>{more}')
    if not total:
        return None, None
    top = sorted(BY.values(), key=lambda c: -len(new_roles(c)))[:3]
    hot = " · ".join(f"{esc(c['name'])} +{len(new_roles(c))}" for c in top if new_roles(c))
    hi = f"Hi {esc(name.split()[0])}," if name else "Hi,"
    subject = f"{total} new role{'s' if total != 1 else ''} at companies you follow"
    body = f"""<div style="background:#F3EEDF;padding:24px 16px"><div style="max-width:560px;margin:0 auto;background:#FBF8EF;border-radius:16px;padding:28px 24px;color:#11100D;font:15px/1.5 Arial,sans-serif">
<div style="font:700 13px monospace;letter-spacing:.08em;color:#6B6558">DEPLOY. HIRING RADAR · WEEK OF {today:%b %-d}</div>
<p style="margin:18px 0 0">{hi} here's what the companies you follow opened in Israel this week.</p>
{''.join(blocks)}
<p style="margin:28px 0 0;padding:14px 16px;background:#F3EEDF;border-radius:12px;font-size:14px"><b>Hiring fastest this week:</b> {hot}</p>
<p style="text-align:center;margin:26px 0 6px"><a href="{RADAR}?utm_source=alert" style="display:inline-block;background:#FF5A18;color:#11100D;font-weight:700;padding:12px 22px;border-radius:999px;text-decoration:none">Open the Radar</a></p>
<p style="color:#6B6558;font-size:12px;margin:22px 0 0">Live from each company's public job board. You get this because you follow companies on the Deploy Hiring Radar; unfollow them there to stop these alerts. It's part of your free Deploy Log membership.</p>
</div></div>"""
    return subject, body


def send(to, subject, body):
    return post("https://api.resend.com/emails", {"from": E("RESEND_FROM"), "to": [to], "subject": subject, "html": body},
                {"Authorization": f"Bearer {E('RESEND_API_KEY')}"})


def main():
    args = sys.argv[1:]
    if "--to" in args:
        to = args[args.index("--to") + 1]
        follows = [c["name"] for c in sorted(BY.values(), key=lambda c: -len(new_roles(c)))[:3]]
        s, b = email("", follows)
        print("test:", s, send(to, "[Test] " + s, b))
        return
    try:
        rows = recipients()
    except Exception as e:  # e.g. radar_alert_list() not in Supabase yet
        if "--send" in args:
            raise
        print("alerts: couldn't read the alert list (dry run, skipping):", e)
        rows = []
    sent = skipped = 0
    preview = None
    for r in rows:
        s, b = email(r.get("name") or "", r["follows"])
        if not s:
            skipped += 1
            continue
        preview = preview or b
        if "--send" in args:
            send(r["email"], s, b)
        sent += 1
    if not preview:  # nobody qualifies yet: preview with the top 3 companies
        preview = email("", [c["name"] for c in sorted(BY.values(), key=lambda c: -len(new_roles(c)))[:3]])[1]
    os.makedirs(os.path.join(HERE, "site"), exist_ok=True)
    open(os.path.join(HERE, "site", "alerts-preview.html"), "w").write(preview or "")
    print(f"alerts: {len(rows)} following, {sent} {'sent' if '--send' in args else 'would get one (dry run)'}, {skipped} with nothing new")


if __name__ == "__main__":
    main()
