"""Read-side queries shared by pages, API, CSV export and digests."""
import datetime as dt
import json

from ..config import FREE_DELAY_DAYS
from ..pipeline.openings import CATEGORY_LABELS
from ..pipeline.permits import KIND_LABELS, KIND_ORDER, STAGE_LABELS

REDACTED = "Subscribers only"


def is_recent(d):
    """True when a date falls inside the free-view delay window."""
    if not d:
        return False
    return d > (dt.date.today() - dt.timedelta(days=FREE_DELAY_DAYS)).isoformat()


def neighbourhoods(con):
    rows = con.execute("SELECT neighbourhood, count(*) n FROM projects WHERE neighbourhood IS NOT NULL GROUP BY 1 ORDER BY 1").fetchall()
    return [r["neighbourhood"] for r in rows]


def parse_list(v):
    return [x for x in (v or "").split(",") if x]


def project_filters(args, full_access):
    """Build WHERE clause from query args. Returns (sql, params, active_filters)."""
    where, params, active = [], [], {}
    hoods = parse_list(args.get("hoods"))
    if hoods:
        where.append("neighbourhood IN (%s)" % ",".join("?" * len(hoods)))
        params += hoods
        active["hoods"] = hoods
    kinds = parse_list(args.get("kinds"))
    if kinds:
        where.append("kind IN (%s)" % ",".join("?" * len(kinds)))
        params += kinds
        active["kinds"] = kinds
    stages = parse_list(args.get("stages"))
    if stages:
        where.append("stage IN (%s)" % ",".join("?" * len(stages)))
        params += stages
        active["stages"] = stages
    days = int(args.get("days") or 30)
    active["days"] = days
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    where.append("last_activity >= ?")
    params.append(since)
    mincost = args.get("mincost")
    if mincost:
        where.append("est_cost >= ?")
        params.append(float(mincost))
        active["mincost"] = float(mincost)
    q = (args.get("q") or "").strip()
    if q:
        where.append("(address LIKE ? OR builder_name LIKE ? OR description LIKE ?)")
        params += [f"%{q}%"] * 3
        active["q"] = q
    if not full_access:
        cutoff = (dt.date.today() - dt.timedelta(days=FREE_DELAY_DAYS)).isoformat()
        where.append("first_filed <= ?")
        params.append(cutoff)
    return " AND ".join(where) or "1=1", params, active


def projects(con, args, full_access, limit=500):
    sql, params, active = project_filters(args, full_access)
    rows = con.execute(f"SELECT * FROM projects WHERE {sql} ORDER BY first_filed DESC, score DESC LIMIT ?", (*params, limit)).fetchall()
    total = con.execute(f"SELECT count(*) FROM projects WHERE {sql}", params).fetchone()[0]
    return [redact_project(dict(r), full_access) for r in rows], total, active


def redact_project(p, full_access):
    p["kind_label"] = KIND_LABELS.get(p["kind"], p["kind"])
    p["stage_label"] = STAGE_LABELS.get(p["stage"], p["stage"])
    if not full_access:
        p["builder_name"] = REDACTED if p["builder_name"] else None
        p["permit_nums"] = None
        p["redacted"] = True
    return p


def project(con, project_id):
    r = con.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if not r:
        return None, []
    permits = con.execute(
        "SELECT * FROM permits WHERE permit_num IN (%s) ORDER BY application_date, revision_num" % ",".join("?" * len(r["permit_nums"].split(","))),
        r["permit_nums"].split(","),
    ).fetchall()
    return dict(r), [dict(x) for x in permits]


def opening_filters(args, full_access):
    where, params, active = [], [], {}
    hoods = parse_list(args.get("hoods"))
    if hoods:
        where.append("neighbourhood IN (%s)" % ",".join("?" * len(hoods)))
        params += hoods
        active["hoods"] = hoods
    cats = parse_list(args.get("cats"))
    if cats:
        where.append("category IN (%s)" % ",".join("?" * len(cats)))
        params += cats
        active["cats"] = cats
    minsig = int(args.get("minsig") or 1)
    active["minsig"] = minsig
    where.append("signal_count >= ?")
    params.append(minsig)
    days = int(args.get("days") or 45)
    active["days"] = days
    where.append("last_signal >= ?")
    params.append((dt.date.today() - dt.timedelta(days=days)).isoformat())
    city = args.get("city") or "toronto"
    active["city"] = city
    if city == "toronto":
        where.append("(city IS NULL OR upper(city) IN ('TORONTO','NORTH YORK','SCARBOROUGH','ETOBICOKE','EAST YORK','YORK'))")
    q = (args.get("q") or "").strip()
    if q:
        where.append("(name LIKE ? OR address LIKE ? OR owner LIKE ?)")
        params += [f"%{q}%"] * 3
        active["q"] = q
    if not full_access:
        cutoff = (dt.date.today() - dt.timedelta(days=FREE_DELAY_DAYS)).isoformat()
        where.append("last_signal <= ?")
        params.append(cutoff)
    return " AND ".join(where), params, active


def openings(con, args, full_access, limit=500):
    sql, params, active = opening_filters(args, full_access)
    rows = con.execute(f"SELECT * FROM openings WHERE {sql} ORDER BY last_signal DESC, score DESC LIMIT ?", (*params, limit)).fetchall()
    total = con.execute(f"SELECT count(*) FROM openings WHERE {sql}", params).fetchone()[0]
    return [redact_opening(dict(r), full_access) for r in rows], total, active


def redact_opening(o, full_access):
    o["category_label"] = CATEGORY_LABELS.get(o["category"], o["category"])
    o["signal_list"] = json.loads(o["signals"] or "[]")
    o["signal_types"] = sorted({s["type"] for s in o["signal_list"]})
    if o["signal_count"] > 8 and not o["name"]:
        o["name"] = "Multiple tenants (mall or tower)"
    if not full_access:
        o["name"] = REDACTED if o["name"] else None
        o["phone"] = REDACTED if o["phone"] else None
        o["owner"] = REDACTED if o["owner"] else None
        # keep street, hide the number
        if o["address"]:
            o["address"] = " ".join(o["address"].split(" ")[1:]) + " (number hidden)"
        o["redacted"] = True
    return o


def opening(con, opening_id):
    r = con.execute("SELECT * FROM openings WHERE opening_id=?", (opening_id,)).fetchone()
    return dict(r) if r else None


def stats(con):
    today = dt.date.today()
    d7 = (today - dt.timedelta(days=7)).isoformat()
    d30 = (today - dt.timedelta(days=30)).isoformat()
    s = {
        "projects_7d": con.execute("SELECT count(*) FROM projects WHERE first_filed>=?", (d7,)).fetchone()[0],
        "projects_30d": con.execute("SELECT count(*) FROM projects WHERE first_filed>=?", (d30,)).fetchone()[0],
        "teardowns_30d": con.execute("SELECT count(*) FROM projects WHERE first_filed>=? AND kind IN ('teardown','new_house','multiplex')", (d30,)).fetchone()[0],
        "cost_30d": con.execute("SELECT coalesce(sum(est_cost),0) FROM projects WHERE first_filed>=?", (d30,)).fetchone()[0],
        "openings_30d": con.execute("SELECT count(*) FROM openings WHERE last_signal>=?", (d30,)).fetchone()[0],
        "openings_multi_30d": con.execute("SELECT count(*) FROM openings WHERE last_signal>=? AND signal_count>=2", (d30,)).fetchone()[0],
        "liquor_live": con.execute("SELECT count(*) FROM liquor_apps WHERE deadline>=?", (today.isoformat(),)).fetchone()[0],
        "last_run": con.execute("SELECT value FROM meta WHERE key='last_run'").fetchone(),
    }
    s["last_run"] = s["last_run"][0] if s["last_run"] else None
    return s


def kinds():
    return [(k, KIND_LABELS[k]) for k in KIND_ORDER]


def categories():
    return list(CATEGORY_LABELS.items())
