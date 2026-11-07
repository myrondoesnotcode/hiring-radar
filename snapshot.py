"""Take today's snapshot of every matched company's open roles.

Writes data/snapshots/YYYY-MM-DD.json.gz (all jobs) and appends per-company counts to data/history.csv.
Run once a day: python3 snapshot.py
"""
import csv, gzip, json, os, datetime
from concurrent.futures import ThreadPoolExecutor
from ats import FETCHERS

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def fetch(row):
    for _ in range(3):  # boards sometimes time out; retry before calling it failed
        jobs = FETCHERS[row["ats"]](row["slug"], row["name"])
        if jobs is not None:
            break
    return row["name"], jobs


def main():
    today = datetime.date.today().isoformat()
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, "companies.csv"))) if r["status"] == "ok"]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(fetch, rows))
    all_jobs, failed = [], []
    for name, jobs in results:
        if jobs is None:
            failed.append(name)
            continue
        all_jobs.extend(jobs)
    # boards with no publish date (Comeet): use the day a role first showed up. On a company's first day
    # nothing counts as new, so adding a company doesn't fake a hiring spike.
    seen, known = {}, set()
    snaps = sorted(f for f in os.listdir(os.path.join(DATA, "snapshots")) if f.endswith(".json.gz") and not f.startswith(today)) \
        if os.path.isdir(os.path.join(DATA, "snapshots")) else []
    if snaps:
        for j in json.load(gzip.open(os.path.join(DATA, "snapshots", snaps[-1]), "rt"))["jobs"]:
            known.add(j["company"])
            if "first_seen" in j:
                seen[(j["company"], j["id"])] = j
    for j in all_jobs:
        if j["published"]:
            continue
        old = seen.get((j["company"], j["id"]))
        if old:  # carried over: same first-seen day, same (maybe empty) date
            j["first_seen"], j["published"] = old["first_seen"], old["published"]
        else:
            j["first_seen"] = today
            j["published"] = today if j["company"] in known else ""
    os.makedirs(os.path.join(DATA, "snapshots"), exist_ok=True)
    with gzip.open(os.path.join(DATA, "snapshots", f"{today}.json.gz"), "wt") as f:
        json.dump({"date": today, "failed": failed, "jobs": all_jobs}, f)
    hist = os.path.join(DATA, "history.csv")
    new = not os.path.exists(hist)
    # drop any rows already written for today (re-runs)
    prev = [] if new else [r for r in csv.DictReader(open(hist)) if r["date"] != today]
    counts = {}
    for j in all_jobs:
        c = counts.setdefault(j["company"], [0, 0])
        c[0] += 1
        c[1] += j["israel"]
    with open(hist, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "company", "jobs", "israel_jobs"])
        w.writeheader()
        w.writerows(prev)
        for name, (n, il) in sorted(counts.items()):
            w.writerow({"date": today, "company": name, "jobs": n, "israel_jobs": il})
    print(f"{today}: {len(all_jobs)} jobs from {len(counts)} companies; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
