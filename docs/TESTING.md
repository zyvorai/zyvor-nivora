# Testing

Run:

```bash
./scripts/test.sh
```

Portable coverage in 0.2 includes:

- `lsof`, `nettop`, route, DNS and interface parsing
- `networksetup` hardware-port enrichment
- ARP and NDP local-neighbor parsing
- listening-service derivation/exposure
- NetworkExtension JSONL latest-report semantics
- live RX/TX delta calculation and app aggregation
- health score, topology and local diagnosis
- persistent behavior-baseline learning
- lease-bounded rules and preview matching
- Time Machine route changes
- SQLite snapshots/events/series
- API auth/CORS/query/rule lifecycle and all intelligence endpoints
- invalid history-query hardening and static-page serving
- web navigation/API contract and `web/lib.js` unit tests (formatting, parsing, sorting, search, CSV injection, preference sanitising, ring buffer, alerts)
- same-origin loopback vs foreign `Origin` handling and dashboard module serving
- demo snapshot
- Swift parser pass when `swiftc` is installed
- plist syntax
- native palette/accent parity with the web tokens and native app file layout
- collector fallback when the App Group rules directory is not writable

At packaging time the portable suite has **29 Python tests**, plus web/plist/demo/Swift syntax gates.

The portable verification environment validates shared logic and syntax, **not** macOS framework type-checking, Apple entitlement approval, signed extension activation, real `nettop` behavior across every macOS release, or NetworkExtension enforcement on hardware.

The GitHub Actions macOS job generates the Xcode project and performs an unsigned build. A release still requires a Mac/signing team with the NetworkExtension entitlements.

## Native unit tests

`native/Tests` holds XCTest cases for snapshot decoding and alert rules, compiled against `App/Model/Snapshot.swift` and `Alerts.swift` only (no UI, no NetworkExtension):

```bash
cd native && xcodegen generate && xcodebuild -project Nivora.xcodeproj -scheme NivoraTests -destination 'platform=macOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO test
```

The fixture `Tests/Fixtures/demo-snapshot.json` comes from `python3 agent/nivora.py --demo --once --no-history`; a Python test fails if its top-level keys drift from the collector.

## Releasing

1. Bump `version` in `package.json`, `VERSION` in `agent/nivora_core.py` and `MARKETING_VERSION` in `native/project.yml`, regenerate `native/Tests/Fixtures/demo-snapshot.json` (a contract test checks all four) and move the changelog entries under the new heading.
2. Merge, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The `release` workflow verifies the tag matches `package.json`, runs the suite, builds the unsigned app, creates `Nivora-X.Y.Z.dmg` plus `SHA256SUMS.txt` and opens a **draft** GitHub release.

The DMG is unsigned and not notarised; shipping the NetworkExtension and capture helper needs Apple signing and entitlement approval (see `docs/NETWORKEXTENSION.md`, `docs/CAPTURE.md`).


## Developer shortcuts

`make help` lists them. `make check` is the fast loop (compile + Python unit tests); `make test` is the full gate; `make test-one T=test_intelligence` runs one module; `make fixtures` regenerates the demo snapshot fixtures after changing snapshot keys; `make app` builds and launches the native app.
