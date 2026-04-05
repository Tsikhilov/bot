#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/SmartKamaVPN"
SERVICE="smartkamavpn"
cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

if [[ -d .git ]]; then
  git fetch --all --prune
  BRANCH=$(git rev-parse --abbrev-ref HEAD || true)
  if [[ -n "$BRANCH" && "$BRANCH" != "HEAD" ]]; then
    git pull --ff-only origin "$BRANCH" || true
  fi
fi

.venv/bin/python -m pip install -U pip setuptools wheel >/dev/null 2>&1 || true
.venv/bin/pip install -r requirements.txt >/dev/null

.venv/bin/python -m py_compile smartkamavpnTelegramBot.py AdminBot/bot.py UserBot/bot.py UserBot/markups.py Utils/api.py Utils/marzban_api.py scripts/selfcheck_api.py scripts/selfcheck_marzban_api.py scripts/server_set_panel_provider.py

PANEL_PROVIDER="$(.venv/bin/python - <<'PY'
import config
print(str(getattr(config, "PANEL_PROVIDER", "3xui") or "3xui").strip().lower())
PY
))"

# Validate panel API against active provider before restart.
if [[ "$PANEL_PROVIDER" == "marzban" ]]; then
  .venv/bin/python scripts/selfcheck_marzban_api.py
else
  .venv/bin/python scripts/selfcheck_api.py
fi

systemctl daemon-reload
systemctl restart "$SERVICE"
systemctl is-active "$SERVICE"

echo "DEPLOY_OK"
