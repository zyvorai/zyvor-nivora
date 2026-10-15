# Widget and Shortcuts

Nivora ships a read-only WidgetKit widget and two App Intents. They show only what the app has already measured.

## Widget

**Network** (small and medium): a health ring and live ↓/↑ rates; the medium size adds the three busiest apps and a finding count. It says "Simulated" for demo data and "Nivora is not running" with the age of the reading when the app has not published for two minutes, so it never shows an old number as current. With no reading yet it says to open Nivora.

Add it from Edit Widgets on the desktop or in Notification Center, under Nivora.

## Shortcuts and Siri

| Intent | Says |
| --- | --- |
| **How is my network?** | `Network health is 92 out of 100. Downloading 1.8 MB/s, uploading 90 KB/s. Google Chrome is the busiest app.` |
| **Block an app for one hour** | Asks for confirmation, then adds a leased block rule. It is only enforced with the NetworkExtension. |

Both run inside the app process and use the bundled loopback collector.

## How the data flows

The app writes `widget.json` (health, rates, counts and the five busiest apps' names and rates; no tokens, no process IDs, paths or addresses) about every five seconds and asks WidgetKit to reload at most every 30 seconds. The extension is sandboxed, so it reads from its own container, `~/Library/Containers/dev.zyvor.nivora.widgets/`. The app is not sandboxed, so it writes there directly, and only once that container exists (the first time macOS runs the widget); it never creates it.

An App Group would be the conventional channel but needs a Developer team identity. With a signing team, `WidgetStore` (`native/Shared/WidgetData.swift`) is the single place to change.

## Building

```bash
make widgets            # or ./scripts/build-native-widgets.sh (needs xcodegen)
```

This builds `native/widgets.yml`: the app plus the extension, ad-hoc signed. It leaves out the content-filter system extension and the capture helper, because their restricted entitlements cannot be satisfied by ad-hoc signing. `scripts/build-native.sh` and `project.yml` remain the plain and the full signed builds.

## What is and is not verified

Verified: the build embeds a sandboxed extension that passes `codesign --verify --deep --strict`; its extension point is `com.apple.widgetkit-extension`; the data model, staleness and the "no container yet" behaviour are covered by `WidgetDataTests`.

Not verified: the widget in the widget gallery or on the desktop, that macOS registers and runs the extension, that the app's file lands in the widget container on a real install, and the Shortcuts and Siri phrases.
