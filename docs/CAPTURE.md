# Packet capture

Capture is an **opt-in, per-session** feature. Everything else in Nivora stays payload-free.

## Guarantees

- Off by default; every capture needs an explicit confirmation (`"confirm": true` on the API, a checkbox in the UI).
- **Headers only by default**: snaplen 96 bytes (allowed 54–256).
- Hard caps enforced by the helper itself: ≤ 300 s, ≤ 64 MB (default 16 MB), one capture at a time.
- Captures live in `/Library/Application Support/Nivora/captures/` (root, `0700`; files `0600`) and are deleted after 24 h.
- Every start/stop/delete is written to the Time Machine as a `capture` event.

## Architecture

```text
web / native UI ──HTTP──▶ nivora.py ──unix socket──▶ dev.zyvor.nivora.capture-helper (root, launchd)
                          capture.py                     └─▶ /usr/sbin/tcpdump (fixed argv, no shell)
```

- The helper is registered with `SMAppService.daemon` (`App/CaptureHelperManager.swift`); macOS asks the user to approve it in **System Settings › Login Items**.
- Wire protocol: JSON lines on `/var/run/dev.zyvor.nivora.capture.sock` (`status`, `start`, `list`, `stop`, `delete`, `fetch`). The socket is connectable by anyone, but each connection is authorised with `getpeereid`: only root or the console user.
- **No free-form BPF.** Requests carry structured fields (interface, literal IP, protocol, port, snaplen, seconds, size). `CaptureValidator` (Swift, authoritative) and `validate_request` (Python, first line of defence) build a closed token list; interface names must exist on the Mac. Hostnames are rejected.
- `argv` is `["-n","-p","-i",iface,"-s",snaplen,"-w",path] + tokens`: non-promiscuous, no name resolution.

## API

```text
GET    /v1/captures                 availability, limits, sessions
POST   /v1/captures                 {iface, host?, port?, proto?, snaplen?, seconds?, max_mb?, confirm:true}
POST   /v1/captures/{id}/stop
GET    /v1/captures/{id}/pcap       application/vnd.tcpdump.pcap attachment
DELETE /v1/captures/{id}
```

Without the helper, `POST` returns `501` with the equivalent manual `sudo tcpdump …` command. Demo mode simulates sessions and serves a synthetic, valid pcap.

## What is and is not verified

Verified in this repo: the helper and app **compile**; Swift/Python validator unit tests (including injection attempts and limit parity); the client against a fake helper socket; the real helper binary answering the protocol and rejecting bad input when run unprivileged; the demo flow in the web UI.

**Not verified:** signing, `SMAppService` registration/approval, running `tcpdump` as root, BPF permission, file-ownership/permissions as root, and `getpeereid` behaviour under a real launchd install. These need a provisioned, signed build on a Mac.
