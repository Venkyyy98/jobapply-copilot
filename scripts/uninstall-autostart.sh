#!/usr/bin/env bash
# Removes the auto-start services installed by install-autostart.sh.
set -euo pipefail

AGENTS_DIR="$HOME/Library/LaunchAgents"
SERVER_LABEL="com.jobapplycopilot.server"
WEB_LABEL="com.jobapplycopilot.web"
UID_NUM="$(id -u)"

launchctl bootout "gui/$UID_NUM" "$AGENTS_DIR/$SERVER_LABEL.plist" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM" "$AGENTS_DIR/$WEB_LABEL.plist" 2>/dev/null || true
rm -f "$AGENTS_DIR/$SERVER_LABEL.plist" "$AGENTS_DIR/$WEB_LABEL.plist"

echo "Auto-start services removed."
