<div align="center">

# Nivora

### See every connection on your Mac.

**Mac-native application and network intelligence for apps, processes, DNS, routes, VPNs, interfaces, FluxVM VMs and sandboxes.** Nivora uses Apple's NetworkExtension APIs when the signed entitlement is available, with a dependency-free `nettop`/`lsof` collector fallback that works immediately.

**macOS only** · **Local-first** · **Live per-app bandwidth** · **0–100 health score** · **Network Map** · **Behavior learning** · **FluxVM aware**

</div>

## Why Nivora

Nivora fills the per-application networking gap between a system monitor and a datacenter network observability platform. It answers questions such as:

- Which application is uploading or downloading the most?
- Which process is using a port?
- Where is an application connecting, and over Wi-Fi, VPN, or a virtual interface?
- Did DNS, the default route, a VPN, or an interface change when connectivity broke?
- What traffic belongs to FluxVM processes, VMs, and sandboxes?
- Which outbound destinations or ports look unusual?

The UI deliberately follows the same macOS-oriented visual language as Zyvor Vytrix: grouped application views, compact cards and tables, light/dark glass surfaces, a local-first collector and deterministic demo telemetry.

## Dashboard UX (unreleased)

Command palette (`⌘K`), keyboard shortcuts (`?`), click-through application sheet, sortable tables, throughput chart, toasts, Settings (theme/accent/density/refresh/alerts/pinned apps) and local JSON/CSV export. See `docs/UX-CONTRACT.md`.

The web dashboard and native app share the Netra palette and type scale; the native app follows Vytrix's structure. The native `App/` sources build with Xcode, but the NetworkExtension targets still need porting to macOS APIs before a full signed build (see `native/README.md`).

## What’s new in 0.2

- **Live bandwidth**, not only cumulative counters: per-flow and per-app RX/TX rates derived from consecutive samples.
- **Network Health 0–100** with route, DNS, latency, active-interface and safety components.
- **Network Map** joining apps → interfaces → top destinations.
- **Behavior learning** persisted in SQLite; destinations first seen after the baseline become Time Machine events and security findings.
- **Local Network** inventory from ARP/NDP plus listening services and bind exposure.
- **Safer blocking**: block rules default to a one-hour lease unless explicitly made permanent.
- **Deeper FluxVM context** from current `/v1/network/health`, `/v1/network/endpoints`, `/v1/network/hubble/flows` and `/v1/network/observe` APIs, with the richer telemetry contract still accepted when available.
- Hardened local HTTP serving, bounded history-series endpoint, richer local diagnosis and expanded CLI.

## Architecture

```text
                         Nivora.app / Browser
                                 |
                           HTTP JSON API
                                 |
                             nivora.py
                          local collector
                _____________|________________
               /             |                \
      NetworkExtension     macOS tools       FluxVM
       filter reports     nettop/lsof        :7788
          |                ifconfig            |
          |                netstat          VMs/sandboxes
          |                scutil               |
          +---------> SQLite time machine <----+
```

### Visibility tiers

**Tier 1 — signed NetworkExtension.** `NEFilterDataProvider` sees new app flows, sets `shouldReport`, and the control provider receives flow reports including inbound/outbound byte counts. Nivora writes metadata only into its App Group and never exports packet payloads.

**Tier 2 — collector fallback.** On a Mac without the entitlement, `nettop` provides app/process byte counters where available, and `lsof` supplies socket endpoints as a fallback. `ifconfig`, `netstat`, `scutil`, `networksetup`, `arp`, and `ndp` provide interface, Wi‑Fi, route, DNS, VPN and local-neighbor state. `lsof` is always sampled for listening services even when another flow source wins.

The dashboard and API use one schema regardless of tier.

## Features

### Applications

- Grouped per-app network activity
- TCP/UDP flow inventory
- Received/sent counters
- Destination and interface rollups
- Bundle ID when reported by NetworkExtension
- Search by app, endpoint, IP, host or port

### Network

- Wi-Fi/Ethernet/loopback/bridge/virtual/`utun` inventory
- IPv4 and IPv6 addresses
- Default routes and gateways
- DNS resolver inventory and scoped VPN resolvers
- Configured/active VPN services
- RTT from `nettop` where macOS exposes it

### Live health and topology

- Per-flow and per-app RX/TX bytes per second
- 0–100 health score with explainable components
- Local diagnosis for route, DNS, latency, VPN path and recent configuration changes
- App → interface → destination topology
- Compact history series for throughput/health charts

### Local Network

- ARP + IPv6 NDP neighbor cache
- Listening TCP/UDP services
- Loopback/local/all-interface exposure classification
- Hardware-port enrichment (Wi‑Fi, Ethernet, Thunderbolt) and current Wi‑Fi SSID where `networksetup` exposes it

### Network Time Machine

- Interface appeared/disappeared/status changes
- DNS resolver changes
- Default-route changes
- SQLite snapshot history, 30-day retention
- Local event journal capped to 5,000 events
- VPN state, new listener and traffic-spike events
- Persistent app/destination behavior baseline with “new destination” events

### Security

- Observe-first findings
- Unusual outbound port finding
- High-volume outbound finding
- Rule preview against live flows
- Block rules are lease-bounded to one hour by default
- Observe / allow / block rule model
- Signed NetworkExtension can apply `block` rules by app, domain, IP or port
- Rules can expire automatically

### FluxVM

Nivora probes FluxVM on `http://127.0.0.1:7788` by default, matching the current `fluxctl serve` default. It reads:

- `/healthz`
- `/v1/vms`
- `/v1/sandboxes`
- `/v1/network/health`
- `/v1/network/endpoints`
- `/v1/network/hubble/flows`
- `/v1/network/observe`
- optional `/v1/network/telemetry` for the richer direct-attribution contract

Set `FLUXVM_SERVER` and `FLUXVM_TOKEN` to override.

### Local investigator

The initial investigator is deterministic and offline. Examples:

```text
Which app uploaded the most?
What uses port 443?
Is my VPN active?
Which DNS resolvers are active?
Why is the network slow?
Show FluxVM.
Anything suspicious?
```

No cloud model or API key is required.

## Quick start

### Demo anywhere

```bash
python3 agent/nivora.py --demo
```

Open the URL printed by the collector. The token is placed in the URL fragment, read by the page, and removed from the address bar; it is not stored in local storage.

### Live on macOS

```bash
python3 agent/nivora.py
```

The collector binds to `127.0.0.1:9857`, generates a bearer token and serves both the dashboard and API.

One snapshot:

```bash
python3 agent/nivora.py --once > snapshot.json
```

Install it as a per-user `launchd` service with the token in Login Keychain:

```bash
./scripts/install-macos.sh
```

Remove it:

```bash
./scripts/uninstall-macos.sh
```

## CLI

```bash
python3 agent/nivoractl.py status
python3 agent/nivoractl.py health
python3 agent/nivoractl.py traffic
python3 agent/nivoractl.py apps
python3 agent/nivoractl.py flows
python3 agent/nivoractl.py topology
python3 agent/nivoractl.py neighbors
python3 agent/nivoractl.py listeners
python3 agent/nivoractl.py behavior
python3 agent/nivoractl.py diagnose
python3 agent/nivoractl.py fluxvm
python3 agent/nivoractl.py ask why is Slack slow
python3 agent/nivoractl.py rule-add --action block --domain example.com --duration 900
python3 agent/nivoractl.py rule-add --action allow --app Safari --domain example.com
python3 agent/nivoractl.py rules
```

`nivoractl` reads `NIVORA_TOKEN`; on macOS it also looks for the token stored by `install-macos.sh` in Login Keychain.

## Native Mac app

The SwiftUI app starts the bundled collector on loopback with a random in-memory token and displays the same data contract natively.

```bash
brew install xcodegen
./scripts/build-native.sh
open native/build/Build/Products/Release/Nivora.app
```

Run the native app with simulated data:

```bash
open native/build/Build/Products/Release/Nivora.app --args --demo
```

NetworkExtension activation requires Apple provisioning/entitlements for the signing team. See `docs/NETWORKEXTENSION.md`.

## API

Default endpoint: `http://127.0.0.1:9857`.

```text
GET    /healthz
GET    /v1/snapshot
GET    /v1/apps
GET    /v1/flows
GET    /v1/interfaces
GET    /v1/routes
GET    /v1/dns
GET    /v1/vpn
GET    /v1/fluxvm
GET    /v1/findings
GET    /v1/health
GET    /v1/traffic
GET    /v1/topology
GET    /v1/neighbors
GET    /v1/listeners
GET    /v1/behavior
GET    /v1/diagnose
GET    /v1/series?limit=120
GET    /v1/timeline
GET    /v1/history?limit=120
GET    /v1/rules
POST   /v1/query
POST   /v1/rules
DELETE /v1/rules/{id}
```

Every `/v1/*` endpoint requires `Authorization: Bearer <token>` when a token is configured. `/healthz` and static dashboard assets are public on the local listener.

See `docs/API.md`.

## Test

```bash
./scripts/test.sh
```

The portable suite currently covers 28 Python tests plus web, plist, demo and Swift syntax gates: collectors, rate calculation, local-network parsers, behavior learning, health/topology/diagnosis, rule leases, Time Machine, SQLite history, API authentication/CORS/intelligence endpoints, and native/web contracts.

The native NetworkExtension targets require Xcode/macOS for type-check/build verification. CI includes a macOS job that generates the Xcode project and performs an unsigned build.

## Repository layout

```text
agent/                 collector, core, CLI
web/                   dependency-free Vytrix-style dashboard
native/App/            SwiftUI shell
native/FilterData/     NEFilterDataProvider
native/FilterControl/  NEFilterControlProvider
native/Shared/         app-group flow contract
docs/                  architecture, API, Apple signing, FluxVM
scripts/               test, install, Xcode build/package
```

## Privacy and safety

- Local-first; no telemetry upload is implemented.
- Payload collection is not implemented.
- The fallback collector executes read-only macOS commands.
- Rules default to observe-only.
- NetworkExtension filtering requires explicit enablement in the native app and valid Apple provisioning.
- API mutations are limited to Nivora's local rule file.

## License

Business Source License 1.1, matching Vytrix's commercial model. Production/commercial use beyond the license grant requires a Zyvor commercial agreement. See `LICENSE`.
