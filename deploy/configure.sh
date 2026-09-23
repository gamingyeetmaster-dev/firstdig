#!/usr/bin/env bash
# Interactive: fills the secrets in /opt/signals/.env and restarts the app.
# Run on the server as root: sudo /opt/signals/deploy/configure.sh
set -euo pipefail
ENV=/opt/signals/.env
[ -f "$ENV" ] || { echo "no $ENV; run install.sh first"; exit 1; }

setk() { # key value
  if grep -q "^$1=" "$ENV"; then sed -i "s|^$1=.*|$1=$2|" "$ENV"; else echo "$1=$2" >> "$ENV"; fi
}
ask() { # key prompt
  cur=$(grep "^$1=" "$ENV" | cut -d= -f2- || true)
  read -r -p "$2 [${cur:-empty}]: " v
  [ -n "$v" ] && setk "$1" "$v"
}

echo "Leave blank to keep the current value."
ask ADMIN_EMAILS "Admin email(s), comma separated"
ask BASE_URL "Public URL (https://yourdomain)"
ask RESEND_API_KEY "Resend API key (re_...)"
ask EMAIL_FROM "From address, e.g. Signals <hello@yourdomain>"
ask STRIPE_SECRET_KEY "Stripe secret key (sk_live_... or sk_test_...)"
if grep -q '^STRIPE_SECRET_KEY=sk_' "$ENV"; then
  echo "Creating Stripe products, prices and webhook (idempotent)..."
  set -a; . "$ENV"; set +a
  out=$(/opt/signals/.venv/bin/python /opt/signals/scripts/stripe_setup.py)
  echo "$out"
  echo "$out" | grep -E '^STRIPE_' | while IFS='=' read -r k v; do setk "$k" "$v"; done
fi
chown signals:signals "$ENV"; chmod 600 "$ENV"
systemctl restart signals
echo "Done. App restarted."
