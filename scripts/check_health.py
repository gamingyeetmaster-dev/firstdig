"""Verify First Dig's daily public-data refresh, not just HTTP liveness.

This zero-secret check is intended for the existing GitHub Actions wake job.
The application health response is public and contains no credentials.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")
URL = "https://first-dig-night-shift.onrender.com/health"


def parse_last_run(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return stamp.replace(tzinfo=dt.timezone.utc) if stamp.tzinfo is None else stamp
    except ValueError:
        return None


def assess(payload, now):
    """Return (is_fresh, diagnostic). Never infer freshness from HTTP 200."""
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return False, "health response is missing ok=true"
    try:
        projects = int(payload.get("projects", 0))
    except (TypeError, ValueError):
        projects = 0
    if projects <= 0:
        return False, f"no project data (projects={projects})"
    stamp = parse_last_run(payload.get("last_run"))
    if stamp is None:
        return False, "last_run missing or invalid"
    local_now = now.astimezone(TORONTO)
    boundary = local_now.replace(hour=6, minute=0, second=0, microsecond=0)
    if local_now < boundary:
        boundary -= dt.timedelta(days=1)
    if stamp.astimezone(dt.timezone.utc) > now.astimezone(dt.timezone.utc) + dt.timedelta(minutes=2):
        return False, "last_run timestamp is in the future"
    if stamp < boundary:
        return False, f"last_run {stamp.isoformat()} predates Toronto 06:00 boundary {boundary.isoformat()}"
    return True, f"fresh nonempty dataset: projects={projects}, last_run={stamp.isoformat()}"


def fetch(url=URL):
    req = urllib.request.Request(url, headers={"User-Agent": "firstdig-health-qa/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.load(response)


def main():
    # At 05:05 EST, the first UTC wake is deliberately only a warm-up.
    # Late runs (even when triggered by the 05:05 cron) must check freshness.
    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(TORONTO)
    if local.hour < 6:
        print(f"PRE-06 TORONTO WARM-UP: liveness wake only ({local.isoformat()})")
        return 0
    # A cold free-instance rebuild can take six minutes: Oct 27's full recovery
    # completed after the old eight-check window expired. Keep a bounded
    # verification window, without ever treating HTTP 200 as data readiness.
    attempts = int(os.environ.get("FIRSTDIG_HEALTH_ATTEMPTS", "12"))
    interval = int(os.environ.get("FIRSTDIG_HEALTH_INTERVAL_SECONDS", "40"))
    for i in range(1, attempts + 1):
        try:
            payload = fetch()
            ok, reason = assess(payload, dt.datetime.now(dt.timezone.utc))
        except (urllib.error.URLError, ValueError, OSError, RuntimeError) as exc:
            ok, reason = False, f"health unavailable: {type(exc).__name__}"
        print(f"attempt {i}/{attempts}: {'PASS' if ok else 'WAIT'} — {reason}", flush=True)
        if ok:
            return 0
        if i < attempts:
            time.sleep(interval)
    print("FAIL: wake succeeded but fresh nonempty data could not be verified", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
