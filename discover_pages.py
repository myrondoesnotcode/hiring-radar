"""Second discovery pass: open each unmatched company's own careers page and look for the job board it links to
(Comeet, Workday, or a Greenhouse/Lever/Ashby/Workable/SmartRecruiters board under a slug discover.py didn't guess).

Reads companies.csv, re-checks every company that isn't "ok", and updates its row when a board with Israel roles is found.
Domains come from seed_companies.txt hints (domain=foo.com) or are guessed from the name.
  python3 discover_pages.py            # all unmatched companies
  python3 discover_pages.py Wix Zenity # just these
"""
import csv, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from ats import FETCHERS, page

HERE = os.path.dirname(os.path.abspath(__file__))
PATHS = ["/careers", "/careers/", "/jobs", "/company/careers", "/about/careers", "/careers/open-positions", "/join-us", ""]
PATTERNS = [
    ("comeet", r"comeet\.com/jobs/([a-z0-9_.-]+)/([0-9A-F]{2}\.[0-9A-F]{3})", lambda m: f"{m[0].lower()}/{m[1]}"),
    ("workday", r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)", lambda m: f"{m[0]}/{m[1]}/{m[2]}"),
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9]+)", lambda m: m[0]),
    ("greenhouse", r"greenhouse\.io/[^\"']*?for=([a-z0-9]+)", lambda m: m[0]),
    ("lever", r"jobs\.lever\.co/([a-z0-9-]+)", lambda m: m[0]),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9.-]+)", lambda m: m[0]),
    ("workable", r"apply\.workable\.com/([a-z0-9-]+)", lambda m: m[0]),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9-]+)", lambda m: m[0]),
]
SKIP = {"j", "api", "embed", "jobs", "careers", "en-us", "wday"}


def domains(name, hint):
    if hint:
        return [hint]
    b = re.sub(r"[^a-z0-9]", "", name.lower().replace(".com", "").replace(".ai", "").replace(".io", ""))
    return [f"{b}.com", f"{b}.io", f"{b}.ai", f"{b}.co", f"{b}.co.il"]


def candidates(html):
    out = []
    for ats, rx, mk in PATTERNS:
        for m in re.findall(rx, html, re.I if ats != "comeet" else 0):
            m = m if isinstance(m, tuple) else (m,)
            if m[-1].lower() in SKIP:
                continue
            c = (ats, mk(m))
            if c not in out:
                out.append(c)
    return out


def scan(args):
    name, hint = args
    tried = set()
    for d in domains(name, hint):
        for p in PATHS:
            for host in (d, "www." + d):
                html = page(f"https://{host}{p}", timeout=12)
                if not html:
                    continue
                for ats, slug in candidates(html):
                    if (ats, slug) in tried:
                        continue
                    tried.add((ats, slug))
                    jobs = FETCHERS[ats](slug, name)
                    if jobs:
                        il = sum(j["israel"] for j in jobs)
                        if il:
                            return {"name": name, "ats": ats, "slug": slug, "jobs": len(jobs), "israel_jobs": il, "status": "ok"}
                break  # the bare host answered; don't retry www.
            else:
                continue
        if tried:
            break  # this domain had a careers page; don't guess other TLDs
    return None


def main():
    hints = {}
    for line in open(os.path.join(HERE, "seed_companies.txt")):
        name, _, h = line.strip().partition("|")
        for x in h.split(","):
            if x.strip().startswith("domain="):
                hints[name.strip().lower()] = x.strip()[7:]
    rows = list(csv.DictReader(open(os.path.join(HERE, "companies.csv"))))
    only = {a.lower() for a in sys.argv[1:]}
    todo = [(r["name"], hints.get(r["name"].lower())) for r in rows if r["status"] != "ok" and (not only or r["name"].lower() in only)]
    with ThreadPoolExecutor(8) as ex:
        found = {r["name"]: r for r in ex.map(scan, todo) if r}
    for r in rows:
        if r["name"] in found:
            r.update(found[r["name"]])
    rows.sort(key=lambda r: (-int(r["israel_jobs"] or 0), r["name"]))
    with open(os.path.join(HERE, "companies.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"found {len(found)} of {len(todo)}")
    for n, r in sorted(found.items()):
        print(f"  {n:25} {r['ats']:15} {r['slug']:40} {r['israel_jobs']:>4} IL / {r['jobs']}")
    print("still missing:", ", ".join(sorted(n for n, _ in todo if n not in found)))


if __name__ == "__main__":
    main()
