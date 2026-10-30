# Installing Nivora

**Paid builds (business use, ₹999 incl. GST).** After payment you receive an email with a GST invoice and a download link
(valid 7 days, 5 downloads). Verify the download against the `.sha256` shown on the payment page or sent on request.

- **Signed and notarized build** (`Nivora-X.Y.Z.dmg`): open the DMG and drag **Nivora** to **Applications**. macOS opens it
  without a warning. It does not include the content filter or the capture helper.
- **Developer build** (`Nivora-X.Y.Z-developer.dmg`): unsigned, so the sections below apply. It includes the content-filter
  and capture-helper code; to activate them you must sign the app yourself with your own Developer ID and a provisioning
  profile that carries the NetworkExtension entitlement. Those parts are compile-verified only.

The rest of this page covers the **free** builds (personal, non-business use), which are not signed or notarised.

Nivora **release builds are not signed with an Apple Developer ID and are not notarised**. macOS Gatekeeper
will refuse to open a downloaded copy the first time and show a message such as:

- *"Nivora" cannot be opened because the developer cannot be verified.*
- *"Nivora" can't be opened because Apple cannot check it for malicious software.*
- *"Nivora" is damaged and can't be opened. You should move it to the Trash.* (a quarantined, unsigned download)

This is expected, not a sign of corruption. It happens because signing and notarisation need an Apple
Developer ID and, for the content filter, an Apple-approved NetworkExtension entitlement. See
[Maturity](../README.md#maturity) for what is and is not verified.

## Option 1: build it yourself (recommended)

An app you build on your own Mac is never quarantined, so Gatekeeper does not interrupt it.

```bash
brew install xcodegen                 # once; Xcode must also be installed
./scripts/build-native.sh
ditto native/build/Build/Products/Release/Nivora.app /Applications/Nivora.app
open /Applications/Nivora.app
```

Optional: give your local copy an ad-hoc signature so macOS treats the bundle as intact:
`codesign --force --deep -s - /Applications/Nivora.app`.

## Option 2: install the downloaded DMG

1. Download `Nivora-X.Y.Z.dmg` and `SHA256SUMS.txt` from [Releases](https://github.com/zyvorai/zyvor-nivora/releases).
2. Verify the download: `shasum -a 256 -c SHA256SUMS.txt` (run it in the folder with both files).
3. Open the DMG and drag **Nivora** to **Applications**.
4. Open Nivora once. If macOS blocks it, use **one** of the following:

**macOS 15 (Sequoia) and later**

1. Try to open Nivora, then dismiss the warning.
2. Open **System Settings → Privacy & Security**.
3. Scroll to **Security**, find *"Nivora" was blocked to protect your Mac* and click **Open Anyway**.
4. Authenticate, then click **Open** in the confirmation. macOS remembers the choice.

**macOS 14 (Sonoma)**

Control-click (right-click) **Nivora** in Applications → **Open** → **Open**. macOS remembers the choice.

**Any version, from Terminal** (removes the quarantine flag from your copy):

```bash
xattr -dr com.apple.quarantine /Applications/Nivora.app
open /Applications/Nivora.app
```

Only do this for a copy whose checksum you verified against the release's `SHA256SUMS.txt`.

## Option 3: no app at all

The collector and dashboard need only Python 3 and nothing from Apple's signing chain:

```bash
python3 agent/nivora.py            # dashboard + API on 127.0.0.1:9857
python3 agent/nivora.py --demo     # simulated data
```

## What an unsigned install can and cannot do

| Works | Needs a signed, provisioned build |
| --- | --- |
| Per-app flows and byte counters via `nettop`/`lsof` | Content-filter system extension (per-flow app attribution from the system) |
| Interfaces, DNS, routes, VPNs, neighbours, listeners | Capture helper (root `tcpdump`, approved in System Settings) |
| Time Machine history, health, exports, filters, menu-bar | Blocking rules taking effect |

Nivora runs in observe-first mode on an unsigned install. Closing its window keeps it in the menu bar; **Quit**
is in the menu-bar menu. The welcome sheet appears once on first launch.

## Uninstall

```bash
pkill -x Nivora
rm -rf /Applications/Nivora.app
rm -rf ~/.local/share/nivora          # history; optional
./scripts/uninstall-macos.sh          # only if you installed the launchd agent
```
