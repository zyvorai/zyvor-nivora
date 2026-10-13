# Native macOS app

Nivora's native app is SwiftUI. The signed NetworkExtension path is a content-filter **system extension** whose `NEFilterDataProvider` makes new-flow decisions and receives byte-count reports (macOS has no control provider). It shares flow metadata with the app/collector through the `group.dev.zyvor.nivora` App Group.

Generate the Xcode project with `../scripts/generate-xcode.sh`, then open `Nivora.xcodeproj`. The project file is generated from `project.yml`; do not hand-edit it.

## Signing requirement

Apple NetworkExtension entitlements must be enabled for the signing team/profile. The checked-in entitlements declare `content-filter-provider`. Developer ID distribution may require a provisioning profile whose entitlement value matches Apple's current Network Extension distribution rules. The build script validates that a team is supplied but it cannot obtain Apple approval for you.

Without the entitlement, the application still works through the local collector (`nettop` first, `lsof` fallback), but per-app byte accounting and optional filter rules are less precise.

## Native app structure

The SwiftUI app follows Zyvor Vytrix's native layout, coloured with the Netra palette (`App/Views/Theme.swift`, kept equal to the web tokens by `tests/test_native_contract.py`):

```text
App/NivoraApp.swift           window + menu-bar scenes, --demo / --appearance / --section launch flags
App/Model/                    NivoraStore (polling, history, rules), Snapshot, Preferences, Alerts, CollectorProcess
App/Views/                    RootView, Overview, Health, Applications (+ detail sheet), Flows, Interfaces,
                              LocalNetwork, FluxVM, Security, Investigator, Alerts, Settings, MenuBar,
                              Components (Panel, MetricTile, Meter, Monogram), Theme (Palette)
```

Closing the window keeps Nivora and its collector running in the menu bar; Quit stops both.

## Build status (be precise)

- `../scripts/build-native.sh` builds `Nivora.app` with the embedded `dev.zyvor.nivora.filter.systemextension` on Xcode 27 (Swift 6 mode, unsigned, `CODE_SIGNING_ALLOWED=NO`). The `App/` target also runs against the bundled collector in `--demo` mode.
- **Not verified:** signing, entitlement approval, system-extension activation, flow attribution, byte-report cadence and drop enforcement. These need a Mac with an Apple Developer team that has the Network Extension entitlement (see `../docs/NETWORKEXTENSION.md`).
- `xcodegen` regenerates `Config/*.plist` and `Config/*.entitlements` from `project.yml`; declare plist/entitlement keys there.
