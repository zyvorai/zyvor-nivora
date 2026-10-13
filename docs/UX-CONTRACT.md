# UX contract

Nivora should feel like a sibling of Vytrix, not a generic network dashboard. Colour and type come from Netra (light-first Apple palette: `#1d1d1f`/`#6e6e73` text, `#0071e3` accent, hairline borders, SF Pro); interaction patterns come from Vytrix. The native app uses the same palette (`native/App/Views/Theme.swift`).

- System font stack / SwiftUI native typography.
- macOS window chrome and traffic-light visual treatment on web.
- Light/dark support.
- Thin separators, low-contrast cards, compact tables.
- Group by application first; packets are evidence, not the primary navigation model.
- Every alarming state must link to evidence.
- Observe-first language; no scary red unless an actual critical condition is present.
- Demo telemetry must be labeled simulated.
- Search works across app, endpoint, IP and port.
- No telemetry upload or account requirement in the base product.

## 0.2 interaction rules

- **Rates first, totals second.** Live RX/TX is the primary number when answering “what is using my network now”; cumulative bytes remain evidence.
- **Health is explainable.** The 0–100 score must render its component scores and a diagnosis. Never show a magic number without evidence.
- **Network Map is identity-first.** Applications are on the left, Mac interfaces in the middle, destinations on the right. Avoid packet-centric topology clutter.
- **Local exposure is visible.** Listening services bound to all interfaces must be visually distinct from loopback-only listeners.
- **Safety is leased.** A Block action defaults to one hour unless the user explicitly chooses permanent. Explicit Allow rules override broader Block rules.
- **Time Machine learns quietly.** The first behavior sample seeds a baseline; only later unseen destinations are called new. Demo data never trains a real host baseline.
- **FluxVM is a first-class source, not a badge.** When available, show VM/sandbox identity, current network health, endpoints and Hubble-style flows alongside host applications.

## 0.3 interaction rules

- **Everything is reachable from the keyboard.** `⌘K`/`Ctrl K` opens the command palette (views, apps, "Ask Investigator"); `/` focuses search, `p` pauses, `r` refreshes, `g` then `o/h/m/a/f` jumps to a view, `?` lists shortcuts, `Esc` closes panels.
- **Click an application to see its evidence.** The right-hand sheet shows live rates, a short history sparkline, destinations, ports, flows and leased rule buttons.
- **Tables are sortable and searchable.** Sorted columns expose `aria-sort`; matches are highlighted.
- **Feedback is non-blocking.** Toasts replace `alert()`; first load shows skeletons; failures show a retry state and a "Disconnected — retrying" status.
- **Rendering never fights the user.** Timer refreshes are skipped while an input has focus and on static views (Timeline, Investigator, Settings).
- **Preferences are local and non-sensitive.** Theme, accent, density, transparency, refresh interval, alert threshold and pinned apps live in `localStorage['nivora-prefs']`; the API token is never persisted.
- **Alerts observe, they do not enforce.** The optional per-app throughput threshold raises a toast and a Security badge only.
- **Exports stay local.** Snapshot JSON and flows CSV are generated in the browser; CSV cells that look like formulas are neutralised.

## Filters, views and inspection

- The search box accepts the shared filter grammar (`docs/API.md`); each token becomes a removable chip above Flows.
- Saved views store a filter string only (max 20, names trimmed, in `localStorage['nivora-views']` via prefs / native UserDefaults); they appear in the command palette.
- Clicking a flow row opens the flow inspector; "Filter to this host" and leased rules are the only actions, both observe-first.
- Group-by (app/host/interface) and "Pin baseline" compare are read-only summaries over the current sample.
- Exports state that they contain metadata only and offer redaction.

