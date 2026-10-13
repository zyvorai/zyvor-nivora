# NetworkExtension integration

Nivora uses Apple's content-filter APIs rather than attempting to port Linux eBPF to macOS.

## Flow

On macOS a content filter is a **system extension** (`dev.zyvor.nivora.filter.systemextension`, embedded in `Nivora.app/Contents/Library/SystemExtensions`). There is no `NEFilterControlProvider` on macOS; the single `NEFilterDataProvider` both decides and receives reports.

1. `FilterDataProvider.handleNewFlow` receives an `NEFilterFlow`.
2. Nivora resolves the owning app from `sourceAppAuditToken` (pid → `proc_pidpath` → enclosing `.app` bundle id), records app/endpoint metadata and returns allow by default, or drop if a local block rule matches.
3. `verdict.shouldReport = true` requests a report and `statisticsReportFrequency = .medium` asks for ~1 s byte-count statistics.
4. `FilterDataProvider.handle(_:)` receives `NEFilterReport` events and cumulative byte counts.
5. Reports are appended to the `group.dev.zyvor.nivora` App Group as `flows.jsonl`.
6. The local collector keeps the latest report per flow and publishes it through the same REST API as fallback telemetry.

Apple's APIs expose source-app audit tokens on filter flows and inbound/outbound byte counts on filter reports. Remote/local endpoints use `remoteFlowEndpoint`/`localFlowEndpoint` on macOS 15+; on macOS 14 only `remoteHostname` is available. The current code intentionally collects metadata, not payloads.

## Provisioning

`native/project.yml` declares the `content-filter-provider-systemextension` Network Extension entitlement and `com.apple.developer.system-extension.install` for the app (XcodeGen regenerates `Config/*.plist` and `*.entitlements` from it, so edit `project.yml`, not the generated files). Actual shipping requires Apple's entitlement approval and a matching provisioning profile/signing identity. Developer ID distribution requirements can differ from App Store provisioning; use the entitlement values present in the profile Apple grants to the team.

The app works in collector fallback mode without this entitlement.

## Rule safety in 0.2

The extension reads the same App Group `rules.json` used by the collector. Expired rules are ignored. New block rules created through the 0.2 API receive a one-hour expiry by default; an operator must explicitly request a longer lease or a permanent block. This keeps the product observe-first even when enforcement is enabled.

The extension and app **compile and link** with Xcode on macOS (unsigned build). Only a correctly provisioned Mac can prove entitlement activation, real flow attribution, report cadence, and drop behavior. Do not market those paths as hardware-verified until that run is completed.
