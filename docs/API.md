# API

All `/v1/*` requests use `Authorization: Bearer $NIVORA_TOKEN` when a token is configured. The local server uses constant-time bearer comparison, rejects unapproved browser origins, serves no-store JSON, and adds basic browser hardening headers.

## Complete snapshot

`GET /v1/snapshot` returns the normalized Mac network state: host, apps, flows, live rates, interfaces, routes, DNS, VPN, Wi-Fi, neighbors, listeners, health, topology, findings, learned behavior, FluxVM context, rules and rule hits.

## Focused reads

- `GET /v1/apps`
- `GET /v1/flows[?filter=<query>]` — optional server-side filter, see *Filter grammar*
- `GET /v1/interfaces`
- `GET /v1/routes`
- `GET /v1/dns`
- `GET /v1/vpn`
- `GET /v1/fluxvm`
- `GET /v1/findings`
- `GET /v1/health`
- `GET /v1/traffic`
- `GET /v1/topology`
- `GET /v1/neighbors`
- `GET /v1/listeners`
- `GET /v1/containers` (container runtime traffic summary)
- `GET /v1/port-conflicts` (ports bound by multiple processes)
- `GET /v1/flows/{id}/explain` — evidence for one flow: app, destination, path, traffic share, new-destination status, matching rules and related findings, plus plain-language `reasons`
- `GET /metrics` — Prometheus text exposition (health, flows, rates, findings by severity, listeners, port conflicts, top apps); same token as the API
- `GET /v1/usage` — today's bytes per app and budget status; budgets live in `budgets.json` beside the history database, `{"app name substring": bytes_per_day}`
- `GET /v1/projects` — traffic grouped by project folder (nearest ancestor of the process working directory holding `.git`, `package.json`, etc., inside the home directory); flows carry `project`
- `GET /v1/diff?from=&to=` — what differs between the stored snapshots at two times (ISO 8601; default last 30 min, max 30 days): health delta, flow groups added/removed, app rate movers, listeners, DNS servers, default route, devices, new findings. Needs history enabled
- `GET /v1/incident?from=&to=` — the same window as an ordered narrative (events, route/traffic changes, new findings) with a one-line headline
- `POST /v1/path-check` `{"host":"example.com","port":443}` — on-demand DNS → TCP → TLS reachability check with timings; the only active probe, runs only when asked, one at a time
- `GET /v1/rule-impact` — per rule: matched flows, apps, bytes and rate, and whether it is enforced
- `GET /v1/behavior`
- `GET /v1/diagnose`
- `GET /v1/timeline`
- `GET /v1/history?limit=120`
- `GET /v1/series?limit=120` — compact timestamp/RX/TX/health/flow/app history
- `GET /v1/rules`

## Investigator

`POST /v1/query`

```json
{"question":"why is the network slow?"}
```

The local deterministic investigator can answer about live upload/download, ports/listeners, health, recent changes, DNS, VPN, new destinations, local neighbors, apps and FluxVM. It returns an answer plus supporting local evidence.

## Rules

`POST /v1/rules`

```json
{"action":"block","domain":"example.com"}
```

A rule needs at least one of `app`, `domain`, `ip`, or `port`. `action` is `observe`, `allow`, `block`, or `shadow`. A `shadow` rule counts what it would block (see `/v1/rule-impact`) and is never enforced, so it needs no lease; use it to preview a block before enabling it.

**Safety:** a block rule without `expires_at` is automatically leased for 3600 seconds. Supply `duration_seconds` to choose 60 seconds through 7 days, or `permanent: true` to intentionally create a non-expiring block.

```json
{"action":"block","app":"com.example.App","duration_seconds":900}
```

`DELETE /v1/rules/{id}` removes one rule.

Collector-only deployments preview matches but do not alter traffic. Signed NetworkExtension deployments can enforce active `block` rules.

## Captures

See `docs/CAPTURE.md`: `GET/POST /v1/captures`, `POST /v1/captures/{id}/stop`, `GET /v1/captures/{id}/pcap`, `DELETE /v1/captures/{id}`. Capture requires `confirm: true`, is headers-only by default and returns `501` plus a manual command when the helper is missing.

## Export

`GET /v1/export?kind=flows|apps|timeline|snapshot|bundle&format=csv|json|ndjson|zip[&filter=<query>][&redact=1]`

Returns an attachment (`Content-Disposition`). `bundle`/`zip` contains `README.txt`, `snapshot.json`, `flows.csv` and `timeline.ndjson`. CSV cells that start with `= + - @` are prefixed with `'` so spreadsheets do not evaluate them. `redact=1` replaces private IPv4/link-local IPv6 addresses, MACs, SSIDs, DNS names/search domains and this Mac's hostname with per-export salted hash tokens (`ip-1a2b3c4d`); the same value maps to the same token within one export only. Exports never contain packet payloads. Unknown kind/format returns `400`.

## Filter grammar

One grammar is shared by the collector (`parse_filter`/`match_flow` in `agent/nivora_core.py`), the web UI (`parseFilter`/`matchFilter` in `web/lib.js`) and the native app (`FlowFilter` in `native/App/Model/Filter.swift`). Parity is enforced by `tests/fixtures/filter-vectors.json`.

| Token | Meaning |
|---|---|
| `app:Safari` | process name or bundle id contains the value (alias `process:`) |
| `host:example.com` | remote host contains the value |
| `port:443`, `port:8000-9000` | local or remote port equals / is within range |
| `proto:tcp` | protocol equals (alias `protocol:`) |
| `iface:en0` | interface equals (alias `interface:`) |
| `state:established`, `source:nettop` | equals |
| `>1mbps`, `<500kbps` | live total rate in bits/s (`bps`, `kbps`, `mbps`, `gbps`) |
| `!key:value` or `-key:value` | exclude |
| `"quoted value"` | keep spaces: `app:"Google Chrome"` |
| anything else | free text over every field |

Different keys combine with AND; repeating a key (`app:safari app:ssh`) is OR; exclusions always win.


## MCP

`agent/nivora_mcp.py` is a read-only MCP server over stdio (JSON-RPC 2.0, stdlib only). Set `NIVORA_URL` and `NIVORA_TOKEN`, then register it with your MCP client, for example `{"command": "python3", "args": ["agent/nivora_mcp.py"], "env": {"NIVORA_TOKEN": "..."}}`. Tools: `summary`, `flows`, `findings`, `explain_flow`, `ask`, `diff`, `incident`, `port_conflicts`, `rule_impact`, `path_check`. None creates or removes rules.
