"""Download the public source files. Each file is cached in data/raw and
re-downloaded when older than max_age_hours."""
import csv
import random
import time
from email.utils import parsedate_to_datetime
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

# Retry inside one source download so a brief CKAN outage does not force the
# outer scheduler to wait 30 minutes. Keep this bounded to avoid hammering an
# already-degraded public service.
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_BACKOFF_SECONDS = (2, 5, 15)
DOWNLOAD_RETRY_CAP_SECONDS = 30
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}

# The City described the active-permit resource as containing more than
# 200,000 rows in September 2026. Its unbounded CKAN dump briefly returned
# exactly 80,000 rows on 2026-10-16. Fail closed well below the known healthy
# size so a platform row cap cannot be mistaken for a complete refresh.
MIN_ACTIVE_PERMIT_ROWS = 100_000


def path_for(key):
    return RAW_DIR / FILES[key]


def _cache_age_hours(path):
    return (time.time() - path.stat().st_mtime) / 3600


def _cache_is_fresh(key, path):
    return path.exists() and _cache_age_hours(path) < MAX_AGE_HOURS[key]


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


def _is_transient(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES
    return isinstance(exc, httpx.TransportError)


def _retry_after_seconds(exc):
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    raw = exc.response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(raw).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return None
    return min(max(seconds, 0), DOWNLOAD_RETRY_CAP_SECONDS)


def _retry_delay(exc, retry_index):
    retry_after = _retry_after_seconds(exc)
    base = DOWNLOAD_BACKOFF_SECONDS[
        min(retry_index, len(DOWNLOAD_BACKOFF_SECONDS) - 1)
    ]
    delay = max(base, retry_after or 0)
    jitter = random.uniform(0, min(1.0, delay * 0.1))
    return min(delay + jitter, DOWNLOAD_RETRY_CAP_SECONDS)


def _download(url, tmp, key, log):
    for attempt in range(DOWNLOAD_ATTEMPTS):
        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=300
            ) as response:
                response.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in response.iter_bytes(1 << 20):
                        f.write(chunk)
            return
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            if attempt + 1 >= DOWNLOAD_ATTEMPTS or not _is_transient(exc):
                raise
            delay = _retry_delay(exc, attempt)
            log(
                f"  {key}: transient download failure "
                f"({type(exc).__name__}); retry {attempt + 2}/"
                f"{DOWNLOAD_ATTEMPTS} in {delay:.1f}s"
            )
            time.sleep(delay)


def fetch(key, force=False, log=print):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = path_for(key)
    if _cache_is_fresh(key, dest) and not force:
        log(f"  {key}: cached ({_cache_age_hours(dest):.1f}h old)")
        return dest
    url = SOURCES[key]
    log(f"  {key}: downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    _download(url, tmp, key, log)
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
        except Exception as e:
            log(f"  {key}: FAILED {e}")
            cached = path_for(key)
            if _cache_is_fresh(key, cached):
                log(
                    f"  {key}: using validated cached copy "
                    f"({_cache_age_hours(cached):.1f}h old)"
                )
                out[key] = cached
            else:
                raise
    return out
