#!/bin/sh
# Local dev: refresh data if the DB is missing, then serve with autoreload.
cd "$(dirname "$0")"
[ -f data/signals.db ] || python3 -m app.pipeline.run
exec python3 -m uvicorn app.web.main:app --port 8000 --reload
