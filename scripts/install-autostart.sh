#!/usr/bin/env bash
# One-time setup: makes the FastAPI server and Next.js web app start
# automatically on login and stay running (auto-restart if they crash),
# via macOS launchd. Run this once:
#
#   bash scripts/install-autostart.sh
#
# To remove later: bash scripts/uninstall-autostart.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
AGENTS_DIR="$HOME/Library/LaunchAgents"
SERVER_LABEL="com.jobapplycopilot.server"
WEB_LABEL="com.jobapplycopilot.web"
UID_NUM="$(id -u)"

mkdir -p "$AGENTS_DIR" "$ROOT_DIR/tmp"

echo "== Checking server dependencies =="
if [ ! -d "$ROOT_DIR/.venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv "$ROOT_DIR/.venv"
fi
source "$ROOT_DIR/.venv/bin/activate"
python -m pip install --quiet --upgrade pip
pip install --quiet -e "$ROOT_DIR/server[dev]" || pip install --quiet --no-build-isolation -e "$ROOT_DIR/server[dev]"
deactivate

echo "== Building web app for production =="
cd "$WEB_DIR"
npm install --silent
npm run build

echo "== Writing launchd agent for FastAPI server =="
cat > "$AGENTS_DIR/$SERVER_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$SERVER_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd '$ROOT_DIR' &amp;&amp; source .venv/bin/activate &amp;&amp; exec uvicorn server.app.main:app --host 127.0.0.1 --port 8787</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT_DIR/tmp/server.log</string>
  <key>StandardErrorPath</key><string>$ROOT_DIR/tmp/server.err.log</string>
</dict>
</plist>
PLIST

echo "== Writing launchd agent for Next.js web app =="
cat > "$AGENTS_DIR/$WEB_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$WEB_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd '$WEB_DIR' &amp;&amp; exec npm run start</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT_DIR/tmp/web.log</string>
  <key>StandardErrorPath</key><string>$ROOT_DIR/tmp/web.err.log</string>
</dict>
</plist>
PLIST

echo "== Loading services =="
launchctl bootout "gui/$UID_NUM" "$AGENTS_DIR/$SERVER_LABEL.plist" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM" "$AGENTS_DIR/$WEB_LABEL.plist" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$AGENTS_DIR/$SERVER_LABEL.plist"
launchctl bootstrap "gui/$UID_NUM" "$AGENTS_DIR/$WEB_LABEL.plist"

sleep 3
echo "== Status =="
curl -s -o /dev/null -w "API  (http://127.0.0.1:8787): %{http_code}\n" http://127.0.0.1:8787/health || echo "API not responding yet"
curl -s -o /dev/null -w "Web  (http://localhost:3000): %{http_code}\n" http://localhost:3000 || echo "Web not responding yet"

echo ""
echo "Done. The server and web app will now start automatically every time you log in,"
echo "and relaunch themselves if they ever crash. Open http://localhost:3000 anytime."
echo "Logs: $ROOT_DIR/tmp/server.log and $ROOT_DIR/tmp/web.log"
