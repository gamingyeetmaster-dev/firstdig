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
    from . import digest, emailer
    try:
        run(log=log.info)
    except Exception:
        log.exception("refresh failed")
        return
    con = connect()
    try:
        digest.send_all(con, emailer.send, log=log.info)
        con.commit()
    except Exception:
        log.exception("digests failed")
    finally:
        con.close()


def _loop():
    last_day = None
    while True:
        now = _now()
        if now.hour >= REFRESH_HOUR and last_day != now.date():
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
