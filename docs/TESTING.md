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

At packaging time the portable suite has **28 Python tests**, plus web/plist/demo/Swift syntax gates.

The portable verification environment validates shared logic and syntax, **not** macOS framework type-checking, Apple entitlement approval, signed extension activation, real `nettop` behavior across every macOS release, or NetworkExtension enforcement on hardware.

The GitHub Actions macOS job generates the Xcode project and performs an unsigned build. A release still requires a Mac/signing team with the NetworkExtension entitlements.
