# Changelog

## Unreleased

- Native Flows pane shows a live throughput strip above the filter bar; the Overview Connections tile has a sparkline.
- Native: byte/rate formatters show "0 bytes" instead of "Zero KB"; the app activates and fronts its window on launch (first `open` from LaunchServices could leave it hidden).
- Native UX: filter bar (removable chips, quick filters, "N of M", saved views) on Flows and Applications, baseline compare card, flow rate sparkline in the inspector, inspector reachable from the application sheet, "Clear filter" empty states, ⌘1–⌘9 pane shortcuts (Go menu), last pane remembered, wider table columns.
- Fix: the app bundle never contained the collector or dashboard (xcodegen ignores a top-level `resources:` key); they are now bundled as resource sources, including `capture.py`, and `install-macos.sh` installs `capture.py`. A contract test guards both.
- Opt-in packet capture: privileged `NivoraCaptureHelper` (SMAppService daemon; fixed-argv tcpdump, structured validated requests, caps, 24 h retention), `/v1/captures` API, web and native Capture panes, "Capture this flow", pcap download, demo simulation. Compile- and unit-verified only; see `docs/CAPTURE.md`.
- Flow inspector (web sheet, native `FlowDetailSheet`), grouped Flows views (by app/host/interface), pinned-baseline compare (web), `first_seen`/`last_seen` per flow, and a demo that now varies over time so charts have shape.
- `GET /v1/export` (flows/apps/timeline/snapshot/bundle; CSV/JSON/NDJSON/zip; current filter; salted-hash redaction) with an Export dialog in the web UI and an Export menu in the native Flows pane.
- Flow filter grammar (`app: host: port: proto: iface: state: source: >1mbps !neg`) shared by collector, web and native, with `GET /v1/flows?filter=`, `nivoractl flows --filter`, removable filter chips and saved views (web localStorage / native UserDefaults, palette + Views menu).
- Native Flows pane exports the current (filtered, sorted) flows as CSV with spreadsheet-formula neutralisation, matching the web export.
- Native XCTest target `NivoraTests` (snapshot decoding, alert rules) with a demo-collector fixture; run in the macOS CI job.
- Dashboard UX pass toward Vytrix parity: command palette (`⌘K`), keyboard shortcuts, application detail sheet, sortable/highlighted tables, throughput chart with tooltip, per-app sparklines, toasts, skeleton/error states, Settings view (theme, accent, density, refresh, alert threshold, pinned apps), snapshot JSON and flows CSV export.
- Health ring now reflects the real score and status.
- Fix: the collector rejected the dashboard's own same-origin `Origin` header (module script fetch and rule POSTs returned 403 in a browser). Loopback same-origin is now accepted; foreign origins are still rejected.
- Web logic split into `web/lib.js` with unit tests.
- Web dashboard recoloured with the Netra palette and SF type scale (light-first, dark via OS or Settings); accents are now blue/cyan/green/amber/purple/graphite.
- Native app rebuilt in Vytrix's structure (Model/Views split, Panel/MetricTile/Meter components, Swift Charts, Settings, menu-bar window, Alerts, app detail sheet, `--appearance`/`--section` flags) with the same Netra palette; palette parity with the web is tested.
- Fix: the collector no longer crashes at startup when the App Group rules directory cannot be created (unsigned builds); it falls back to `~/.local/share/nivora/rules.json`.
- NetworkExtension ported to macOS APIs: a single content-filter system extension (`NEFilterDataProvider` + `handle(_:)` reports) replaces the iOS-style data/control app extensions; source app identity from audit tokens; macOS 15 flow endpoints with a macOS 14 hostname fallback; `./scripts/build-native.sh` now builds the app with the embedded extension.
- Fix: entitlements and Info.plist keys are now declared in `project.yml` (xcodegen was overwriting the checked-in plists with empty ones); the app declares system-extension install and content-filter entitlements.
- The app activates the extension via `OSSystemExtensionRequest` before enabling the filter (observe-first, user initiated).

## 0.2.0 — 2026-10-13

- Live per-flow and per-app RX/TX rates from counter deltas.
- 0–100 network health model with explainable route/DNS/latency/interface/safety components.
- Local network diagnosis and traffic history series.
- App → interface → destination Network Map.
- ARP/NDP neighbors, listening services and exposure classification.
- `networksetup` hardware-port/Wi-Fi enrichment.
- Persistent destination behavior learning with first-seen findings and Time Machine events.
- VPN-state, listener and traffic-spike Time Machine events.
- One-hour default leases for block rules; validation for predicates, ports, IPs and expiries.
- FluxVM network health, endpoints, Hubble flows and observe-state integration, plus host-flow correlation.
- New health/traffic/topology/neighbors/listeners/behavior/diagnose/series APIs and CLI commands.
- Native Health and Local Network views, live bandwidth columns and menu-bar health/rates.
- Web Health, Network Map and Local Network views.
- Local API/static-serving hardening.
- Expanded portable test suite from 13 to 21 Python tests plus web/plist/demo/Swift syntax gates.

## 0.1.0 — 2026-10-13

- Initial Nivora product repository.
- Per-app flow model with NetworkExtension JSONL ingestion, `nettop` and `lsof` fallback.
- DNS, route, interface and VPN inventory.
- FluxVM integration against the local REST API.
- SQLite history and Network Time Machine events.
- Observe/allow/block rules with live preview and signed extension enforcement path.
- Local investigator.
- Vytrix-style dependency-free dashboard.
- Native SwiftUI app, filter-data provider and filter-control provider.
- `nivoractl`, `launchd` installer, CI and test suite.
