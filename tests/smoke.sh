#!/bin/sh
# Smoke test against a running instance. Usage: tests/smoke.sh http://127.0.0.1:8000
B="${1:-http://127.0.0.1:8000}"; fail=0
for u in / /teardown /openings /pricing /methodology /terms /app/teardown /app/openings /login /health /robots.txt "/api/teardown.geojson?days=14" "/api/openings.geojson?minsig=2"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$B$u"); [ "$c" = "200" ] || { echo "FAIL $c $u"; fail=1; }
done
c=$(curl -s -o /dev/null -w '%{http_code}' "$B/tasks/refresh?key=wrong"); [ "$c" = "403" ] || { echo "FAIL cron key not enforced ($c)"; fail=1; }
c=$(curl -s -o /dev/null -w '%{http_code}' "$B/export/teardown.csv"); [ "$c" = "200" ] || { echo "note: export unauthenticated -> $c (303 expected)"; }
curl -s -I "$B/" | grep -qi "x-content-type-options" || { echo "FAIL security headers missing"; fail=1; }
[ $fail = 0 ] && echo "smoke OK: $B"
exit $fail
