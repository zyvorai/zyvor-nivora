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

Later additions: alert delivery, retention, tracker and geo files (`test_collector_intel.py`); CLI output, `--json`, version check, completions, man page and the MCP tools, resources and prompts (`test_cli_mcp.py`); SBOM, cask, notarize-script dry run and Pages runner (`test_release_tools.py`); native/web pane parity (`test_pane_parity.py`).

The portable suite now has **138 Python tests**, plus web/plist/demo/Swift syntax gates and `bash -n scripts/notarize-mini.sh`.

The portable verification environment validates shared logic and syntax, **not** macOS framework type-checking, Apple entitlement approval, signed extension activation, real `nettop` behavior across every macOS release, or NetworkExtension enforcement on hardware.

The GitHub Actions macOS job generates the Xcode project and performs an unsigned build. A release still requires a Mac/signing team with the NetworkExtension entitlements.

## Native unit tests

`native/Tests` holds XCTest cases (37 at the time of writing) for snapshot decoding, alert rules, filters, exports, widgets and the Explore helpers (Domains, Network Map layout, palette ranking), compiled against the `App/Model` files listed in `native/project.yml` only (no UI, no NetworkExtension):

```bash
cd native && xcodegen generate && xcodebuild -project Nivora.xcodeproj -scheme NivoraTests -destination 'platform=macOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO test
```

The fixture `Tests/Fixtures/demo-snapshot.json` comes from `python3 agent/nivora.py --demo --once --no-history`; a Python test fails if its top-level keys drift from the collector.

## Releasing

1. Bump `version` in `package.json`, `VERSION` in `agent/nivora_core.py` and `MARKETING_VERSION` in `native/project.yml`, regenerate `native/Tests/Fixtures/demo-snapshot.json` (a contract test checks all four) and move the changelog entries under the new heading.
2. Merge, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The `release` workflow verifies the tag matches `package.json`, runs the suite, builds the unsigned app, creates `Nivora-X.Y.Z.dmg` plus `SHA256SUMS.txt` and opens a **draft** GitHub release.

The CI DMG is unsigned and not notarised; shipping the NetworkExtension and capture helper needs Apple signing and entitlement approval (see `docs/NETWORKEXTENSION.md`, `docs/CAPTURE.md`).

CI's macOS job runs on a hosted runner that is much slower than a laptop; timing tests use generous deadlines for that reason.

### Signed and notarized build (maintainers, on a Mac with the Developer ID certificate)

`scripts/notarize-mini.sh` runs the same build on the Mac mini over ssh (see `docs/RELEASING.md`).

```bash
DEVELOPER_ID_APP="Developer ID Application: NAME (TEAMID)" NOTARY_PROFILE=<notarytool keychain profile> ./scripts/package-signed.sh
```

It writes `release-signed/Nivora-X.Y.Z.dmg` (+ `.sha256`, git-ignored), notarizes, staples and runs `spctl`. The standard build omits the content filter and capture helper. Check by hand before shipping: `codesign --verify --deep --strict`, `spctl -a -t exec -vv` on the app inside the mounted DMG, no restricted entitlements (`codesign -d --entitlements -`), then open the app on a real desktop and confirm Overview shows data. Do not feed it fixtures only: run the bundled collector against a Mac that has FluxVM running and decode that output with `native/App/Model/Snapshot.swift`, because demo data uses a different FluxVM shape than the real API (that gap hid the 0.5.2 "Collector unavailable" bug).


## Developer shortcuts

`make help` lists them. `make check` is the fast loop (compile + Python unit tests); `make test` is the full gate; `make test-one T=test_intelligence` runs one module; `make fixtures` regenerates the demo snapshot fixtures after changing snapshot keys; `make app` builds and launches the native app.
