"""Upload data/report.json to the Deploy DB (Supabase) for deploytlv.com/db/radar/.

Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the environment (GitHub secrets in CI;
locally: set -a; . ~/Claude\\ Projects/deploytlv-db/.env.local; set +a). Skips quietly if they're missing.
Tables: public.radar_companies, public.radar_meta (migration 20261107_hiring_radar.sql in the deploytlv repo).
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL, KEY = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def rest(method, path, body=None, prefer=""):
    req = urllib.request.Request(f"{URL}/rest/v1/{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                                          "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def main():
    if not URL or not KEY:
        print("push_supabase: no SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY, skipped")
        return
    rep = json.load(open(os.path.join(HERE, "data", "report.json")))
    cos = [c for c in rep["companies"] if c["israel"] > 0]
    rows = [{"name": c["name"], "pos": i, "data": c, "updated_at": rep["totals"]["date"]} for i, c in enumerate(cos)]
    rest("POST", "radar_companies?on_conflict=name", rows, "resolution=merge-duplicates,return=minimal")
    names = ",".join('"' + c["name"].replace('"', '') + '"' for c in cos)
    rest("DELETE", f"radar_companies?name=not.in.({urllib.request.quote(names)})", prefer="return=minimal")
    rest("POST", "radar_meta?on_conflict=id", [{"id": 1, "totals": rep["totals"]}], "resolution=merge-duplicates,return=minimal")
    print(f"push_supabase: {len(rows)} companies, totals for {rep['totals']['date']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("push_supabase failed:", e, file=sys.stderr)
        sys.exit(1)
