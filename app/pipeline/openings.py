"""Opening Soon: join AGCO liquor applications, new City of Toronto business
licences, and commercial fit-out building permits by address."""
import csv
import datetime as dt
import json
import re
from collections import defaultdict

from .geo import address_key, parse_free_address


def unit_of(addr):
    """'2900 Warden Ave, #218 & 219' -> '218'; '25 The West Mall, F001' -> 'F001'; '848 KING ST W, GROUND FL' -> None."""
    a = (addr or "").upper()
    m = re.search(r"(?:#|\b(?:UNIT|SUITE|STE|APT)\s*#?\s*)([A-Z]?\d+[A-Z]?)", a)
    if m:
        return m.group(1)
    m = re.search(r",\s*([A-Z]{0,2}\d{1,5}[A-Z]{0,2})\s*(?:&|,|$)", a.split(",", 1)[-1] and a[a.index(","):] if "," in a else "")
    return m.group(1) if m else None


def opening_key(num, street, unit=None):
    k = address_key(num, street)
    return f"{k} #{unit}" if unit else k

LICENCE_CATEGORIES = {
    "EATING OR DRINKING ESTABLISHMENT": "restaurant",
    "TAKE-OUT OR RETAIL FOOD ESTABLISHMENT": "takeout",
    "BAKE SHOP": "bakery",
    "PERSONAL SERVICES SETTINGS": "salon_spa",
    "RETAIL STORE (FOOD)": "grocery",
    "ENTERTAINMENT ESTABLISHMENT/NIGHTCLUB": "bar",
    "BILLIARD HALL": "bar",
    "BODY RUB PARLOUR": None,
    "HOLISTIC CENTRE": "clinic",
    "SIDEWALK CAFE": "restaurant",
    "MARKETPLACE": "retail",
    "CANNABIS RETAIL": "retail",
    "ENTERTAINMENT PLACE OF ASSEMBLY": "bar",
    "EXPANDED EATING/DRINKING ESTABLISHMENT": "restaurant",
    "CURB LANE CAFE": "restaurant",
    "AMUSEMENT ESTABLISHMENT": "fitness",
    "PET SHOP": "retail",
    "SECOND HAND SHOP": "retail",
    "PRECIOUS METAL SHOP": "retail",
    "SMOKE SHOP": "retail",
    "VAPOUR PRODUCT RETAILER": "retail",
    "LAUNDRY PREMISES": "other",
    "THEATRE": "bar",
}

CATEGORY_LABELS = {
    "restaurant": "Restaurant", "bar": "Bar or lounge", "cafe": "Café", "bakery": "Bakery", "takeout": "Take-out or quick service",
    "grocery": "Grocery or food retail", "salon_spa": "Salon, barber or spa", "clinic": "Clinic or dental", "fitness": "Gym or studio",
    "retail": "Retail", "daycare": "Daycare or school", "office": "Office", "brewery": "Brewery or winery", "other": "Other commercial",
}

# keyword -> category, first match wins (order matters)
PERMIT_KEYWORDS = [
    (r"\b(brewery|brew pub|winery|distillery|tied house)\b", "brewery"),
    (r"\b(caf[eé]|coffee|espresso|tea shop|bubble tea|boba)\b", "cafe"),
    (r"\b(bakery|bake shop|patisserie|donut|bagel)\b", "bakery"),
    (r"\b(bar|pub|lounge|tavern|nightclub|cocktail|wine bar|taproom)\b", "bar"),
    (r"\b(restaurant|resto|bistro|eatery|dining|kitchen|pizza|sushi|ramen|noodle|grill|bbq|shawarma|taqueria|diner|food hall|group a2|a-2 occupancy|assembly occupancy)\b", "restaurant"),
    (r"\b(take-?out|quick service|fast food|acai|smoothie|juice|ice cream|gelato|dessert|poke|shawarma)\b", "takeout"),
    (r"\b(grocery|supermarket|market|convenience|butcher|fishmonger|food store|lcbo)\b", "grocery"),
    (r"\b(dental|dentist|orthodont|clinic|medical|physio|chiro|pharmacy|optical|optometr|veterinar|vet clinic|health centre|wellness|laser|aesthetic|med ?spa)\b", "clinic"),
    (r"\b(salon|barber|hair|nail|spa|lash|brow|beauty|tattoo|massage)\b", "salon_spa"),
    (r"\b(gym|fitness|yoga|pilates|crossfit|boxing|climbing|studio|martial arts|dance)\b", "fitness"),
    (r"\b(daycare|child ?care|montessori|school|academy|tutoring|learning centre)\b", "daycare"),
    (r"\b(retail|store|shop|boutique|showroom|dispensary|cannabis|mercantile|group e)\b", "retail"),
    (r"\b(office|tenant fit|fit-?up|fit out|group d)\b", "office"),
]

COMMERCIAL_PERMIT_TYPES = {"Building Additions/Alterations", "New Building", "Non-Residential Building Permit", "Multiple Use Permit", "Designated Structures"}
LOOKBACK_DAYS = 150

TORONTO_CITIES = {"TORONTO", "NORTH YORK", "SCARBOROUGH", "ETOBICOKE", "EAST YORK", "YORK"}


def _date(v):
    v = (v or "").strip()[:10]
    return v if re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None


def _agco_date(v):
    try:
        return dt.datetime.strptime(v.strip(), "%d-%b-%y").date().isoformat()
    except Exception:
        return None


def categorize_text(text):
    t = (text or "").lower()
    for pat, cat in PERMIT_KEYWORDS:
        if re.search(pat, t):
            return cat
    return None


def extract_name(desc):
    """Pull a business name from a permit description when the applicant wrote one in."""
    d = desc or ""
    for pat in (r"\(([^)]{3,40})\)", r"for\s+(?:a\s+new\s+)?['\"]?([A-Z][A-Za-z0-9&' ]{2,40}?)['\"]?\s+(?:restaurant|caf|bakery|dental|clinic|salon|studio|store)",
                r"-\s*([A-Z][A-Z0-9&' ]{3,40})\s*(?:DRYWALL|INTERIOR|TENANT)"):
        m = re.search(pat, d)
        if m:
            name = m.group(1).strip(" .-")
            if re.fullmatch(r"[\d\s&,'-]+", name) or re.search(r"\b(group|occupancy|unit|floor|level|storey|sq|ft|m2|seats?|alteration|existing|proposed|interior|tenant|retail|commercial|building|new)\b", name, re.I):
                continue
            if True:
                return name.title() if name.isupper() else name
    return None


# ---------- loaders ----------

def load_licences(con, csv_path, geo, log=print):
    today = dt.date.today().isoformat()
    cutoff = (dt.date.today() - dt.timedelta(days=LOOKBACK_DAYS * 2)).isoformat()
    existing = {r[0] for r in con.execute("SELECT licence_no FROM licences")}
    batch, n = [], 0
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        for r in csv.DictReader(f):
            cat = r.get("Category", "").strip()
            if cat not in LICENCE_CATEGORIES or LICENCE_CATEGORIES[cat] is None:
                continue
            issued = _date(r.get("Issued"))
            if not issued or issued < cutoff:
                continue
            addr1 = (r.get("Licence Address Line 1") or "").strip()
            num, street = parse_free_address(addr1)
            loc = geo.locate(None, num, street) if num else None
            lat, lon = loc if loc else (None, None)
            batch.append((
                r["Licence No."], cat, (r.get("Operating Name") or "").strip(), (r.get("Client Name") or "").strip(),
                issued, _date(r.get("Cancel Date")), _date(r.get("Last Record Update")),
                (r.get("Business Phone") or "").strip(), addr1, " ".join(x.strip() for x in [r.get("Licence Address Line 2", ""), r.get("Licence Address Line 3", "")] if x.strip()),
                (r.get("Ward") or "").strip(), lat, lon, geo.neighbourhood(lat, lon) if loc else None,
                today,
            ))
            if r["Licence No."] not in existing:
                n += 1
    con.executemany(
        """INSERT INTO licences VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(licence_no) DO UPDATE SET cancel_date=excluded.cancel_date, last_update=excluded.last_update,
             operating_name=excluded.operating_name, phone=excluded.phone""",
        batch,
    )
    log(f"  licences: {len(batch)} relevant rows loaded, {n} new")
    return n


def load_liquor(con, csv_path, geo, log=print):
    today = dt.date.today().isoformat()
    existing = {r[0] for r in con.execute("SELECT file_number FROM liquor_apps")}
    batch, n = [], 0
    with open(csv_path, newline="", encoding="utf-8-sig", errors="ignore") as f:
        for r in csv.DictReader(f):
            city = (r.get("city") or "").strip().upper()
            num, street = parse_free_address(r.get("address"))
            loc = geo.locate(None, num, street) if (num and city in TORONTO_CITIES) else None
            lat, lon = loc if loc else (None, None)
            batch.append((
                r["file_number"].strip(), city.title(), (r.get("premises_name") or "").strip(" ,"), (r.get("address") or "").strip(),
                _agco_date(r.get("deadline_objections_submissions", "")), r.get("application_type_en", "").strip(), r.get("licence_type_en", "").strip(),
                r.get("areas", "").strip(), lat, lon, geo.neighbourhood(lat, lon) if loc else None, today, today,
            ))
            if r["file_number"].strip() not in existing:
                n += 1
    con.executemany(
        """INSERT INTO liquor_apps VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(file_number) DO UPDATE SET deadline=excluded.deadline, last_seen=excluded.last_seen""",
        batch,
    )
    log(f"  liquor: {len(batch)} applications on notice, {n} new")
    return n


# ---------- join ----------

def build_openings(con, log=print):
    cutoff = (dt.date.today() - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    groups = defaultdict(lambda: {"signals": [], "names": [], "cats": [], "phone": None, "owner": None,
                                  "address": None, "city": "Toronto", "postal": None, "ward": None, "hood": None,
                                  "lat": None, "lon": None, "cost": None, "desc": None})

    def touch(g, lat, lon, hood, ward, address, postal=None, city=None):
        if lat and not g["lat"]:
            g["lat"], g["lon"], g["hood"] = lat, lon, hood
        g["ward"] = g["ward"] or ward
        g["address"] = g["address"] or address
        g["postal"] = g["postal"] or postal
        if city:
            g["city"] = city

    # 1. liquor applications (new applications only; changes to existing licences are weaker)
    for r in con.execute("SELECT * FROM liquor_apps WHERE first_seen >= ? OR deadline >= ?", (cutoff, cutoff)):
        num, street = parse_free_address(r["address"])
        key = opening_key(num, street, unit_of(r["address"])) if num else f"agco:{r['file_number']}"
        if r["city"].upper() not in TORONTO_CITIES:
            key = f"{r['city'].upper()}|{key}"
        g = groups[key]
        strength = "new" if r["application_type"].startswith("New") else "change"
        g["signals"].append({"type": "liquor", "date": r["first_seen"], "strength": strength,
                             "detail": f"AGCO {r['application_type'].split(' - ')[0].lower()}: {r['licence_type']} ({r['areas'].lower()}). Objections close {r['deadline']}."})
        g["names"].append((1, r["premises_name"]))
        cat = categorize_text(r["premises_name"]) or ("brewery" if "Tied House" in r["licence_type"] else "restaurant")
        g["cats"].append((1, cat))
        addr = r["address"].split(",")[0].title()
        m = re.search(r"([A-Z]\d[A-Z]\s?\d[A-Z]\d)", r["address"])
        touch(g, r["lat"], r["lon"], r["neighbourhood"], None, addr, m.group(1) if m else None, r["city"])

    # 2. business licences
    for r in con.execute("SELECT * FROM licences WHERE issued >= ? AND cancel_date IS NULL", (cutoff,)):
        num, street = parse_free_address(r["address"])
        key = opening_key(num, street, unit_of(r["address"])) if num else f"lic:{r['licence_no']}"
        g = groups[key]
        g["signals"].append({"type": "licence", "date": r["issued"], "strength": "new",
                             "detail": f"City business licence issued: {r['category'].title()}."})
        g["names"].append((2, r["operating_name"]))
        g["cats"].append((2, LICENCE_CATEGORIES.get(r["category"]) or "other"))
        g["phone"] = g["phone"] or r["phone"]
        g["owner"] = g["owner"] or r["client_name"]
        touch(g, r["lat"], r["lon"], r["neighbourhood"], r["ward"], r["address"].title())

    # 3. commercial fit-out permits
    q = """SELECT * FROM permits WHERE application_date >= ? AND permit_type IN ({}) AND street_num != ''""".format(
        ",".join("?" * len(COMMERCIAL_PERMIT_TYPES)))
    for r in con.execute(q, (cutoff, *sorted(COMMERCIAL_PERMIT_TYPES))):
        text = f"{r['description']} {r['proposed_use']}"
        cat = categorize_text(text)
        if not cat or cat == "office" and not re.search(r"tenant|fit", text, re.I):
            continue
        if re.search(r"\b(dwelling|residential|condominium|apartment)\b", text, re.I) and cat in ("retail", "office"):
            continue
        base = address_key(r["street_num"], " ".join(x for x in [r["street_name"], r["street_type"], r["street_dir"]] if x))
        unit = unit_of(r["description"][:60]) if re.match(r"^\s*(unit|suite|#)", r["description"], re.I) else None
        key = f"{base} #{unit}" if unit else base
        if not unit:
            unit_keys = [k for k in groups if k.startswith(base + " #")]
            if len(unit_keys) == 1 and not groups[unit_keys[0]]["signals"][0]["type"] == "permit":
                key = unit_keys[0]
        g = groups[key]
        g["signals"].append({"type": "permit", "date": r["application_date"], "strength": "new",
                             "detail": f"Building permit ({r['work'] or r['permit_type']}): {r['description'][:180]}" + (f" Est. ${r['est_cost']:,.0f}." if r["est_cost"] else "")})
        name = extract_name(r["description"])
        if name:
            g["names"].append((3, name))
        g["cats"].append((3, cat))
        g["cost"] = max(g["cost"] or 0, r["est_cost"] or 0) or None
        g["desc"] = g["desc"] or r["description"]
        if r["builder_name"]:
            g["owner"] = g["owner"] or r["builder_name"]
        touch(g, r["lat"], r["lon"], r["neighbourhood"], r["ward"], r["address"], r["postal"])

    today = dt.date.today().isoformat()
    out = []
    for key, g in groups.items():
        for sg in g["signals"]:
            if sg["date"] and sg["date"] > today:
                sg["date"] = today
        sigs = sorted(g["signals"], key=lambda s: s["date"] or "")
        types = {s["type"] for s in sigs}
        cat = sorted(g["cats"])[0][1] if g["cats"] else "other"
        names = [n for _, n in sorted(g["names"]) if n]
        name = names[0] if names else None
        score = 0
        score += 40 if "liquor" in types else 0
        score += 30 if "licence" in types else 0
        score += 25 if "permit" in types else 0
        score += 20 * (len(types) - 1)
        if g["cost"]:
            score += min(int(g["cost"] / 50000), 20)
        last = sigs[-1]["date"] or ""
        try:
            age = (dt.date.today() - dt.date.fromisoformat(last)).days
            score += max(0, 20 - age // 7)
        except ValueError:
            pass
        out.append((
            key, name, cat, g["address"], g["city"], g["postal"], g["ward"], g["hood"], g["lat"], g["lon"],
            g["phone"], g["owner"], sigs[0]["date"], last, json.dumps(sigs), len(sigs), score, g["cost"], g["desc"],
        ))
    con.execute("DELETE FROM openings")
    con.executemany("INSERT INTO openings VALUES (%s)" % ",".join("?" * 19), out)
    log(f"  openings: {len(out)} joined records ({sum(1 for o in out if o[15] > 1)} with 2+ signals)")
    return len(out)
