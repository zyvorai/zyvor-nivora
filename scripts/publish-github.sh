#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VISIBILITY="${1:-public}"
case "$VISIBILITY" in public|private|internal) ;; *) echo "usage: $0 [public|private|internal]" >&2; exit 2;; esac
command -v gh >/dev/null || { echo "GitHub CLI (gh) is required" >&2; exit 1; }
cd "$ROOT"
if [[ ! -d .git ]]; then git init -b main; git add .; git commit -m 'feat: initial Nivora macOS network intelligence product'; fi
if gh repo view zyvorai/zyvor-nivora >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/zyvorai/zyvor-nivora.git
  git push -u origin main
else
  gh repo create zyvorai/zyvor-nivora "--$VISIBILITY" --source . --remote origin --push --description "Mac-native application and network intelligence for apps, DNS, VPN, routes and FluxVM"
fi
