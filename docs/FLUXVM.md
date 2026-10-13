# FluxVM integration

FluxVM is a first-class Nivora context source, not just another process name.

Default base URL: `http://127.0.0.1:7788`.

Nivora 0.2 probes the current FluxVM read APIs when present:

```text
/healthz
/v1/vms
/v1/sandboxes
/v1/network/health
/v1/network/endpoints
/v1/network/hubble/flows?limit=200
/v1/network/observe
```

It also probes optional `/v1/network/telemetry` for a future/richer direct-attribution contract. Every network endpoint is optional so Nivora remains compatible with FluxVM builds that do not ship a specific subsystem.

Environment overrides:

```bash
export FLUXVM_SERVER=http://127.0.0.1:7788
export FLUXVM_TOKEN=...
python3 agent/nivora.py
```

Nivora also correlates host flows whose process identity belongs to FluxVM/VZ/usernet/vmnet and surfaces counts beside FluxVM network endpoints and Hubble flows.

A richer direct attribution record may look like:

```json
{
  "vm_id":"macos-build-07",
  "sandbox_id":null,
  "backend":"vz",
  "interface":"vmnet8",
  "local":"10.0.2.15:40544",
  "remote":"github.com:443",
  "bytes_in":1234,
  "bytes_out":567
}
```
