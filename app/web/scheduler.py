"""In-process scheduler so the app needs no external cron. Enabled with
ENABLE_SCHEDULER=1. Refreshes data at REFRESH_HOUR (Toronto time) and
sends digests right after. Safe to leave on with a single web process."""
import datetime as dt
import logging
import os
import threading
import time

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Toronto")
except Exception:  # pragma: no cover
    TZ = None

log = logging.getLogger("scheduler")
REFRESH_HOUR = int(os.getenv("REFRESH_HOUR", "6"))


def _now():
    return dt.datetime.now(TZ) if TZ else dt.datetime.now()


def _job():
    from ..db import connect
    from ..pipeline.run import run
    from . import digest, emailer, marketing_brief
    try:
        run(log=log.info)
    except Exception:
        log.exception("refresh failed")
        return
    con = connect()
    try:
        digest.send_all(con, emailer.send, log=log.info)
        marketing_brief.send(con, emailer.send, log_fn=log.info)
        con.commit()
    except Exception:
        log.exception("digests failed")
    finally:
        con.close()


def _should_run(now, last_day):
    """Run once during the configured local hour, never merely because it is later.

    This matters on hosts that restart on deploy: a 9 p.m. deploy must not replay
    the morning refresh just because 9 >= 6.
    """
    return now.hour == REFRESH_HOUR and last_day != now.date()


def _read_data_state():
    """The local SQLite public-data cache is ephemeral; inspect it every tick."""
    from ..db import connect, get_meta
    con = connect()
    try:
        last_run = get_meta(con, "last_run")
        count = con.execute("SELECT count(*) FROM projects").fetchone()[0]
    finally:
        con.close()
    return last_run, count


def _last_run_local(last_run):
    if not last_run:
        return None
    try:
        stamp = dt.datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)  # pipeline writes UTC
        return stamp.astimezone(TZ or dt.timezone.utc)
    except (ValueError, TypeError, AttributeError):
        log.warning("unparseable last_run; refresh remains unverified")
        return None


def _data_ready(now, last_run, projects):
    """Data available and recent enough to serve, even before today's 06:00.

    This is deliberately NOT a guarantee that today's scheduled refresh ran.
    The separate _data_fresh() predicate makes that promise.
    """
    stamp = _last_run_local(last_run)
    if not projects or projects <= 0 or stamp is None:
        return False
    # UTC elapsed time avoids DST wall-clock subtraction errors.
    age = now.astimezone(dt.timezone.utc) - stamp.astimezone(dt.timezone.utc)
    return dt.timedelta(minutes=-2) <= age <= dt.timedelta(hours=30)


def _data_fresh(now, last_run, projects):
    """A successful nonempty refresh since the latest Toronto 06:00 boundary.

    Before 06:00, yesterday's 06:00 is the latest expected boundary.
    """
    stamp = _last_run_local(last_run)
    if not _data_ready(now, last_run, projects) or stamp is None:
        return False
    boundary = now.replace(hour=REFRESH_HOUR, minute=0, second=0, microsecond=0)
    if now < boundary:
        boundary -= dt.timedelta(days=1)
    return boundary <= stamp <= now + dt.timedelta(minutes=2)


def _should_refresh(now, last_run, projects, retry_at=None):
    """Recover an empty/stale cache immediately; after 06:00 refresh today.

    Late catch-up is data-only, with bounded retries, never email.
    """
    if retry_at is not None and now < retry_at:
        return False
    if not _data_ready(now, last_run, projects):
        return True
    return now.hour >= REFRESH_HOUR and not _data_fresh(now, last_run, projects)


def _refresh_data_only():
    """Intentionally NO digest or marketing send; outbound needs durable outbox."""
    from ..pipeline.run import run
    run(log=log.info)


def _loop():
    failures = 0
    retry_at = None
    while True:
        now = _now()
        try:
            last_run, projects = _read_data_state()
            if _should_refresh(now, last_run, projects, retry_at):
                log.info("data-only refresh: cache empty/stale; no outbound email")
                _refresh_data_only()
                last_run, projects = _read_data_state()
                if not _data_fresh(_now(), last_run, projects):
                    raise RuntimeError("pipeline finished but data readiness unverified")
                failures = 0
                retry_at = None
                log.info("data-only refresh verified: %d projects", projects)
        except Exception:
            failures += 1
            delay = min(1800 * 2 ** min(failures - 1, 2), 7200)
            retry_at = now + dt.timedelta(seconds=delay)
            log.exception("data-only refresh failed; retry in %d seconds", delay)
        time.sleep(300)


def start():
    if os.getenv("ENABLE_SCHEDULER", "0") != "1":
        return
    t = threading.Thread(target=_loop, name="scheduler", daemon=True)
    t.start()
    log.info("scheduler started; daily refresh after %02d:00 Toronto time", REFRESH_HOUR)
