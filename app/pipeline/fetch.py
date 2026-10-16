"""Download the public source files. Each file is cached in data/raw and
re-downloaded when older than max_age_hours."""
import csv
import time
from pathlib import Path

import httpx

from ..config import RAW_DIR, SOURCES

FILES = {
    "permits_active": "permits-active.csv",
    "business_licences": "business-licences.csv",
    "agco_liquor": "agco.csv",
    "address_points": "address-points.csv",
    "neighbourhoods": "neighbourhoods.geojson",
}

# Address points and neighbourhood polygons barely change; refresh weekly.
MAX_AGE_HOURS = {
    "permits_active": 20,
    "business_licences": 20,
    "agco_liquor": 20,
    "address_points": 24 * 7,
    "neighbourhoods": 24 * 30,
}

# The City described the active-permit resource as containing more than
# 200,000 rows in September 2026. Its unbounded CKAN dump briefly returned
# exactly 80,000 rows on 2026-10-16. Fail closed well below the known healthy
# size so a platform row cap cannot be mistaken for a complete refresh.
MIN_ACTIVE_PERMIT_ROWS = 100_000


def path_for(key):
    return RAW_DIR / FILES[key]


def _validate_snapshot(key, path):
    if key != "permits_active":
        return
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = sum(1 for _ in csv.reader(f)) - 1
    if rows < MIN_ACTIVE_PERMIT_ROWS:
        raise RuntimeError(
            f"{key}: partial snapshot ({rows} rows; expected at least "
            f"{MIN_ACTIVE_PERMIT_ROWS}), keeping old file"
        )


def fetch(key, force=False, log=print):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = path_for(key)
    if dest.exists() and not force:
        age_h = (time.time() - dest.stat().st_mtime) / 3600
        if age_h < MAX_AGE_HOURS[key]:
            log(f"  {key}: cached ({age_h:.1f}h old)")
            return dest
    url = SOURCES[key]
    log(f"  {key}: downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    size = tmp.stat().st_size
    if size < 1000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{key}: response too small ({size} bytes), keeping old file")
    try:
        _validate_snapshot(key, tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(dest)
    log(f"  {key}: {size/1e6:.1f} MB")
    return dest


def fetch_all(force=False, log=print):
    out = {}
    for key in FILES:
        try:
            out[key] = fetch(key, force=force, log=log)
        except Exception as e:  # keep going with the cached copy if any
            log(f"  {key}: FAILED {e}")
            if path_for(key).exists():
                out[key] = path_for(key)
            else:
                raise
    return out
