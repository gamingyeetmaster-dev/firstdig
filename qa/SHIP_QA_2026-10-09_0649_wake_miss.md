# SHIP QA — First Dig morning refresh wake not occurring at 06:00 Toronto
**Observed:** 2026-10-09 06:49 EDT (10:49 UTC)  
**Severity:** P0 operational / data freshness; investigate before claiming morning digest delivery.  
**Repository baseline:** `7ec489cd94c64818c26b44f988cf0a4443ec1404` (Render live deploy `dep-db0r8g79nhgc738vgh1g`).  
**No production code/config changes in this QA pass.**

## Evidence (independently retrievable)
1. The live main workflow `.github/workflows/daily.yml` schedules zero-secret wake GET /health at **10:05 UTC** and **11:05 UTC** (06:05 EDT and 07:05 EDT respectively). The 11:05 UTC trigger is *outside* the configured 06:00 local refresh window during daylight time.
2. GitHub Actions runs from Oct 8 were created at **17:19:46 UTC** and **17:49:54 UTC**, *not* the expected 10:05/11:05 UTC times. Both report success: [run 37815704149](https://github.com/gamingyeetmaster-dev/firstdig/actions/runs/37815704149), [run 37819586112](https://github.com/gamingyeetmaster-dev/firstdig/actions/runs/37819586112). The job logs show successful curl calls returning `{"ok":true,"last_run":null,"projects":0,"auth_store":"sqlite"}` at 17:20:23 UTC and 17:50:29 UTC. Successful wake **does not mean data refresh succeeded**.
3. Render app logs for `srv-dasv4svpn0mc73a7jkig` on Oct 8 show scheduler startup at 17:20:18 and 17:50:20 UTC, successful `GET /health` 200, then app shutdown after ~15 min. There is **no `scheduled refresh starting` event** in those startup windows. Scheduler source `app/web/scheduler.py` permits execution only when `now.hour == REFRESH_HOUR` (6).
4. GitHub Actions `actions/runs` queried on Oct 9 10:49 UTC showed **no Oct 9 scheduled run yet**; newest run was Oct 8 17:49 UTC. Render logs queried for Oct 9 09:55–10:55 UTC returned **zero events**. This is evidence of an absent observed wake/refresh *as of the check*, not proof no job can execute later.
5. The Oct 8 /health response reported `last_run:null`, `projects:0`, and `auth_store:sqlite`. This indicates no last successful pipeline run is recorded on that ephemeral host instance and zero loaded projects **at the time of the health checks**. It does not establish user traffic or explain any earlier history.

## Root-cause hypothesis
The GitHub Actions `schedule` events appear to be running many hours late in this environment. Because the app is on Render free and sleeps after ~15 minutes, a wake outside the single local 06:00 hour cannot start the pipeline. This failure mode exists even though both GitHub runs show green and both /health requests return HTTP 200.

## Immediate safe next steps
1. **Do not treat successful GitHub wake workflow as successful refresh.** QA gate must verify a fresh `last_run`, positive project count, and `scheduled refresh starting` / pipeline completion log, not just HTTP 200.
2. Inspect scheduled-run delays and confirm whether the workflow is still executing ~7h late on Oct 9; do not silently infer a cron-time bug from one day. Check whether GitHub Actions scheduling is reliable enough for this SLA.
3. Fix architecture rather than shifting cron by a magic number: use a reliable wake mechanism at 06:00 Toronto plus durable once-per-local-day execution claim, or run a supervised external scheduled refresh. Preserve zero-cost constraint and prevent duplicate refreshes on restart.
4. Ensure pipeline failures are visible in health and logs; include `last_attempt`, `last_success`, `project_count`, and scheduler claim date with sensitive data excluded.
5. After any change, verify at 06:05–06:55 Toronto on an actual production day and test both DST offsets. **Do not send commercial email** until compliance gates are met.
6. Postgres commercial-state durability remains **unverified/inactive** until `AUTH_DATABASE_URL` is privately set and tested. Existing free DB expires 2026-10-28.
7. No Toronto After Dark resubmission and no UTSU distribution.

## Scope limitations
The QA runner cannot directly GET the public sites from its own network; live /health evidence above comes from independently logged GitHub Actions curl and Render request logs. No new Render service was created, no customer email was sent, and no traffic, revenue, or awards are claimed.
