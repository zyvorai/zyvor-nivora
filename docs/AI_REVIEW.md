# AI code review (zyvor-nivora)

_Generated 2026-10-20 by claude-opus-5-5 from a snapshot of tracked sources; verify before acting._

# Code review: zyvor-nivora

## Summary

Zyvor Nivora is a macOS-only, local-first network observability product. It has three parts:

- **Collector:** a stdlib-only Python collector (`agent/`) that serves a bearer-token REST API and a dependency-free web dashboard on loopback.
- **Native app:** a SwiftUI app that bundles and launches the collector.
- **Optional privileged components:** a content-filter system extension (`NEFilterDataProvider`), a root `tcpdump` capture helper and a WidgetKit widget.

Its default posture is observe-first. Block rules are short leases, and they are only enforced by the signed extension, which is compile-verified only.

## Bugs and correctness risks

**`scripts/install-macos.sh`: the generated `run-collector.sh` is broken (high confidence)**
- The heredoc is unquoted (`<<EOF`). Inside an unquoted heredoc, `\"` is written literally as `\"`.
- The generated script therefore contains `TOKEN=\"$(security ... -a \"$USER\" -w)\"` and `exec ... \"/Users/x/Library/Application Support/Nivora/agent/nivora.py\" --port \"9857\"`.
- At runtime the quotes become literal characters:
  - `security` is asked for the account `"user"` (with quotes), fails, and `set -e` aborts the script.
  - The path is split at the space in "Application Support".
  - `--port` receives `"9857"`, which is not an integer.
- Because the plist sets `KeepAlive`, launchd will respawn the failing script in a loop. The per-user service path appears to never work.

**`native/FilterData/FilterDataProvider.swift`: rule matching**
- **Leases may never expire.** `ISO8601DateFormatter()` with default options does not parse fractional seconds. Python's `isoformat()` emits microseconds unless they are stripped. I can't see `RuleStore`, so this is unconfirmed.
  - If parsing fails, `date` is `nil` and the rule is treated as still active. A "1-hour" block would then be permanent.
  - Safer behaviour: treat an unparseable expiry as expired.
- **Matching is substring-based and over-broad:**
  - `remote.contains(ip)`: `1.2.3.4` also matches `11.2.3.45:443`.
  - `remote.contains(d)` for domains: `a.co` also matches `a.com`.
  - `localizedCaseInsensitiveContains(a)` for apps: blocking "Mail" also blocks "MailMate".
  - A "Block app for 1 h" button (`AppDetailSheet`, `FlowDetailSheet`, `BlockAppIntent`) can therefore drop unrelated traffic.
- **Schema drift fails open silently.** Rules are decoded as `[FilterRule]` with `port: Int?`. If `rules.json` is a wrapper object, or any field has a different type, decoding fails and the stale `cached` rules are used. Because `mtime` is advanced before the decode, the file is not retried until it changes again.
- **The App Group may not be shared.** System extensions run as root, so `containerURL(forSecurityApplicationGroupIdentifier:)` may resolve under root's home. The user-run collector reads the user's `~/Library/Group Containers`.
