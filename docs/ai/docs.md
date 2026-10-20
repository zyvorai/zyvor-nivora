# AI docs (zyvor-nivora)

_Generated 2026-10-20 by claude-opus-5-5 from a snapshot of tracked sources; verify before acting._

# Part 1: Improved README.md

````markdown
<div align="center">

<img src="docs/brand/nivora-icon.svg" width="112" alt="Zyvor Nivora app icon" />

# Zyvor Nivora

[![verify](https://github.com/zyvorai/zyvor-nivora/actions/workflows/ci.yml/badge.svg)](https://github.com/zyvorai/zyvor-nivora/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-BUSL--1.1-0071e3)](LICENSE)
[![Platform](https://img.shields.io/badge/macOS%2014%2B-000000)](docs/TESTING.md)
[![Collector](https://img.shields.io/badge/collector-python%203%20%C2%B7%200%20deps-32ade6)](agent/nivora.py)
[![Mode](https://img.shields.io/badge/mode-observe--first-34c759)](#privacy-and-safety)

![Zyvor Nivora: see every connection on your Mac](docs/social/nivora-hero.jpg)

### See every connection on your Mac.

**Nivora shows which app on your Mac is talking to what, over which interface.** It covers per-app flows, DNS, routes, VPNs, listeners and FluxVM workloads. It runs as a native SwiftUI app or a browser dashboard, both backed by a Python collector that uses only the standard library. Local-first and observe-first.

🎮 **[Live demo](https://zyvorai.github.io/zyvor-nivora/demo/)** · 🌐 **[Site](https://zyvorai.github.io/zyvor-nivora/)** · 🚀 **[Quickstart](#quickstart)** · ⚙️ **[Configuration](#configuration)** · 🔒 **[Privacy](#privacy-and-safety)** · 📖 **[API](docs/API.md)**

</div>

## Why Nivora

| When this happens | Nivora gives you |
| --- | --- |
| "Something is eating my bandwidth" | Live ↓/↑ rate per application, plus an inspector for every app and flow |
| "What is this connection to `17.253.x.x`?" | The owning app, remote endpoint, interface, RTT and every other flow to the same host |
| "Did my VPN or DNS just change?" | A **Time Machine** of interface, DNS, route, VPN, listener and device changes, stored in SQLite |
| "Is the network actually healthy?" | A **0–100 health score** with explained components (route, DNS, latency, interfaces, safety) and an offline investigator |
| "I need to hand this to someone" | **CSV / JSON / NDJSON / zip exports** of the current filter. Exports can optionally be redacted of private IPs, MACs, SSID and hostname |
| You run VMs or sandboxes with FluxVM | Workloads shown beside host traffic, read from FluxVM's local REST API |

## See it

**[Try the live demo](https://zyvorai.github.io/zyvor-nivora/demo/)**. It is the real web dashboard running in your browser on simulated telemetry, with nothing to install.

![Tour of the native app: Overview, Flows, Applications, Health, Time Machine, Capture, Security](docs/social/nivora-tour.gif)

| Light | Dark |
| --- | --- |
| ![Overview, light](docs/ux/native-light-overview.png) | ![Overview, dark](docs/ux/native-dark-overview.png) |
| ![Flows, light](docs/ux/native-light-flows.png) | ![Flows, dark](docs/ux/native-dark-flows.png) |
| ![Applications, light](docs/ux/native-light-applications.png) | ![Capture, dark](docs/ux/native-dark-capture.png) |
| ![Time Machine, light](docs/ux/native-light-timeline.png) | ![Time Machine, dark](docs/ux/native-dark-timeline.png) |

*Every image shows the native app on its built-in **simulated telemetry** (host `zyvor-mac-studio`). They are window-only captures made with `./scripts/shots-native.sh`.*

## Requirements

| To run | You need |
| --- | --- |
| Collector + web dashboard | macOS and Python 3. No third-party packages are needed. |
| Native app (build from source) | macOS 14+, Xcode (Swift 6 mode) and [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`) |
| Native app (at runtime) | Python 3 at `/opt/homebrew/bin/python3`, `/usr/local/bin/python3` or `/usr/bin/python3`. The app launches its bundled collector with it. |
| Content filter / capture helper | A signed, provisioned build. See [Maturity](#maturity). |
| Running the test suite | Python 3 and Node.js (CI uses Python 3.13 and Node 22). `swiftc` is optional. |

## Quickstart

```bash
# 1. Try it on simulated data
python3 agent/nivora.py --demo

# 2. Monitor this Mac (dashboard + API on 127.0.0.1:9857)
python3 agent/nivora.py          # or ./scripts/run.sh

# 3. Or build the native app
brew install xcodegen
./scripts/build-native.sh
open native/build/Build/Products/Release/Nivora.app
```

**Collector token.** When run directly, the collector prints a URL with a one-time token in the fragment (`#token=…`). The page reads the token and removes it from the address bar. The browser keeps it only in memory.

**Native app collector.** The native app starts its bundled collector on loopback with a random in-memory token. It uses port 9857, or the next free port if 9857 is taken. Closing the window keeps Nivora and its collector running in the menu bar. **Quit** stops both. The collector also exits if the app that launched it goes away.

### Installing a release build

GitHub Release DMGs are **ad-hoc signed only**. They are not signed with a Developer ID and are not notarised, so Gatekeeper blocks the first launch. You have three options:

- Build the app yourself (it is not quarantined).
- Use **System Settings → Privacy & Security → Open Anyway**.
- See [docs/INSTALL.md](docs/INSTALL.md) for checksum verification, the macOS 14 steps and uninstalling.

## Usage

### Per-user service (launchd)

```bash
./scripts/install-macos.sh     # launchd agent dev.zyvor.nivora.collector, token in Login Keychain
./scripts/uninstall-macos.sh   # removes the agent, the Keychain item and ~/Library/Application Support/Nivora
```

The installer:

- copies the collector and dashboard to `~/Library/Application Support/Nivora`;
- starts the collector at login;
- prints the dashboard URL with its token;
- links the CLI at `~/Library/Application Support/Nivora/nivoractl`.

Set `NIVORA_PORT` before installing to use a port other than 9857.

### CLI: `nivoractl`

```bash
python3 agent/nivoractl.py status
python3 agent/nivoractl.py flows --filter 'app:Safari port:443 >1mbps'
python3 agent/nivoractl.py explain <flow-id>
python3 agent/nivoractl.py ask which app uploaded the most
python3 agent/nivoractl.py rule-add --action shadow --domain example.com
python3 agent/nivoractl.py rule-add --action block --domain example.com --duration 900
python3 agent/nivoractl.py diff --from 2026-10-15T10:00:00Z --to 2026-10-15T10:30:00Z
python3 agent/nivoractl.py path-check example.com --port 443
python3 agent/nivoractl.py policy-plan work.json      # dry run; policy-apply applies
```

**Read commands** print JSON from the matching `/v1/*` endpoint:

`status`, `apps`, `flows`, `interfaces`, `routes`, `dns`, `vpn`, `fluxvm`, `findings`, `timeline`, `rules`, `health`, `traffic`, `topology`, `neighbors`, `listeners`, `behavior`, `diagnose`, `series`, `usage`, `projects`, `containers`, `port-conflicts`, `trust`, `privacy`, `egress`, `profiles`, `fleet`, `policy-export`, `rule-impact`, `explain`, `diff`, `incident`

**Write and active commands:**

`ask`, `rule-add`, `rule-delete`, `profile <name>`, `policy-plan`, `policy-apply`, `path-check`

**Connection:**

- `nivoractl` uses `--url` (default `NIVORA_URL` or `http://127.0.0.1:9857`).
- It uses `--token` (default `NIVORA_TOKEN`). On macOS it falls back to the token stored by `install-macos.sh`.

### Filter grammar

The same grammar is used by the collector, the web dashboard, the native app and the CLI. Parity is tested against `tests/fixtures/filter-vectors.json`.

```text
app:Safari  host:example.com  port:443  port:8000-9000  proto:tcp  iface:en0
state:established  source:nettop  >1mbps  <500kbps  !iface:lo0  app:"Google Chrome"
```

How terms combine:

- Different keys are combined with AND.
- A repeated key is OR.
- `!` or `-` excludes, and exclusions always win.
- Unkeyed text matches any field.

See [docs/API.md](docs/API.md#filter-grammar).

### Native app

**Panes:** Overview, Health, Applications, Flows, Time Machine, Interfaces, Local Network, FluxVM, Security, Insights, Capture, Investigator, Alerts and Settings.

| Pane | What it does |
| --- | --- |
| **Overview** | Health, ↓/↑ rate and connection tiles with sparklines; throughput chart; top apps; "What changed"; "What needs attention" |
| **Applications / Flows** | Sortable tables and a filter bar with chips, quick filters and saved views. Flows can be grouped by app/host/interface and compared against a pinned baseline. Includes a flow inspector and an export menu (CSV, NDJSON, zip bundle, optionally redacted). |
| **Health** | Score, explained components and history chart |
| **Time Machine** | Events grouped by day, filterable by kind and text |
| **Interfaces / Local Network** | Interfaces, Wi-Fi, routes, DNS and VPN. ARP/NDP neighbours and listening services, with all-interface binds highlighted. |
| **FluxVM** | Connection status, VMs and sandboxes |
| **Security** | Visibility status, NetworkExtension toggle, findings and rules |
| **Insights** | Situation profile, privacy report card, per-app trust score and sandbox/VM egress |
| **Capture** | Opt-in, headers-only packet capture through the privileged helper |
| **Investigator** | Deterministic, offline answers from local telemetry |
| **Alerts / Settings** | Findings and threshold alerts. Appearance, accent, per-app throughput alert, new-destination notifications, live vs demo data. |

**Menu bar:** health, live rates, the top four apps and an alert count, plus Pause and Quit.

**Keyboard:**

| Shortcut | Action |
| --- | --- |
| `⌘1…⌘9` | First nine panes (Go menu) |
| `⌘,` | Settings |
| `⌘/` | Shortcuts sheet |
| `⌘R` | Refresh |
| `⌘P` | Pause / resume |
| `⇧⌘1` / `⇧⌘2` | Monitor this Mac / demo data |

**Launch flags** (used for screenshots and QA):

| Flag | Effect |
| --- | --- |
| `--demo` | Use simulated data |
| `--appearance light\|dark` | Force the appearance |
| `--section <pane title>` | Open a specific pane |
| `--welcome` / `--no-welcome` | Force or suppress the first-run welcome sheet |

**Shortcuts:** "How is my network?" (with Siri phrases) and "Block an app for one hour" (asks for confirmation; enforced only with the content filter).

**Widget:** there is a read-only **Network** widget (small/medium). Build it with `./scripts/build-native-widgets.sh` (or `make widgets`). See [docs/WIDGETS.md](docs/WIDGETS.md).

### Web dashboard

The collector serves the dashboard at `http://127.0.0.1:9857/`. Its views are:

- Overview, Health, Network Map, Applications, Flows, Domains
- DNS, Interfaces, Routes, VPN, Local Network
- FluxVM, Security, Insights, Time Machine, Capture, Investigator, Settings

It also has an export dialog. Keyboard shortcuts:

| Shortcut | Action |
| --- | --- |
| `⌘K` / `Ctrl K` | Command palette |
| `/` | Search |
| `p` | Pause |
| `r` | Refresh |
| `g` then `o/h/m/a/f` | Jump to a view |
| `Esc` | Close panels |

### Integrations

- **HTTP API**: `/v1/*` with a bearer token. See [docs/API.md](docs/API.md).
- **Prometheus**: `GET /metrics` exposes health, flows, rates, findings by severity, listeners, port conflicts and the top 20 apps. It uses the same token as the API.
- **MCP**: `agent/nivora_mcp.py` is a read-only MCP server over stdio. It exposes the tools `summary`, `flows`, `findings`, `explain_flow`, `ask`, `diff`, `incident`, `port_conflicts`, `rule_impact` and `path_check`. Configure it with `NIVORA_URL` / `NIVORA_TOKEN`.
- **Multi-Mac fleet**: workers push a compact summary to a coordinator with `--fleet-push <url> --fleet-token <token> [--fleet-interval <s>]`. It is push-only: there is no command channel and the coordinator never connects out.

## How it fits together

```text
              Nivora.app (SwiftUI)  /  browser dashboard  /  nivoractl  /  MCP
                            │   HTTP JSON · 127.0.0.1 · bearer token
                        nivora.py   (Python stdlib only)
            ┌───────────────┼────────────────┐
     NetworkExtension    nettop · lsof     FluxVM :7788
     content filter     ifconfig · netstat  VMs · sandboxes
     (signed, opt-in)   scutil · arp · ndp
            └───────────────┴──────→ SQLite time machine
```

| Visibility tier | Needs | Gives you |
| --- | --- | --- |
| **Collector fallback** | Nothing extra | Per-app flows and byte counters (`nettop` first, `lsof` fallback); interfaces, routes, DNS, VPNs, neighbours and listeners |
| **Content filter** | Signed build + Apple NetworkExtension entitlement | Per-flow app attribution (audit tokens), ~1 s byte reports and enforcement of block rules |
| **Capture helper** | Signed build + your approval in System Settings › Login Items | Headers-only `.pcap` for one interface / IP / protocol / port, for up to 5 minutes |

All tiers produce the same JSON schema. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/NETWORKEXTENSION.md](docs/NETWORKEXTENSION.md).

## Configuration

### Collector flags

These flags appear in the repo's scripts and tests. `agent/nivora.py` is the authoritative list.

| Flag | Purpose |
| --- | --- |
| `--demo` | Simulated telemetry. It never writes to the real history database. |
| `--once` | Print one snapshot as JSON and exit |
| `--no-history` | Do not use the SQLite history |
| `--bind`, `--port` | Listen address and port (loopback, `9857` by default) |
| `--token` | Bearer token for `/v1/*` |
| `--web-root` | Directory of dashboard files to serve |
| `--database`, `--rules` | Paths of the history database and rule file |
| `--interval` | Sample interval in seconds |
| `--quiet` | Less output |
| `--parent-pid` | Exit when this process is gone (used by the native app) |
| `--fleet-push`, `--fleet-token`, `--fleet-interval` | Push summaries to a fleet coordinator |

### Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `FLUXVM_SERVER`, `FLUXVM_TOKEN` | collector | FluxVM API (default `http://127.0.0.1:7788`). See [docs/FLUXVM.md](docs/FLUXVM.md). |
| `NIVORA_URL`, `NIVORA_TOKEN` | `nivoractl`, MCP server | API base URL and token |
| `NIVORA_CAPTURE_SOCKET` | collector | Capture helper socket (default `/var/run/dev.zyvor.nivora.capture.sock`) |
| `NIVORA_PORT` | `install-macos.sh` | Port for the launchd collector |
| `DEVELOPMENT_TEAM` | `build-native.sh` | Signing team. Without it the build is unsigned (`CODE_SIGNING_ALLOWED=NO`). |

### Files

| File | Purpose |
| --- | --- |
| `rules.json` | Rule store. It lives in the `group.dev.zyvor.nivora` App Group (shared with the content filter). If that directory cannot be created, it falls back to `~/.local/share/nivora/rules.json`. |
| `budgets.json` | Optional daily per-app budgets, beside the history database: `{"app name substring": bytes_per_day}` |
| Situation profiles | `default`, `coding`, `presenting`, `travel`. They change alert thresholds, budget scale and info-finding visibility, but never relax blocking rules. Set them with `nivoractl profile <name>` or the Insights pane. |
| Policy files | `{"name": "...", "rules": [...]}`, applied via `POST /v1/policy`. This is a dry run by default. |

## Privacy and safety

- **Local-first.** No account, no cloud and no telemetry upload. The API binds to loopback, `/v1/*` requires a bearer token (compared in constant time) and foreign browser origins are rejected. Do not expose it on a non-loopback address without an authenticated TLS reverse proxy.
- **Observe-first.** Rules are inert in collector-only mode.
  - Block rules default to a one-hour lease. You can choose 60 s–7 days with `duration_seconds`, or `permanent: true` explicitly.
  - Only the signed `NEFilterDataProvider` can drop traffic.
  - Explicit allow rules override broader blocks.
  - `shadow` rules count what a block would match without enforcing it.
- **No payloads.** Nivora collects flow metadata only. The one exception is [packet capture](docs/CAPTURE.md), which:
  - is off until you start it and confirm;
  - is headers-only by default (96 bytes, maximum 256);
  - is capped at 5 min and 64 MB, one capture at a time;
  - stores files root-only on disk and deletes them after 24 h.
- **Read-only collection.** The fallback runs read-only macOS commands: `nettop`, `lsof`, `ifconfig`, `netstat`, `scutil`, `networksetup`, `arp`, `ndp`, `ps` and `codesign`, and does not need root. The only active probe is `path-check`, which runs only when you ask.
- **Redacted exports.** Exports can replace private IPs, MACs, SSIDs, DNS names and the hostname with salted hash tokens.

Report security issues as described in [SECURITY.md](SECURITY.md).

## Maturity

| Area | Status |
| --- | --- |
| Collector, API, dashboard, CLI, exports, filters | Built and tested in CI (Python, Node) |
| Native app (SwiftUI) and unit tests | Builds and runs unsigned with Xcode; XCTest suite passes in the macOS CI job |
| Content filter (system extension) and capture helper | **Compile-verified only.** Signing, entitlement approval, activation, flow attribution, report cadence, drop enforcement and root capture are untested; they need a provisioned, signed Mac |
| Insights pane, Shortcuts/Siri actions, widget | Build and unit tests pass; the widget in the macOS widget gallery and the Shortcuts/Siri phrases are **not exercised** |
| Release DMG | Ad-hoc sealed, unsigned by a Developer ID, not notarised (Gatekeeper asks for Open Anyway) |
| Homebrew cask (`packaging/homebrew/`) | Draft; untested through Homebrew |

## Project layout

```text
agent/       nivora.py (collector + API), nivora_core.py, nivoractl.py (CLI), nivora_mcp.py, intelligence modules
web/         dependency-free dashboard served by the collector (also the /demo/ site)
native/      SwiftUI app, content-filter system extension, capture helper, widget, XCTest (project.yml)
site/        GitHub Pages landing page
scripts/     build, test, install, packaging and screenshot scripts
tests/       Python unit tests, web/demo tests and shared fixtures
docs/        architecture, API, install, capture, NetworkExtension, FluxVM, widgets, UX, testing
packaging/   draft Homebrew cask
```

## Documentation

| Doc | Topic |
| --- | --- |
| [docs/INSTALL.md](docs/INSTALL.md) | Install, Gatekeeper and unsigned builds |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components and data flow |
| [docs/API.md](docs/API.md) | HTTP endpoints, filter grammar, exports, MCP |
| [docs/CAPTURE.md](docs/CAPTURE.md) | Packet-capture design and guarantees |
| [docs/NETWORKEXTENSION.md](docs/NETWORKEXTENSION.md) | Content filter, signing and entitlements |
| [docs/FLUXVM.md](docs/FLUXVM.md) | FluxVM integration |
| [docs/WIDGETS.md](docs/WIDGETS.md) | Widget and Shortcuts |
| [docs/UX-CONTRACT.md](docs/UX-CONTRACT.md) | Design tokens and interaction rules |
| [docs/TESTING.md](docs/TESTING.md) | Test suite and release steps |
| [native/README.md](native/README.md) | Native app structure and build status |
| [CHANGELOG.md](CHANGELOG.md) | History |

## Contributing

1. Run the full gate before opening a pull request:

   ```bash
   ./scripts/test.sh
   ```

   It runs:
   - Python compile checks and the unit tests;
   - the web and demo tests;
   - the static-site build and check;
   - Swift syntax parsing (when `swiftc` is present);
   - plist/entitlement syntax checks;
   - a demo-collector snapshot check.

2. Build and test the native app:

   ```bash
   ./scripts/build-native.sh
   cd native && xcodebuild -project Nivora.xcodeproj -scheme NivoraTests \
     -destination 'platform=macOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO test
   ```

3. Follow these ground rules (from [CONTRIBUTING.md](CONTRIBUTING.md)):
   - Keep the collector Python-stdlib-only and the web dashboard dependency-free, unless there is a strong operational reason.
   - macOS-specific features must fail closed to observation-only when an entitlement or API is unavailable.
   - Keep observe-first behaviour as the default.
   - Do not add payload inspection, credential capture, argv/environment collection or a remote command channel.
   - Do not claim a NetworkExtension path is tested unless it was built and run on macOS.

4. Follow these native project rules:
   - `native/Nivora.xcodeproj` is generated from `native/project.yml` by `./scripts/generate-xcode.sh`. Do not hand-edit it.
   - Declare plist and entitlement keys in `project.yml`, not in the generated `Config/*` files.

5. Releasing is covered in [docs/TESTING.md](docs/TESTING.md#releasing). Pushing a `v*` tag that matches `package.json` builds an unsigned DMG with checksums and drafts a GitHub release.

## License

Nivora is licensed under the **Business Source License 1.1**.

You may use Nivora for development, evaluation, testing, demonstration and other non-production purposes under the terms of the BSL.

**Production and commercial deployments require a commercial license from Zyvor AI Labs Private Limited.**

Each version converts to the **Apache License 2.0** four years after its initial release under the Business Source License.

See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright © 2026 Zyvor AI Labs Private Limited · [zyvor.dev](https://zyvor.dev)
````

> Build note: `scripts/build-site-terminal.py` parses the `## Maturity` heading followed by a blank line and a two-column table, so that structure is preserved. Each row's status wording is chosen so its regex flags unverified areas correctly. The new Homebrew row uses "untested" for this reason, because "unverified" would not be flagged. The `#maturity` and `#privacy-and-safety` anchors are kept because `docs/INSTALL.md` and the app's Help menu link to them.

# Part 2: Docs gaps I could not fill

**Source files not provided**

- **Collector CLI and defaults.** `agent/nivora.py` was not shown. Still unknown:
  - the exact flag names for FluxVM URL/token (tests use `fluxvm_url` / `fluxvm_token` attributes) and `--allow-origin`;
  - default values for `--interval`, `--database` and `--rules`;
  - whether `--help` exists;
  - the default history database path. INSTALL.md implies `~/.local/share/nivora`, but this is not confirmed.
- **Native pane order and titles.** The `Pane` enum was not shown, so I could not say which pane each of `⌘1…⌘9` opens, or the exact `--section` titles beyond "Time Machine".
- **Situation profile storage.** The path of the profile file `ProfileStore` writes is not shown.
- **Makefile.** It was not provided. `make help/check/test/test-one/fixtures/app/widgets/stop/clean` are cited only from TESTING.md and WIDGETS.md.
- **Web dashboard behaviour.** `web/app.js` was not provided. What the Network Map, Domains and Insights views actually render is undocumented beyond nav labels.
- **Investigator.** `answer_query` was not shown, so the full set of supported questions is unclear.
- **`package.json`.** Not shown, so it is unclear whether Node dependencies exist, and what CI's Node is used for beyond the tests.

**Unverified or inconsistent behaviour**

- **`⌘F` shortcut.** It is listed in the shortcuts sheet, but no explicit binding is visible. It may come from `.searchable`.
- **Supported versions.**
  - Minimum Python version is undocumented (CI uses 3.13).
  - Required Xcode version is unclear: native/README says "Xcode 27", while CI uses the `macos-15` runner.
  - It is unclear whether the native app works with the stock `/usr/bin/python3` stub when Command Line Tools are not installed.
- **CPU architecture.** The Homebrew cask declares `arm64` only and the site says "Apple silicon". It is unclear whether self-built or Intel builds are supported.
- **macOS 14 vs 15 differences.** Only endpoint capture is documented (no local endpoint on 14, hostname only for remote). The user-visible impact is not described.
- **Entitlement name mismatch.** native/README says the entitlements declare `content-filter-provider`, but `project.yml` declares `content-filter-provider-systemextension`. One of them needs correcting.
- **MCP server version.** It reports itself as `0.1.0`, while the product is `0.5.1`. It is unclear whether this is intentional.
- **Homebrew tap.** It is unclear whether the `zyvorai/homebrew-tap` repository exists, and what the "Homebrew install line" on the site (per CHANGELOG) installs.
- **Tracker list extension.** The code comment says it can be extended "later". There is no documented way to extend it today.

**Missing procedures**

- **Signed build.** There is no end-to-end guide covering:
  - building with `DEVELOPMENT_TEAM`;
  - which provisioning profiles are needed;
  - approving the system extension;
  - enabling the filter from Security → "Enable NetworkExtension inspector";
  - verifying that it works.
- **Capture helper on a signed build.** There is no procedure for install and approval, or for diagnosing a `notFound` / `requiresApproval` status.
- **Fleet coordinator setup.** Fleet requires a non-loopback reachable coordinator, which conflicts with SECURITY.md's guidance to use an authenticated TLS proxy. No deployment recipe is given.
- **Full uninstall of the native app.** INSTALL.md omits the App Group container `~/Library/Group Containers/group.dev.zyvor.nivora`, which the cask's `zap` removes. It also omits the widget container and how to remove the filter configuration and system extension.

**Stale docs**

- TESTING.md says "29 Python tests".
- ARCHITECTURE.md, PRODUCT-REVIEW.md and FLUXVM.md refer to "Nivora 0.2".
- None reflect 0.5.x modules such as trust, privacy, policy, fleet, egress and MCP.

**Licensing details**

- The BUSL Change Date, Additional Use Grant and commercial-licence contact are in LICENSE/NOTICE, which were not provided. Only the summary was restated.

**Contributor and dev setup**

- Dev-only tools are required by `scripts/build-hero.py`, `build-tour.py` and `build-brand.sh`: Pillow, `rsvg-convert` (librsvg), `sips` and `iconutil`. They are not listed in any setup section.
- The Pages workflow runs on a self-hosted `[self-hosted, mini]` runner. Forks and contributors are not told how site deployment behaves for them.
