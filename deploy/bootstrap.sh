#!/usr/bin/env bash
# Bootstrap Loose Ends on a fresh Amazon Linux 2023 box.
#
#   sudo bash bootstrap.sh
#
# Idempotent: safe to re-run, and re-running is how you deploy the latest main.
#
# Does NOT write secrets. You drop one env file per Slack workspace into
# /opt/looseends/env/ yourself (see deploy/README.md), because this script is public:
#
#   env/judging.env   → looseends-app@judging     (the judging mirror)
#   env/looseend.env  → looseends-app@looseend    (the original workspace)
#
# One shared MCP server on 127.0.0.1:8765 serves both.
set -euo pipefail

REPO="https://github.com/zaxcoraider/loose-ends.git"
APP_DIR="/opt/looseends"
ENV_DIR="$APP_DIR/env"

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

echo "==> env"
mkdir -p "$ENV_DIR"
# Boxes bootstrapped before multi-workspace support kept a single /opt/looseends/.env, and
# that one was the judging mirror. Move it into place instead of silently ignoring it.
if [ -f "$APP_DIR/.env" ] && [ ! -f "$ENV_DIR/judging.env" ]; then
  echo "    migrating legacy .env -> env/judging.env"
  mv "$APP_DIR/.env" "$ENV_DIR/judging.env"
fi
chmod 700 "$ENV_DIR"
chmod 600 "$ENV_DIR"/*.env 2>/dev/null || true

# Each workspace's SQLite file lives beside the code on the EBS root volume, which survives
# reboots and stop/starts. It does NOT survive terminating the instance — snapshot the volume
# if the tracked items ever matter beyond a demo. Give every env file its own LOOSEENDS_DB,
# or both workspaces write into one database and each dashboard shows the other's items.
chown -R looseends:looseends "$APP_DIR"

shopt -s nullglob
ENV_FILES=("$ENV_DIR"/*.env)
shopt -u nullglob

if [ ${#ENV_FILES[@]} -eq 0 ]; then
  echo
  echo "!! No env files in $ENV_DIR — there is nothing to run."
  echo "   Add one per workspace (judging.env, looseend.env), then re-run this script."
  echo "   See deploy/README.md."
  echo
fi

echo "==> systemd"
# The app is a template unit now. Retire the old single-workspace unit if this box predates
# that, or it keeps running against an .env that no longer exists.
if [ -f /etc/systemd/system/looseends-app.service ]; then
  echo "    retiring old single-workspace looseends-app.service"
  systemctl disable --now looseends-app.service >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/looseends-app.service
fi

cp "$APP_DIR/deploy/looseends-mcp.service" /etc/systemd/system/
cp "$APP_DIR/deploy/looseends-app@.service" /etc/systemd/system/
systemctl daemon-reload

systemctl enable --now looseends-mcp.service

# One app instance per env file. Deleting an env file stops that workspace from being served
# on the next run — but it is not stopped for you here, because a deploy script quietly
# killing a live agent is worse than one extra command.
UNITS=()
for f in "${ENV_FILES[@]}"; do
  name="$(basename "$f" .env)"
  UNITS+=("looseends-app@${name}.service")
  echo "    ${name}"
  systemctl enable "looseends-app@${name}.service" >/dev/null
  systemctl restart "looseends-app@${name}.service"
done

echo
systemctl --no-pager --lines=0 status looseends-mcp.service || true
for u in "${UNITS[@]}"; do
  systemctl --no-pager --lines=0 status "$u" || true
done
echo
echo "done. logs:"
for u in "${UNITS[@]}"; do
  echo "  journalctl -u $u -f"
done
