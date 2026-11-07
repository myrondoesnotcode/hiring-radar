"""Find each seed company's public job board. Writes companies.csv (name, ats, slug, jobs, israel_jobs, status).

A board only counts as a match if it has at least one job in Israel (guards against slug collisions,
e.g. 'unit' or 'port' belonging to an unrelated company). Run: python3 discover.py
"""
import csv, re, sys, os
from concurrent.futures import ThreadPoolExecutor
from ats import FETCHERS

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = ["security", "networks", "labs", "technologies", "software", "systems", "global", "insurance", "data", "cyber", "health"]


def slugs_for(name, hints):
    base = re.sub(r"[^a-z0-9]", "", name.lower().replace(".com", "com"))
    plain = re.sub(r"[^a-z0-9]", "", name.lower().split(".")[0])
    out = list(hints)
    for s in [base, plain, plain + "inc", plain + "hq", plain + "io", plain + "ai"]:
        if s and s not in out:
            out.append(s)
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    core = "".join(w for w in words if w not in STOP)
    if core and core not in out:
        out.append(core)
    dashed = "-".join(words)
    if dashed not in out:
        out.append(dashed)
    return out


def probe(args):
    name, hints = args
    best = None
    for slug in slugs_for(name, hints):
        for ats, fn in FETCHERS.items():
            jobs = fn(slug, name)
            if not jobs:
                continue
            il = sum(j["israel"] for j in jobs)
            cand = (il, len(jobs), ats, slug)
            if best is None or cand > best:
                best = cand
        if best and best[0] > 0:
            break  # first slug (hints first) with Israeli jobs is good enough
    if best is None:
        return {"name": name, "ats": "", "slug": "", "jobs": 0, "israel_jobs": 0, "status": "not_found"}
    il, n, ats, slug = best
    return {"name": name, "ats": ats, "slug": slug, "jobs": n, "israel_jobs": il,
            "status": "ok" if il > 0 else "no_israel_jobs"}


def main():
    seen, rows = set(), []
    for line in open(os.path.join(HERE, "seed_companies.txt")):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, h = line.partition("|")
        name = name.strip()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        rows.append((name, [x.strip() for x in h.split(",") if x.strip()]))
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(probe, rows))
    res.sort(key=lambda r: (-r["israel_jobs"], r["name"]))
    with open(os.path.join(HERE, "companies.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        w.writeheader()
        w.writerows(res)
    ok = [r for r in res if r["status"] == "ok"]
    print(f"{len(ok)} matched / {len(res)} seeds")
    for r in res:
        print(f"{r['status']:15} {r['name']:25} {r['ats']:15} {r['slug']:20} {r['jobs']:4} {r['israel_jobs']:4}")


if __name__ == "__main__":
    main()
