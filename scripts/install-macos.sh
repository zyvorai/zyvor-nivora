#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPDIR="$HOME/Library/Application Support/Nivora"
PLIST="$HOME/Library/LaunchAgents/dev.zyvor.nivora.collector.plist"
PORT="${NIVORA_PORT:-9857}"
mkdir -p "$APPDIR/agent" "$APPDIR/web" "$HOME/Library/LaunchAgents"
cp "$ROOT/agent/nivora.py" "$ROOT/agent/nivora_core.py" "$ROOT/agent/capture.py" "$ROOT/agent/containers.py" "$ROOT/agent/ports.py" "$ROOT/agent/anomalies.py" "$ROOT/agent/dns_diag.py" "$ROOT/agent/explain.py" "$ROOT/agent/lan.py" "$ROOT/agent/metrics.py" "$ROOT/agent/projects.py" "$ROOT/agent/usage.py" "$ROOT/agent/diff.py" "$ROOT/agent/pathcheck.py" "$ROOT/agent/nivora_mcp.py" "$ROOT/agent/identity.py" "$ROOT/agent/trust.py" "$ROOT/agent/privacy.py" "$ROOT/agent/policy.py" "$ROOT/agent/profiles.py" "$ROOT/agent/egress.py" "$ROOT/agent/fleet.py" "$ROOT/agent/nivoractl.py" "$APPDIR/agent/"
cp -R "$ROOT/web/." "$APPDIR/web/"
TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
security delete-generic-password -s dev.zyvor.nivora -a "$USER" >/dev/null 2>&1 || true
security add-generic-password -U -s dev.zyvor.nivora -a "$USER" -w "$TOKEN" >/dev/null
cat > "$APPDIR/run-collector.sh" <<EOF
#!/bin/bash
set -euo pipefail
TOKEN=\"\$(security find-generic-password -s dev.zyvor.nivora -a \"\$USER\" -w)\"
exec /usr/bin/env python3 \"$APPDIR/agent/nivora.py\" --port \"$PORT\" --token \"\$TOKEN\" --web-root \"$APPDIR/web\"
EOF
chmod 700 "$APPDIR/run-collector.sh"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>dev.zyvor.nivora.collector</string>
<key>ProgramArguments</key><array><string>$APPDIR/run-collector.sh</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$APPDIR/collector.log</string>
<key>StandardErrorPath</key><string>$APPDIR/collector.err</string>
</dict></plist>
EOF
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
ln -sf "$APPDIR/agent/nivoractl.py" "$APPDIR/nivoractl"
printf 'Installed Nivora collector.\nOpen: http://127.0.0.1:%s/#token=%s\nCLI: %s/nivoractl\n' "$PORT" "$TOKEN" "$APPDIR"
