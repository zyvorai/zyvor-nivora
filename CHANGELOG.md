# Changelog

## Unreleased

- Site: terminal tabs with real `nivoractl` output captured at build time, a verified-vs-not table copied from the README, a command palette (`/` or ⌘K) over sections, docs and demo panes, and a Homebrew install line.

- Site: `/docs/` hub built from `docs/*.md`, `CHANGELOG.md` and `SECURITY.md` by `scripts/build-docs.py` (stdlib Markdown subset, heading anchors, on-page TOC, search over titles and headings).

- Site: the static demo now simulates flow explain, profiles, fleet, path check, diff/incident, policy dry-run and rule impact; gallery adds Insights, Alerts and Settings with arrow-key navigation and a link into the matching demo pane; new feature cards.


## 0.5.2 — 2026-10-16

- **Fix: "Collector unavailable" on every Mac that runs FluxVM.** FluxVM answers `/v1/vms` with `{"items": [...]}` and `status`; the collector forwarded that object, the native app expects an array, so decoding the whole snapshot failed and the app showed an error for a collector that was running fine. The collector now normalises `vms` and `sandboxes` to lists with `state` (`fluxvm_workloads`), the egress code accepts the envelope too, and the native decoder is tolerant: an unexpected shape in this optional section can no longer blank the app. Regression tests cover the collector, egress and the Swift decoder with real-shaped data.
- Fix: the app no longer flashes "Collector unavailable" while the bundled collector starts (about 3 s). A failed poll within the first 20 s with no data keeps "Starting Nivora…"; once data has been shown a failed poll never replaces it.
- Native: when the content-filter extension is not in the bundle the app says so ("Content filter is not included in this build") instead of showing a raw system error.
- New: `scripts/package-signed.sh` builds a Developer ID signed, hardened-runtime, notarized and stapled DMG. It omits the content-filter extension and the capture helper (a plain Developer ID signature cannot carry their restricted NetworkExtension entitlements) and refuses to sign if restricted entitlements are present. `package-dmg.sh` gains `SUFFIX`/`OUT_DIR` and writes a relative checksum file. The GitHub release DMG from CI is unchanged: ad-hoc signed, not notarized.

## 0.5.1 — 2026-10-15

- Release DMG: the app is ad-hoc signed before packaging so `codesign --verify --deep --strict` passes (resources are sealed). Still not Developer ID signed or notarised.

## 0.5.0 — 2026-10-15

- Native: WidgetKit "Network" widget (small and medium) fed by `widget.json` in the widget's container, built with `make widgets`; documented in `docs/WIDGETS.md`. Compile- and codesign-verified only.
- Fix: the bundled collector no longer outlives the app. It exits when the launching process is gone (`--parent-pid`), and the app picks the next free loopback port if 9857 is held by a stale collector.
- Trust score per app, privacy report card, verified process identity (path, signing, team ID; "unsigned binary contacting the internet"), situation profiles, policy-as-code (`/v1/policy`, dry-run by default), FluxVM sandbox egress lens, push-only multi-Mac fleet view; `nivoractl` verbs for all of them.
- Web: Insights view. Native: Insights pane, Shortcuts/Siri actions ("How is my network?", "Block an app for one hour"), and opt-in notifications for new destinations with Observe / Block 1 h (after the fact; connections are not paused).
- Time-travel diff and incident narrative: `/v1/diff`, `/v1/incident`, `nivoractl diff|incident`; on-demand path check (`/v1/path-check`, `nivoractl path-check`); read-only MCP server `agent/nivora_mcp.py`.
- LAN change detection: new device on the network (learned by MAC after a baseline), IP→MAC change, gateway MAC change (critical), Wi-Fi network change, and "DNS may bypass the VPN"; findings and Time Machine events.
- Daily per-app usage with optional budgets (`budgets.json`), `/v1/usage`; project attribution (`project` on flows, `/v1/projects`); Prometheus `/metrics`.
- Web: "Why this flow?" in the flow sheet and a shadow rule option. Draft Homebrew cask in `packaging/homebrew/` (unverified).
- Why this flow?: `GET /v1/flows/{id}/explain` and `nivoractl explain <id>` collect the evidence for one flow. Shadow rules (`action: shadow`) and `/v1/rule-impact` show what a block would match before it is enabled.
- Dev: `make help`, `check`, `test-one`, `fixtures`, `app`, `stop`, `clean` shortcuts (documented in `docs/TESTING.md`).

- Developer intelligence: container runtime awareness (`containers`), port ownership/conflicts (`port_conflicts`, flagged on listeners), rate-based anomaly findings, and DNS resolver diagnosis (`dns_diagnosis`); `/v1/containers` and `/v1/port-conflicts`. Collector stays stdlib-only and observe-only.
- Docs: `docs/INSTALL.md` explains the unsigned, un-notarised release (Gatekeeper messages, Open Anyway on macOS 15+, Control-click on 14, `xattr`, checksum verification, what works unsigned, uninstall); linked from the README and the site's install section and FAQ.
- Docs: Time Machine in the screenshot gallery and site picker; `scripts/build-tour.py` builds `docs/social/nivora-tour.gif` (a pane tour from the real native screenshots, not a screen recording) for the README.
- Native Time Machine pane: events by day with kind filter and text filter (`TimelineKit`), icons per kind, auto-refresh.
- Fix: `--demo` no longer writes simulated snapshots, events or destination baselines into the real history database; the simulated Mac has a seeded in-memory event history instead.
- Static in-browser demo (`web/demo.js`, `?demo` or `data-demo`): the real dashboard runs on simulated telemetry with no collector; the demo Mac now has 8 apps.
- GitHub Pages site (`site/`, `scripts/build-site.sh`, `scripts/site-check.mjs`, `.github/workflows/pages.yml`): landing page with a light/dark pane gallery, plus the dashboard under `/demo/`.
- README rewritten to the Zyvor product standard (hero, why table, screenshots, tiers, maturity, licence); `scripts/shots-native.sh` and `scripts/build-hero.py` regenerate the images from the real app.
- The dashboard loads assets by relative path so it works under a sub-path.
- Brand: app icon (an N drawn as a network path) with `scripts/build-brand.sh` deriving the icns, favicon, apple-touch icon and share image from one master SVG; the real icon replaces the letter badge in the dashboard.
- Native: first-run welcome sheet (once; `--welcome` forces it), per-app sparklines and a "What changed" panel on the Overview, Help menu links and a ⌘/ shortcuts sheet, About section in Settings.
- Legal: Zyvor name, `© 2026 Zyvor AI Labs Private Limited` and BUSL-1.1 shown in the app (bundle copyright, welcome, Settings), the dashboard footer and the share image, matching Zyvor Vytrix.
- The collector no longer writes `__pycache__` into the app bundle.
- Release workflow: pushing a `v*` tag builds an unsigned DMG with checksums and drafts a GitHub release (checks the tag against `package.json`).
## 0.3.0 — 2026-10-13

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
