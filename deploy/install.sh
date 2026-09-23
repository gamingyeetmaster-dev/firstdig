#!/usr/bin/env bash
# One-shot server install for Ubuntu 22.04/24.04 (Azure B1s, Hetzner, DO, anything).
# Idempotent: safe to re-run to update. Usage (as root):
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/install.sh | REPO_URL=https://github.com/<you>/<repo>.git DOMAIN=example.com bash
set -euo pipefail

REPO_URL="${REPO_URL:?set REPO_URL to your git repo}"
DOMAIN="${DOMAIN:?set DOMAIN to your domain, e.g. firstdig.app}"
APP_DIR=/opt/signals
APP_USER=signals

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip git curl sqlite3 libgeos-c1v5 debian-keyring debian-archive-keyring apt-transport-https

# 2 GB swap so the first geo-index build survives on a 1 GB box
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

id -u $APP_USER >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin $APP_USER

# code
if [ -d $APP_DIR/.git ]; then
  git -C $APP_DIR pull -q
else
  git clone -q "$REPO_URL" $APP_DIR
fi
mkdir -p $APP_DIR/data
[ -f $APP_DIR/.env ] || cat > $APP_DIR/.env <<EOF
DEV_MODE=0
BASE_URL=https://$DOMAIN
SECRET_KEY=$(openssl rand -hex 32)
CRON_SECRET=$(openssl rand -hex 24)
ADMIN_EMAILS=
ENABLE_SCHEDULER=1
REFRESH_HOUR=6
DATA_DIR=$APP_DIR/data
DB_PATH=$APP_DIR/data/signals.db
# fill these in with deploy/configure.sh
RESEND_API_KEY=
EMAIL_FROM=Signals <hello@$DOMAIN>
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_TEARDOWN=
STRIPE_PRICE_OPENINGS=
STRIPE_PRICE_BUNDLE=
EOF
chown -R $APP_USER:$APP_USER $APP_DIR

# python env
sudo -u $APP_USER bash -c "cd $APP_DIR && [ -d .venv ] || python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt"

# systemd
cat > /etc/systemd/system/signals.service <<EOF
[Unit]
Description=First Dig web app
After=network-online.target
[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn app.web.main:app --host 127.0.0.1 --port 8080 --workers 1
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now signals
systemctl restart signals

# Caddy: automatic HTTPS
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi
cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN, www.$DOMAIN {
  encode gzip
  reverse_proxy 127.0.0.1:8080
}
EOF
systemctl reload caddy || systemctl restart caddy

# first data build (2-3 min); later runs are handled by the in-process scheduler
sudo -u $APP_USER bash -c "cd $APP_DIR && set -a && . ./.env && set +a && .venv/bin/python -m app.pipeline.run" || true
systemctl restart signals

echo
echo "Installed. Point $DOMAIN (A record) at this server's public IP; Caddy issues the certificate automatically."
echo "Then run: sudo $APP_DIR/deploy/configure.sh   to add email, admin and Stripe keys."
