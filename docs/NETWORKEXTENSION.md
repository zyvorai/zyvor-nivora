# NetworkExtension integration

Nivora uses Apple's content-filter APIs rather than attempting to port Linux eBPF to macOS.

## Flow

1. `FilterDataProvider.handleNewFlow` receives an `NEFilterFlow`.
2. Nivora records app/endpoint metadata and returns allow by default, or drop if a local block rule matches.
3. `verdict.shouldReport = true` requests a report.
4. `FilterControlProvider.handle(_:)` receives `NEFilterReport` events and cumulative byte counts.
5. Reports are appended to the `group.dev.zyvor.nivora` App Group as `flows.jsonl`.
6. The local collector keeps the latest report per flow and publishes it through the same REST API as fallback telemetry.

Apple's APIs expose source-app identifiers/audit tokens on filter flows and inbound/outbound byte counts on filter reports. The current code intentionally collects metadata, not payloads.

## Provisioning

The source tree declares the `content-filter-provider` Network Extension entitlement. Actual shipping requires Apple's entitlement approval and a matching provisioning profile/signing identity. Developer ID distribution requirements can differ from App Store provisioning; use the entitlement values present in the profile Apple grants to the team.

The app works in collector fallback mode without this entitlement.

## Rule safety in 0.2

The extension reads the same App Group `rules.json` used by the collector. Expired rules are ignored. New block rules created through the 0.2 API receive a one-hour expiry by default; an operator must explicitly request a longer lease or a permanent block. This keeps the product observe-first even when enforcement is enabled.

The portable build can syntax-check these sources, but only a correctly provisioned Mac can prove entitlement activation, real flow attribution, report cadence, and drop behavior. Do not market those paths as hardware-verified until that run is completed.
