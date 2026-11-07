"""Turn the latest snapshot into hiring signals: data/report.json.

Signals per company: open roles, Israel roles, roles first posted in the last 30 days, AI/ML roles,
top teams, Israeli cities, US pay ranges, and opened/closed since the previous snapshot (once one exists).
Run after snapshot.py: python3 signals.py
"""
import csv, gzip, json, os, re, datetime, statistics, glob
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

AI_RE = re.compile(r"\b(ai|a\.i\.|ml|llm|llms|genai|gen ai|generative|machine learning|deep learning|nlp|computer vision|"
                   r"data scientist|applied scientist|research scientist|agent|agents|agentic|mlops|inference)\b", re.I)
CITIES = [("Tel Aviv", ["tel aviv", "tel-aviv", "tlv", "jaffa"]), ("Herzliya", ["herzliya", "herzliyya"]),
          ("Haifa", ["haifa", "matam"]), ("Jerusalem", ["jerusalem"]), ("Petah Tikva", ["petah tikva", "petach tikva", "petah tiqva"]),
          ("Ramat Gan", ["ramat gan"]), ("Ra'anana", ["ra'anana", "raanana"]), ("Netanya", ["netanya"]),
          ("Yokneam", ["yokneam", "yoqneam"]), ("Be'er Sheva", ["be'er sheva", "beer sheva", "beersheba"]),
          ("Rehovot", ["rehovot"]), ("Hod HaSharon", ["hod hasharon"]), ("Kfar Saba", ["kfar saba"]),
          ("Or Yehuda", ["or yehuda"]), ("Rosh HaAyin", ["rosh ha'ayin", "rosh haayin"]), ("Airport City", ["airport city"]),
          ("Givatayim", ["givatayim"]), ("Holon", ["holon"]), ("Caesarea", ["caesarea"])]


def city(loc):
    l = loc.lower()
    for name, keys in CITIES:
        if any(k in l for k in keys):
            return name
    return "Israel (other)"


def snapshots():  # YYYY-MM-DD.json.gz (older ones may be plain .json)
    d = os.path.join(DATA, "snapshots")
    return sorted(glob.glob(os.path.join(d, "*.json")) + glob.glob(os.path.join(d, "*.json.gz")), key=os.path.basename)


def load(p):
    return json.load(gzip.open(p, "rt") if p.endswith(".gz") else open(p))


def main():
    snaps = snapshots()
    cur = load(snaps[-1])
    prev = load(snaps[-2]) if len(snaps) > 1 else None
    today = datetime.date.fromisoformat(cur["date"])
    cutoff = (today - datetime.timedelta(days=30)).isoformat()
    meta = {r["name"]: r for r in csv.DictReader(open(os.path.join(HERE, "companies.csv")))}

    by = defaultdict(list)
    for j in cur["jobs"]:
        by[j["company"]].append(j)
    prev_ids = defaultdict(set)
    if prev:
        for j in prev["jobs"]:
            prev_ids[j["company"]].add(j["id"])

    companies = []
    for name, jobs in by.items():
        il = [j for j in jobs if j["israel"]]
        new30 = [j for j in jobs if j["published"] and j["published"] >= cutoff]
        il_new30 = [j for j in il if j in new30]
        ai = [j for j in jobs if AI_RE.search(j["title"])]
        ai_il = [j for j in ai if j["israel"]]
        paid = [j for j in jobs if j["pay_min"] and (j["pay_cur"] or "USD") == "USD" and not j["israel"]]
        teams = Counter(j["dept"] or "Other" for j in il).most_common(4)
        new_teams = Counter(j["dept"] or "Other" for j in new30).most_common(3)
        cities = Counter(city(j["location"]) for j in il).most_common(3)
        top_paid = max(paid, key=lambda j: j["pay_max"] or 0) if paid else None
        ids = {j["id"] for j in jobs}
        opened = len(ids - prev_ids[name]) if prev else None
        closed = len(prev_ids[name] - ids) if prev else None
        latest_il = sorted(il, key=lambda j: j["published"], reverse=True)[:50]
        c = {
            "name": name, "ats": meta.get(name, {}).get("ats", ""), "jobs": len(jobs), "israel": len(il),
            "israel_share": round(len(il) / len(jobs), 2) if jobs else 0,
            "new30": len(new30), "israel_new30": len(il_new30),
            "ai": len(ai), "ai_israel": len(ai_il), "ai_share_israel": round(len(ai_il) / len(il), 2) if il else 0,
            "teams_israel": teams, "new_teams": new_teams, "cities": cities,
            "us_pay_roles": len(paid),
            "us_pay_median_mid": int(statistics.median([(j["pay_min"] + j["pay_max"]) / 2 for j in paid])) if paid else None,
            "top_paid": {"title": top_paid["title"], "location": top_paid["location"], "min": top_paid["pay_min"],
                         "max": top_paid["pay_max"]} if top_paid else None,
            "opened": opened, "closed": closed,
            "latest_israel": [{"title": j["title"], "location": j["location"], "dept": j["dept"], "published": j["published"],
                               "url": j["url"]} for j in latest_il],
        }
        c["hooks"] = hooks(c)
        companies.append(c)
    companies.sort(key=lambda c: (-c["israel_new30"], -c["israel"]))

    all_il = [j for j in cur["jobs"] if j["israel"]]
    totals = {
        "date": cur["date"], "companies": len(companies), "jobs": len(cur["jobs"]), "israel": len(all_il),
        "israel_new30": sum(c["israel_new30"] for c in companies),
        "ai_israel": sum(c["ai_israel"] for c in companies),
        "cities": Counter(city(j["location"]) for j in all_il).most_common(8),
        "teams": Counter(j["dept"] or "Other" for j in all_il).most_common(10),
        "us_pay_roles": sum(c["us_pay_roles"] for c in companies),
        "has_previous": bool(prev), "previous_date": prev["date"] if prev else None,
        "failed": cur.get("failed", []),
    }
    json.dump({"totals": totals, "companies": companies}, open(os.path.join(DATA, "report.json"), "w"), indent=1)
    print(json.dumps(totals, indent=1))
    for c in companies[:15]:
        print(f"{c['name']:22} IL {c['israel']:4}  IL new30 {c['israel_new30']:3}  AI-IL {c['ai_israel']:3}  | {c['hooks'][0] if c['hooks'] else ''}")


def hooks(c):
    h = []
    if c["israel_new30"] >= 5:
        h.append(f"{c['name']} posted {c['israel_new30']} new roles in Israel in the last 30 days")
    if c["ai_israel"] >= 3:
        h.append(f"{c['ai_israel']} of {c['name']}'s {c['israel']} Israel roles are AI/ML")
    if c["new_teams"] and c["new_teams"][0][1] >= 4:
        t, n = c["new_teams"][0]
        h.append(f"Biggest new push: {t} ({n} roles posted this month)")
    if c["top_paid"] and c["top_paid"]["max"]:
        tp = c["top_paid"]
        h.append(f"Top US pay posted: {tp['title']} in {tp['location']}, ${tp['min']:,}-${tp['max']:,} base")
    if c["israel_share"] >= 0.6 and c["israel"] >= 10:
        h.append(f"{int(c['israel_share'] * 100)}% of open roles are in Israel")
    if c["opened"]:
        h.append(f"{c['opened']} roles opened, {c['closed']} closed since last snapshot")
    return h


if __name__ == "__main__":
    main()
