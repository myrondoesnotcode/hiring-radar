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
    # "eu/<slug>" = Lever's EU instance (e.g. Mobileye)
    host, slug = ("api.eu.lever.co", slug[3:]) if slug.startswith("eu/") else ("api.lever.co", slug)
    d = get(f"https://{host}/v0/postings/{slug}?mode=json")
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


def page(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (deploy-hiring-tracker)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError):
        return None


def comeet(slug, company):
    """slug = "<company-slug>/<company-uid>", e.g. "zenity/19.000". Reads Comeet's public hosted careers page.
    Comeet gives no publish date, so published stays empty; snapshot.py fills it with the day the role first showed up."""
    s = page(f"https://www.comeet.com/jobs/{slug}")
    m = re.search(r"COMPANY_POSITIONS_DATA\s*=\s*\[", s or "")
    if not m:
        return None
    try:
        d, _ = json.JSONDecoder().raw_decode(s[m.end() - 1:])
    except ValueError:
        return None
    out = []
    for j in d:
        if j.get("is_internal"):
            continue
        l = j.get("location") or {}
        loc = l.get("name") or ", ".join(x for x in [l.get("city"), l.get("country")] if x)
        out.append(job(company, "comeet", j.get("uid"), j.get("name"), loc, is_israel(loc, l.get("country") == "IL" and "israel"),
                       j.get("department"), j.get("url_active_page") or j.get("url_comeet_hosted_page"), "", None,
                       l.get("is_remote") or j.get("workplace_type") == "Remote"))
    return out


def post(url, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**UA, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError):
        return None


def workday(slug, company):
    """slug = "<tenant>/<wdN>/<site>", e.g. "nvidia/wd5/NVIDIAExternalCareerSite". Public Workday job search.
    Big Workday boards hold thousands of roles, so only the Israel roles are listed; the board's total is kept
    as extra placeholder rows (israel=False, no title) so the worldwide count stays right."""
    try:
        tenant, wd, site = slug.split("/")
    except ValueError:
        return None
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    first = post(api, {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""})
    if not first or "jobPostings" not in first:
        return None
    total = first.get("total") or 0
    facet = None
    def walk(fs):
        nonlocal facet
        for f in fs or []:
            for v in f.get("values") or []:
                if "values" in v:
                    walk([v])
                elif (v.get("descriptor") or "").strip().lower() == "israel" and facet is None:
                    facet = (f.get("facetParameter"), v.get("id"))
    walk(first.get("facets"))
    il = []
    if facet:
        off, n = 0, None
        while off < 1000:
            d = post(api, {"appliedFacets": {facet[0]: [facet[1]]}, "limit": 20, "offset": off, "searchText": ""})
            if not d or not d.get("jobPostings"):
                break
            il += d["jobPostings"]
            n = n or d.get("total") or 0  # Workday only sends the total on the first page
            off += 20
            if off >= n:
                break
    import datetime
    today = datetime.date.today()
    def posted(t):
        t = (t or "").lower()
        if "today" in t: return today.isoformat()
        if "yesterday" in t: return (today - datetime.timedelta(1)).isoformat()
        m = re.search(r"(\d+)\+? days? ago", t)
        return (today - datetime.timedelta(int(m.group(1)))).isoformat() if m and "+" not in t else ""
    out = []
    for j in il:
        loc = j.get("locationsText") or ""
        loc = loc if is_israel(loc) else (loc + " · Israel").strip(" ·")
        jid = (j.get("bulletFields") or [j.get("externalPath")])[0]
        out.append(job(company, "workday", jid, j.get("title"), loc, True, "", base + "/" + site + (j.get("externalPath") or ""),
                       posted(j.get("postedOn")), None, "remote" in loc.lower()))
    for k in range(max(0, total - len(out))):
        out.append(job(company, "workday", f"_other{k}", "", "", False, "", "", ""))
    return out


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable,
            "smartrecruiters": smartrecruiters, "comeet": comeet, "workday": workday}
