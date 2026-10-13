# Architecture

Nivora 0.2 separates collection, normalization, intelligence, storage and presentation while keeping the collector dependency-free.

## Collectors

1. **NetworkExtension flow reports** — preferred when the signed entitlement is active. New-flow decisions are pass-by-default unless a local block rule matches. Reports are metadata-only and are written as JSONL to the shared App Group.
2. **`nettop` fallback** — sampled cumulative app/process counters plus interface and RTT where macOS exposes them.
3. **`lsof`** — connection fallback and, independently, the source for listening TCP/UDP sockets.
4. **macOS network state** — `ifconfig`, `netstat`, `scutil --dns`, `scutil --nc list`, `networksetup`, `arp`, and `ndp`.
5. **FluxVM** — local REST probe using the current network-health/endpoints/Hubble/observe APIs plus optional direct telemetry.

## Normalized flow

```json
{
  "id":"stable-or-provider-id",
  "process":"Slack",
  "bundle_id":"com.tinyspeck.slackmacgap",
  "pid":602,
  "protocol":"tcp",
  "local":"192.168.1.42:53102",
  "remote":"13.107.6.175:443",
  "state":"ESTABLISHED",
  "bytes_in":98566144,
  "bytes_out":12582912,
  "rx_bps":125000.0,
  "tx_bps":18000.0,
  "total_bps":143000.0,
  "interface":"utun4",
  "rtt_ms":181.0,
  "source":"networkextension"
}
```

Rates are deltas between stable flow IDs over the real sample interval. Counter resets never produce negative throughput.

## Intelligence layer

- **Health** — weighted route, DNS, latency, interface and safety score from 0–100.
- **Diagnosis** — likely causes from missing route/DNS, high RTT, VPN-vs-direct latency and recent Time Machine changes.
- **Topology** — app → interface → destination nodes and weighted edges.
- **Behavior** — SQLite-learned app/destination/port tuples. The initial sample seeds the baseline; later first-seen destinations become events/findings.
- **Exposure** — listeners classified as loopback, local-address or all-interface binds.

## Storage

`HistoryStore` uses SQLite WAL mode, local permissions `0600`, 30-day snapshot retention, a bounded 5,000-event journal and a 90-day behavior table. `/v1/series` reads compact throughput/health history from the same database.

## Safety

Rules are inert in collector-only mode. Block rules default to a one-hour lease. The signed `NEFilterDataProvider` is the only component that can return a drop verdict. Payload capture and cloud telemetry are not implemented.
