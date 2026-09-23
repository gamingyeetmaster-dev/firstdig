"""Load the city's active-permits file into SQLite and roll rows up into
residential construction projects for the Teardown Feed."""
import csv
import datetime as dt
import re
from collections import defaultdict

from .geo import address_key

# Permit types that define a project (subsidiary plumbing/HVAC/drain rows
# are attached as signals but never create a project on their own).
PRIMARY_TYPES = {
    "New Houses", "Demolition Folder (DM)", "Small Residential Projects",
    "Building Additions/Alterations", "Residential Building Permit",
    "New Building", "Multiple Use Permit",
}
SUBSIDIARY_TYPES = {"Plumbing(PS)", "Mechanical(MS)", "Drain and Site Service", "Fire/Security Upgrade"}

KIND_LABELS = {
    "teardown": "Teardown and rebuild",
    "new_house": "New house",
    "multiplex": "Multiplex",
    "garden_suite": "Garden or laneway suite",
    "major_addition": "Major addition",
    "underpinning": "Underpinning / basement",
    "second_suite": "Second suite",
    "pool": "Pool",
    "new_building": "New building",
}
KIND_ORDER = ["teardown", "new_house", "multiplex", "garden_suite", "major_addition", "pool", "underpinning", "second_suite", "new_building"]

STAGE_LABELS = {"applied": "Applied", "issued": "Permit issued", "construction": "Under construction", "completed": "Completed"}

# Only projects first filed on or after this date are rolled up. Keeps the
# table small and the site focused on live opportunities.
PROJECT_SINCE = "2024-01-01"


def _cost(v):
    v = (v or "").replace("$", "").replace(",", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _date(v):
    v = (v or "").strip()[:10]
    return v if re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None


def load_permits(con, csv_path, geo, log=print):
    """Upsert every row from the city file. Returns count of new rows."""
    today = dt.date.today().isoformat()
    existing = {r[0] for r in con.execute("SELECT permit_key FROM permits")}
    new = 0
    batch = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            key = f"{r['PERMIT_NUM']}|{r['REVISION_NUM']}"
            street = " ".join(x for x in [r["STREET_NAME"], r["STREET_TYPE"], r["STREET_DIRECTION"]] if x and x.strip())
            address = f"{r['STREET_NUM'].strip()} {street}".strip()
            loc = geo.locate(r["GEO_ID"], r["STREET_NUM"], street)
            lat, lon = loc if loc else (None, None)
            hood = geo.neighbourhood(lat, lon) if loc else None
            batch.append((
                key, r["PERMIT_NUM"], r["REVISION_NUM"], r["PERMIT_TYPE"], r["STRUCTURE_TYPE"], (r["WORK"] or "").strip(),
                r["STREET_NUM"], r["STREET_NAME"], r["STREET_TYPE"], r["STREET_DIRECTION"],
                address, (r["POSTAL"] or "").strip(), r["GEO_ID"], r["WARD_GRID"],
                _date(r["APPLICATION_DATE"]), _date(r["ISSUED_DATE"]), _date(r["COMPLETED_DATE"]), (r["STATUS"] or "").strip(),
                (r["DESCRIPTION"] or "").strip(), r["CURRENT_USE"], r["PROPOSED_USE"],
                _int(r["DWELLING_UNITS_CREATED"]), _int(r["DWELLING_UNITS_LOST"]), _cost(r["EST_CONST_COST"]),
                (r["BUILDER_NAME"] or "").strip(), lat, lon, hood,
                today if key not in existing else None, today,
            ))
            if key not in existing:
                new += 1
            if len(batch) >= 5000:
                _flush(con, batch)
                batch = []
    _flush(con, batch)
    log(f"  permits: {new} new rows, {len(existing)} existing")
    return new


def _flush(con, batch):
    if not batch:
        return
    con.executemany(
        """INSERT INTO permits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(permit_key) DO UPDATE SET
             status=excluded.status, issued_date=excluded.issued_date, completed_date=excluded.completed_date,
             description=excluded.description, est_cost=excluded.est_cost, builder_name=excluded.builder_name,
             lat=COALESCE(excluded.lat, permits.lat), lon=COALESCE(excluded.lon, permits.lon),
             neighbourhood=COALESCE(excluded.neighbourhood, permits.neighbourhood),
             last_seen=excluded.last_seen""",
        batch,
    )


# ---------- project roll-up ----------

def classify(rows):
    """rows: list of permit dict rows for one address. Returns (kind, score) or (None, 0)."""
    types = {r["permit_type"] for r in rows}
    works = {(r["work"] or "").lower() for r in rows}
    text = " ".join((r["description"] or "").lower() for r in rows)
    cost = max((r["est_cost"] or 0) for r in rows)
    units = max((r["units_created"] or 0) for r in rows)
    has_demo = "Demolition Folder (DM)" in types or "demolition" in works or bool(re.search(r"\bdemoli", text))
    has_new_house = "New Houses" in types or ("New Building" in types and re.search(r"dwelling|house|residential|plex", text))
    is_multi = units >= 2 or bool(re.search(r"\b(duplex|triplex|fourplex|four-plex|multiplex|multi-plex|\d+\s*-?\s*unit)", text))

    if has_new_house and is_multi:
        return "multiplex", 90
    if has_new_house and has_demo:
        return "teardown", 100
    if has_new_house:
        return "new_house", 85
    if re.search(r"garden suite|laneway suite|laneway house|rear yard suite", text) or "new laneway / rear yard suite" in works:
        return "garden_suite", 70
    if re.search(r"\bpool\b", text) and not re.search(r"carpool|liverpool", text):
        return "pool", 65
    if has_demo and not has_new_house and re.search(r"dwelling|house", text):
        return "teardown", 80  # demolition filed, new-build permit usually follows within weeks
    if ("addition(s)" in works or "multiple projects" in works or re.search(r"\baddition\b", text)) and cost >= 150000:
        return "major_addition", 60 + min(int(cost / 100000), 25)
    if "underpinning" in works or re.search(r"underpin", text):
        return "underpinning", 40
    if "second suite (new)" in works or re.search(r"second (suite|unit)|basement apartment", text):
        return "second_suite", 30
    if "New Building" in types and cost >= 1000000:
        return "new_building", 50
    return None, 0


def stage_for(rows):
    statuses = {(r["status"] or "") for r in rows}
    if any(r["completed_date"] for r in rows) or "Closed" in statuses:
        return "completed"
    if "Inspection" in statuses:
        return "construction"
    if any(s in statuses for s in ("Permit Issued", "Revision Issued")):
        return "issued"
    return "applied"


def headline_for(kind, rows, cost, units):
    label = KIND_LABELS[kind]
    text = " ".join((r["description"] or "") for r in rows)
    m = re.search(r"(\d)\s*[- ]?\s*storey", text, re.I)
    storeys = f"{m.group(1)}-storey " if m else ""
    parts = [label]
    if kind in ("teardown", "new_house") and storeys:
        parts = [f"{label}: new {storeys}house"]
    if kind == "multiplex":
        m = re.search(r"(\d+)\s*-?\s*unit", text, re.I)
        n = max(units or 0, int(m.group(1)) if m else 0)
        parts = [f"{label}: {n} units" if n >= 2 else label]
    if cost:
        parts.append(f"est. ${cost/1e6:.1f}M" if cost >= 1e6 else f"est. ${cost/1e3:.0f}k")
    return " · ".join(parts)


def build_projects(con, log=print):
    rows = con.execute(
        """SELECT * FROM permits WHERE application_date >= ? AND permit_type IN ({}) AND street_num != ''""".format(
            ",".join("?" * len(PRIMARY_TYPES | SUBSIDIARY_TYPES))),
        (PROJECT_SINCE, *sorted(PRIMARY_TYPES | SUBSIDIARY_TYPES)),
    ).fetchall()
    groups = defaultdict(list)
    for r in rows:
        groups[address_key(r["street_num"], " ".join(x for x in [r["street_name"], r["street_type"], r["street_dir"]] if x))].append(dict(r))

    out = []
    for pid, grp in groups.items():
        primary = [r for r in grp if r["permit_type"] in PRIMARY_TYPES]
        if not primary:
            continue
        kind, score = classify(primary)
        if not kind:
            continue
        cost = max((r["est_cost"] or 0) for r in primary) or None
        units = max((r["units_created"] or 0) for r in primary) or None
        builders = [r["builder_name"] for r in grp if r["builder_name"]]
        dates = [r["application_date"] for r in grp if r["application_date"]]
        acts = [d for r in grp for d in (r["application_date"], r["issued_date"]) if d]
        issued = [r["issued_date"] for r in primary if r["issued_date"]]
        loc = next(((r["lat"], r["lon"], r["neighbourhood"]) for r in grp if r["lat"]), (None, None, None))
        desc = max((r["description"] or "" for r in primary), key=len)
        # recency bonus so the feed sorts sensibly
        first = min(dates) if dates else None
        age_days = (dt.date.today() - dt.date.fromisoformat(first)).days if first else 999
        score += max(0, 30 - age_days // 10)
        out.append((
            pid, grp[0]["address"], next((r["postal"] for r in grp if r["postal"]), None), grp[0]["ward"], loc[2],
            loc[0], loc[1], kind, stage_for(primary), headline_for(kind, primary, cost, units), desc[:600],
            cost, units, builders[0] if builders else None,
            first, max(acts) if acts else None, max(issued) if issued else None,
            ",".join(sorted({r["permit_num"] for r in grp})),
            ",".join(sorted({r["permit_type"] for r in grp})), score,
        ))
    con.execute("DELETE FROM projects")
    con.executemany("INSERT INTO projects VALUES (%s)" % ",".join("?" * 20), out)
    log(f"  projects: {len(out)} rolled up from {len(rows)} permit rows")
    return len(out)
