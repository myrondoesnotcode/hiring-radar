"""Fetchers for public job-board APIs. Each returns a list of normalized jobs or None if the board doesn't exist."""
import json, re, urllib.request, urllib.error, html

UA = {"User-Agent": "deploy-hiring-tracker/0.1"}

IL_WORDS = ["israel", "tel aviv", "tel-aviv", "herzliya", "herzliyya", "haifa", "jerusalem", "petah tikva", "petach tikva",
            "petah tiqva", "ramat gan", "ra'anana", "raanana", "netanya", "rehovot", "yokneam", "yoqneam", "be'er sheva",
            "beer sheva", "beersheba", "hod hasharon", "kfar saba", "caesarea", "or yehuda", "rosh ha'ayin", "rosh haayin",
            "airport city", "modi'in", "modiin", "givatayim", "bnei brak", "holon", "rishon", "tlv", "jaffa", "ness ziona",
            "nes ziona", "lod", "kiryat", "ashdod", "ashkelon", "nazareth", "migdal haemek", "matam"]


def is_israel(*parts):
    s = " ".join(p for p in parts if p).lower()
    if any(w in s for w in IL_WORDS):
        return True
    return bool(re.search(r"(^|[\s,(])il($|[\s,)])", s))


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError):
        return None


def job(company, ats, jid, title, location, israel, dept, url, published, pay=None, remote=False):
    return {"company": company, "ats": ats, "id": str(jid), "title": (title or "").strip(), "location": (location or "").strip(),
            "israel": bool(israel), "dept": (dept or "").strip(), "url": url, "published": (published or "")[:10],
            "pay_min": pay[0] if pay else None, "pay_max": pay[1] if pay else None, "pay_cur": pay[2] if pay else None,
            "remote": bool(remote)}


def greenhouse(slug, company):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?pay_transparency=true")
    if not d or "jobs" not in d:
        return None
    # department lookup
    depts = {}
    dd = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/departments") or {}
    for dep in dd.get("departments", []):
        for j in dep.get("jobs", []):
            depts[j["id"]] = dep["name"]
    out = []
    for j in d["jobs"]:
        loc = (j.get("location") or {}).get("name", "")
        pay = None
        for pr in j.get("pay_input_ranges") or []:
            if pr.get("min_cents"):
                pay = (pr["min_cents"] // 100, pr["max_cents"] // 100, pr.get("currency_type"))
                break
        out.append(job(company, "greenhouse", j["id"], j.get("title"), loc, is_israel(loc), depts.get(j["id"], ""),
                       j.get("absolute_url"), j.get("first_published") or j.get("updated_at"), pay,
                       "remote" in loc.lower()))
    return out


def lever(slug, company):
    d = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(d, list):
        return None
    out = []
    for j in d:
        c = j.get("categories") or {}
        locs = c.get("allLocations") or [c.get("location", "")]
        loc = " / ".join(l for l in locs if l)
        import datetime
        pub = datetime.datetime.utcfromtimestamp(j["createdAt"] / 1000).strftime("%Y-%m-%d") if j.get("createdAt") else ""
        sr = j.get("salaryRange") or {}
        pay = (sr["min"], sr["max"], sr.get("currency")) if sr.get("min") else None
        out.append(job(company, "lever", j["id"], j.get("text"), loc, is_israel(loc, j.get("country")),
                       c.get("team") or c.get("department"), j.get("hostedUrl"), pub, pay,
                       j.get("workplaceType") == "remote"))
    return out


def ashby(slug, company):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not d or "jobs" not in d:
        return None
    out = []
    for j in d["jobs"]:
        if j.get("isListed") is False:
            continue
        addr = ((j.get("address") or {}).get("postalAddress") or {})
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        loc = " / ".join(l for l in locs if l)
        pay = None
        comp = j.get("compensation") or {}
        for t in comp.get("summaryComponents") or []:
            if t.get("compensationType") == "Salary" and t.get("minValue"):
                pay = (int(t["minValue"]), int(t.get("maxValue") or t["minValue"]), t.get("currencyCode"))
                break
        out.append(job(company, "ashby", j.get("id"), j.get("title"), loc,
                       is_israel(loc, addr.get("addressCountry")), j.get("department") or j.get("team"),
                       j.get("jobUrl"), j.get("publishedAt"), pay, j.get("isRemote")))
    return out


def workable(slug, company):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if not d or "jobs" not in d:
        return None
    out = []
    for j in d["jobs"]:
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        out.append(job(company, "workable", j.get("shortcode"), j.get("title"), loc, is_israel(loc),
                       j.get("department"), j.get("url") or j.get("shortlink"), j.get("published_on") or j.get("created_at"),
                       None, j.get("telecommuting")))
    return out


def smartrecruiters(slug, company):
    d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100")
    if not d or not d.get("content"):
        return None
    out, offset = [], 0
    while d and d.get("content"):
        for j in d["content"]:
            l = j.get("location") or {}
            loc = ", ".join(x for x in [l.get("city"), l.get("country")] if x)
            out.append(job(company, "smartrecruiters", j.get("id"), j.get("name"), loc,
                           is_israel(loc, l.get("country")), (j.get("department") or {}).get("label"),
                           f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}", j.get("releasedDate"), None,
                           l.get("remote")))
        offset += 100
        if offset >= d.get("totalFound", 0) or offset > 2000:
            break
        d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
    return out


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable,
            "smartrecruiters": smartrecruiters}
