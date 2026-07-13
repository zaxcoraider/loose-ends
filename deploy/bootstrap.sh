#!/usr/bin/env bash
# Bootstrap Loose Ends on a fresh Amazon Linux 2023 box.
#
#   sudo bash bootstrap.sh
#
# Idempotent: safe to re-run. Does NOT write secrets — you drop /opt/looseends/.env
# in yourself (see deploy/README.md), because this script is in a public repo.
set -euo pipefail

REPO="https://github.com/zaxcoraider/loose-ends.git"
APP_DIR="/opt/looseends"

echo "==> packages"
dnf -y install git python3.12 python3.12-pip >/dev/null

echo "==> service user"
id -u looseends >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /sbin/nologin looseends

echo "==> code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all --quiet
  git -C "$APP_DIR" reset --hard origin/main --quiet
else
  mkdir -p "$APP_DIR"
  git clone --quiet "$REPO" "$APP_DIR"
fi

echo "==> venv"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  python3.12 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# The SQLite file lives beside the code on the EBS root volume, which persists across
# reboots and stop/starts. It does NOT survive terminating the instance — snapshot the
# volume if the tracked items ever matter beyond a demo.
touch "$APP_DIR/loose_ends.sqlite"
chown -R looseends:looseends "$APP_DIR"

if [ ! -f "$APP_DIR/.env" ]; then
  echo
  echo "!! /opt/looseends/.env is missing — the services will fail to start."
  echo "   Copy it up, then: chown looseends:looseends /opt/looseends/.env && chmod 600 it"
  echo "   See deploy/README.md."
  echo
fi

echo "==> systemd"
cp "$APP_DIR/deploy/looseends-mcp.service" /etc/systemd/system/
cp "$APP_DIR/deploy/looseends-app.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now looseends-mcp.service
systemctl enable --now looseends-app.service

echo
systemctl --no-pager --lines=0 status looseends-mcp.service || true
systemctl --no-pager --lines=0 status looseends-app.service || true
echo
echo "done. logs:  journalctl -u looseends-app -f"
