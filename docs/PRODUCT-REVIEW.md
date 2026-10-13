# Nivora product review — 0.2

## Problems found in 0.1

1. Cumulative bytes looked like activity but did not answer “what is using bandwidth **now**?”
2. Health was a list of findings, not a single explainable state.
3. Time Machine knew route/DNS/interface changes but did not learn app behavior.
4. The product did not show local neighbors or listening-service exposure.
5. FluxVM probing stopped short of network APIs that already exist in FluxVM.
6. A block rule could accidentally be created without an expiry.
7. The API had a path-prefix static-file check and non-constant-time bearer comparison that were worth hardening.
8. Native and web experiences did not surface a unified health/live-throughput model.

## 0.2 changes

- Live per-flow/per-app bandwidth deltas.
- 0–100 health score and diagnosis engine.
- Network Map.
- ARP/NDP local network and listening services.
- Wi-Fi/hardware-port enrichment.
- Persistent destination baseline and first-seen alerts.
- VPN/listener/traffic-spike Time Machine events.
- Lease-bounded blocking (one hour by default).
- Current FluxVM network-health/endpoints/Hubble/observe integration.
- Compact history series for charts.
- New API + CLI surfaces for health, traffic, topology, local network, behavior and diagnosis.
- Native macOS health/local-network screens and live menu-bar rates.
- HTTP/static-serving hardening.

## Highest-value next milestones

These intentionally remain future work because they require real Mac hardware/provisioning rather than portable simulation:

1. Sign, activate and endurance-test the NetworkExtension on macOS 26/27.
2. Measure app attribution across QUIC/HTTP3, VPNs, Private Relay and multiple user sessions.
3. Resolve audit tokens to verified process path/signing identity/team ID in the extension or privileged helper.
4. Add optional packet metadata capture only if it can preserve the current payload-free privacy promise.
5. Validate FluxVM direct VM/sandbox attribution on real `vz`, vmnet and usernet paths.
6. Add multi-Mac Nivora Fleet only after single-Mac telemetry semantics are stable.
