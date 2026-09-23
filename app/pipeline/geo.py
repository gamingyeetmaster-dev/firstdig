"""Geocoding against Toronto's own address-point file, and neighbourhood
lookup by point-in-polygon. Built once per run and cached on disk as a
compact pickle so daily runs take seconds, not minutes."""
import csv
import json
import pickle
import re
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from ..config import DATA_DIR

CACHE = DATA_DIR / "geo-index.pkl"

STREET_TYPE_MAP = {
    "AVENUE": "AVE", "AV": "AVE", "STREET": "ST", "ROAD": "RD", "DRIVE": "DR", "BOULEVARD": "BLVD",
    "CRESCENT": "CRES", "COURT": "CRT", "CT": "CRT", "PLACE": "PL", "LANE": "LANE", "TERRACE": "TER",
    "GARDENS": "GDNS", "CIRCLE": "CIR", "CIRCL": "CIR", "TRAIL": "TRL", "SQUARE": "SQ", "PARKWAY": "PKWY",
    "HEIGHTS": "HTS", "GROVE": "GRV", "PATH": "PATH", "WAY": "WAY", "ROW": "ROW", "HILL": "HILL",
    "MEWS": "MEWS", "PARK": "PARK", "GATE": "GATE", "WALK": "WALK", "CLOSE": "CLOSE", "ROADWAY": "RDWY",
}
DIR_MAP = {"EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S"}


def normalize_street(s):
    """'Bayview Avenue East' -> 'BAYVIEW AVE E'. Used on both sides of joins."""
    s = re.sub(r"[.,]", " ", (s or "").upper())
    toks = [t for t in s.split() if t]
    out = []
    for t in toks:
        out.append(STREET_TYPE_MAP.get(t, DIR_MAP.get(t, t)))
    return " ".join(out)


def normalize_number(n):
    n = (n or "").strip().upper()
    n = re.sub(r"\s+", "", n)
    return n


def address_key(number, street):
    return f"{normalize_number(number)} {normalize_street(street)}".strip()


def parse_free_address(addr):
    """'223 JAMESON AVE SUITE 101, TORONTO, ON, M6K2Y3' -> ('223','JAMESON AVE')."""
    first = (addr or "").split(",")[0].upper()
    first = re.sub(r"\b(SUITE|UNIT|APT|#|STE|FLOOR|FL|LEVEL|RM)\b.*$", "", first).strip()
    m = re.match(r"^(\d+[A-Z]?)\s*[-–]?\s*(?:\d+[A-Z]?\s+)?(.+)$", first)
    if not m:
        return None, first
    return m.group(1), m.group(2).strip()


class GeoIndex:
    def __init__(self, by_id, by_addr, hoods, tree_geoms, tree):
        self.by_id = by_id          # ADDRESS_POINT_ID -> (lat, lon)
        self.by_addr = by_addr      # 'NUM STREET' -> (lat, lon)
        self.hoods = hoods          # list of names aligned with tree_geoms
        self.tree_geoms = tree_geoms
        self.tree = tree

    def locate(self, geo_id=None, number=None, street=None):
        if geo_id and geo_id in self.by_id:
            return self.by_id[geo_id]
        if number and street:
            return self.by_addr.get(address_key(number, street))
        return None

    def neighbourhood(self, lat, lon):
        if lat is None or lon is None:
            return None
        p = Point(lon, lat)
        try:
            idx = self.tree.query(p)
        except Exception:
            return None
        for i in idx:
            i = int(i)
            if self.tree_geoms[i].contains(p):
                return self.hoods[i]
        return None


def build(address_csv: Path, hoods_geojson: Path, log=print):
    log("  geo: building address index (this takes ~1 minute the first time)")
    by_id, by_addr = {}, {}
    with open(address_csv, newline="") as f:
        for r in csv.DictReader(f):
            try:
                c = json.loads(r["geometry"])["coordinates"][0]
            except Exception:
                continue
            latlon = (round(c[1], 6), round(c[0], 6))
            by_id[r["ADDRESS_POINT_ID"]] = latlon
            k = address_key(r["ADDRESS_NUMBER"], r["LINEAR_NAME_FULL"])
            by_addr.setdefault(k, latlon)
    g = json.load(open(hoods_geojson))
    hoods, geoms = [], []
    for ft in g["features"]:
        name = ft["properties"].get("AREA_NAME") or ft["properties"].get("AREA_SHORT_CODE")
        name = re.sub(r"\s*\(\d+\)\s*$", "", name or "").strip()
        hoods.append(name)
        geoms.append(shape(ft["geometry"]))
    idx = GeoIndex(by_id, by_addr, hoods, geoms, STRtree(geoms))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump({"by_id": by_id, "by_addr": by_addr, "hoods": hoods,
                     "geoms": [gm.wkb for gm in geoms]}, f, protocol=pickle.HIGHEST_PROTOCOL)
    log(f"  geo: {len(by_id)} address points, {len(hoods)} neighbourhoods")
    return idx


def load(address_csv: Path, hoods_geojson: Path, log=print):
    from shapely import wkb
    if CACHE.exists() and CACHE.stat().st_mtime >= address_csv.stat().st_mtime:
        d = pickle.load(open(CACHE, "rb"))
        geoms = [wkb.loads(b) for b in d["geoms"]]
        return GeoIndex(d["by_id"], d["by_addr"], d["hoods"], geoms, STRtree(geoms))
    return build(address_csv, hoods_geojson, log=log)
