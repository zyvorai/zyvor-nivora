#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
APPDIR="$HOME/Library/Application Support/Nivora"
PLIST="$HOME/Library/LaunchAgents/dev.zyvor.nivora.collector.plist"
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
security delete-generic-password -s dev.zyvor.nivora -a "$USER" >/dev/null 2>&1 || true
rm -rf "$APPDIR"
echo "Nivora collector removed. The NetworkExtension preference can be disabled from the Nivora app before deleting the app."
