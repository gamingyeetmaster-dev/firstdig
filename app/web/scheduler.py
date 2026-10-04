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


def _loop():
    last_day = None
    while True:
        now = _now()
        if _should_run(now, last_day):
            # Claim the day before work starts so a failure does not spin every
            # five minutes. The next scheduled day (or a manual refresh) retries.
            last_day = now.date()
            log.info("scheduled refresh starting")
            _job()
        time.sleep(300)


def start():
    if os.getenv("ENABLE_SCHEDULER", "0") != "1":
        return
    t = threading.Thread(target=_loop, name="scheduler", daemon=True)
    t.start()
    log.info("scheduler started; daily refresh after %02d:00 Toronto time", REFRESH_HOUR)
