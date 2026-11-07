# Deploy Hiring Radar

Tracks open roles at Israeli tech companies from their public job-board APIs (Greenhouse, Lever, Ashby, Workable, SmartRecruiters). It needs no API keys and nothing beyond the Python standard library.

```
python3 discover.py     # seed_companies.txt -> companies.csv (re-run when you add companies)
python3 snapshot.py     # today's jobs -> data/snapshots/YYYY-MM-DD.json.gz + data/history.csv
python3 signals.py      # -> data/report.json (30-day postings, AI roles, teams, cities, US pay, opened/closed)
python3 images.py       # logos + cover images from each company's site -> data/images/ (re-run when companies change; add the domain to DOMAINS)
python3 build_page.py   # -> site/index.html (GitHub Pages) + site/hiring-radar.html (artifact), images embedded
```

- Run `snapshot.py` once a day. Opened/closed counts and growth need at least two snapshots.
- To add a company, add a line to `seed_companies.txt` (`Name | slug-hint`) and re-run `discover.py`.
- "Last 30 days" uses each posting's first-published date, which resets when a company reposts a role.
- US pay comes from US postings only (some US states require pay ranges). Israeli postings have no pay.
- Not covered yet: Comeet and Workday (monday, Wix, Check Point, CyberArk and others).

## Hosting (test phase)

`.github/workflows/daily.yml` runs every day at 04:00 UTC: snapshot → signals → build, commits the new data, and publishes `site/index.html` to GitHub Pages. A push to `main` just rebuilds and publishes. `images.py` runs locally only (it uses macOS `sips`), so commit `data/images/` after re-running it. The page is `noindex` while testing. At launch, add a `CNAME` file (e.g. `radar.deploytlv.com`).
