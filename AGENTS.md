# Agent instructions

- Product scope: macOS application/network intelligence, not a Linux Netra port.
- Prefer Apple NetworkExtension for signed per-app flow reporting; use `nettop`/`lsof` only as fallback.
- Keep the collector Python stdlib-only.
- Keep the web UI dependency-free and visually consistent with Vytrix/macOS.
- Never claim a NetworkExtension build was tested unless it was built on macOS/Xcode.
- Keep observe-first behavior as the default.
- FluxVM default API is `http://127.0.0.1:7788`; support `FLUXVM_SERVER`/`FLUXVM_TOKEN` overrides.
- Run `./scripts/test.sh` after changes.
