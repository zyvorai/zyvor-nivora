# API

All `/v1/*` requests use `Authorization: Bearer $NIVORA_TOKEN` when a token is configured. The local server uses constant-time bearer comparison, rejects unapproved browser origins, serves no-store JSON, and adds basic browser hardening headers.

## Complete snapshot

`GET /v1/snapshot` returns the normalized Mac network state: host, apps, flows, live rates, interfaces, routes, DNS, VPN, Wi-Fi, neighbors, listeners, health, topology, findings, learned behavior, FluxVM context, rules and rule hits.

## Focused reads

- `GET /v1/apps`
- `GET /v1/flows`
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

A rule needs at least one of `app`, `domain`, `ip`, or `port`. `action` is `observe`, `allow`, or `block`.

**Safety:** a block rule without `expires_at` is automatically leased for 3600 seconds. Supply `duration_seconds` to choose 60 seconds through 7 days, or `permanent: true` to intentionally create a non-expiring block.

```json
{"action":"block","app":"com.example.App","duration_seconds":900}
```

`DELETE /v1/rules/{id}` removes one rule.

Collector-only deployments preview matches but do not alter traffic. Signed NetworkExtension deployments can enforce active `block` rules.
