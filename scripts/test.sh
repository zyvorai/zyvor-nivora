#!/usr/bin/env bash
# SPDX-License-Identifier: BUSL-1.1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m py_compile agent/nivora_core.py agent/capture.py agent/nivora.py agent/nivoractl.py agent/containers.py agent/ports.py agent/anomalies.py agent/dns_diag.py agent/explain.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --experimental-vm-modules tests/web.mjs
node tests/demo.mjs
./scripts/build-site.sh >/dev/null && node scripts/site-check.mjs
if command -v swiftc >/dev/null 2>&1; then
  while IFS= read -r f; do swiftc -parse "$f"; done < <(find native/App native/Shared native/FilterData native/CaptureHelper native/Tests -name '*.swift' | sort)
  echo "swift syntax: PASS"
else
  echo "swiftc unavailable: SKIP syntax parse"
fi
python3 - <<'PY2'
import plistlib, pathlib
for p in pathlib.Path('native/Config').glob('*.plist'):
    plistlib.loads(p.read_bytes())
for p in pathlib.Path('native/Config').glob('*.entitlements'):
    plistlib.loads(p.read_bytes())
print('plist syntax: PASS')
PY2
python3 agent/nivora.py --demo --once >/tmp/nivora-demo.json
python3 - <<'PY'
import json
s=json.load(open('/tmp/nivora-demo.json'))
assert s['apps'] and s['flows'] and s['interfaces'] and s['fluxvm']['connected']
assert s['version'] == json.load(open('package.json'))['version'], 'collector VERSION must match package.json'
assert s['traffic']['total_bps'] > 0 and 0 <= s['health']['score'] <= 100
assert s['topology']['nodes'] and s['neighbors'] and s['listeners']
assert s['fluxvm']['network_endpoints'] and s['fluxvm']['hubble_flows']
print('demo snapshot: PASS')
PY
