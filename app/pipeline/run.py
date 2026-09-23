"""Daily refresh. `python -m app.pipeline.run [--force]`."""
import datetime as dt
import sys
import time

from ..db import db, init_db, set_meta
from . import fetch, geo, openings, permits


def run(force=False, log=print):
    init_db()
    t0 = time.time()
    started = dt.datetime.utcnow().isoformat(timespec="seconds")
    notes = []
    ok = 1
    with db() as con:
        run_id = con.execute("INSERT INTO runs(started, ok) VALUES (?, 0)", (started,)).lastrowid
    try:
        log("fetching sources")
        files = fetch.fetch_all(force=force, log=log)
        log("loading geo index")
        gi = geo.load(files["address_points"], files["neighbourhoods"], log=log)
        with db() as con:
            log("permits")
            n = permits.load_permits(con, files["permits_active"], gi, log=log)
            notes.append(f"permits+{n}")
            permits.build_projects(con, log=log)
            log("openings")
            n = openings.load_licences(con, files["business_licences"], gi, log=log)
            notes.append(f"licences+{n}")
            n = openings.load_liquor(con, files["agco_liquor"], gi, log=log)
            notes.append(f"liquor+{n}")
            openings.build_openings(con, log=log)
            set_meta(con, "last_run", started)
            set_meta(con, "permits_file_date", dt.datetime.fromtimestamp(files["permits_active"].stat().st_mtime).isoformat(timespec="minutes"))
    except Exception as e:
        ok = 0
        notes.append(f"ERROR {e!r}")
        log(f"FAILED: {e!r}")
        raise
    finally:
        with db() as con:
            con.execute("UPDATE runs SET finished=?, ok=?, notes=? WHERE id=?",
                        (dt.datetime.utcnow().isoformat(timespec="seconds"), ok, "; ".join(notes), run_id))
        log(f"done in {time.time()-t0:.0f}s: {'; '.join(notes)}")


if __name__ == "__main__":
    run(force="--force" in sys.argv)
