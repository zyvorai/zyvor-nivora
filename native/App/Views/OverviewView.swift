// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct OverviewView: View {
    @EnvironmentObject var store: NivoraStore
    let open: (Pane) -> Void

    var body: some View {
        if let s = store.snapshot {
            Page {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 4), spacing: 12) {
                    MetricTile(label: "Health", symbol: "heart.text.square", value: "\(s.health.score)", unit: "/ 100", hint: s.health.status.capitalized,
                               series: store.history.map { Double($0.health) }, tint: Palette.status(s.health.status)) { open(.health) }
                    MetricTile(label: "Download", symbol: "arrow.down.circle", value: rateString(s.traffic.rx_bps), hint: "live",
                               series: store.history.map(\.rx)) { open(.flows) }
                    MetricTile(label: "Upload", symbol: "arrow.up.circle", value: rateString(s.traffic.tx_bps), hint: "live",
                               series: store.history.map(\.tx), tint: Palette.purple) { open(.flows) }
                    MetricTile(label: "Connections", symbol: "arrow.left.arrow.right", value: "\(s.flows.count)", hint: "\(s.apps.count) applications",
                               series: store.history.map { Double($0.flows) }, tint: Palette.green) { open(.applications) }
                }
                Panel(title: "Throughput", subtitle: "Download and upload over the last few minutes") { RateChart(samples: store.history) }
                HStack(alignment: .top, spacing: 16) {
                    Panel(title: "Top applications now") {
                        let top = s.apps.sorted { $0.total_bps > $1.total_bps }.prefix(6)
                        let peak = max(1, top.first?.total_bps ?? 1)
                        ForEach(Array(top)) { app in
                            Button { store.selectedApp = app.name } label: {
                                HStack(spacing: 10) {
                                    Monogram(name: app.name)
                                    VStack(alignment: .leading, spacing: 4) {
                                        HStack { Text(app.name).font(.callout.weight(.medium)); Spacer(); Text(rateString(app.total_bps)).font(.callout).monospacedDigit().foregroundStyle(Palette.textSecondary) }
                                        Meter(fraction: app.total_bps / peak)
                                    }
                                    Sparkline(values: store.appRates[app.name]).frame(width: 64, height: 24)
                                }
                            }.buttonStyle(.plain)
                        }
                    }
                    VStack(spacing: 16) {
                    Panel(title: "What changed", subtitle: "Recent network events") {
                        let events = Array((s.recent_events ?? []).suffix(4).reversed())
                        if events.isEmpty {
                            Text("Nothing has changed since Nivora started watching.").foregroundStyle(Palette.textSecondary)
                        }
                        ForEach(events) { e in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(e.title).font(.callout.weight(.medium))
                                if let d = e.detail, !d.isEmpty { Text(d).font(.caption).foregroundStyle(Palette.textSecondary) }
                            }
                        }
                    }
                    Panel(title: "What needs attention") {
                        if store.alerts.isEmpty {
                            Text("No current findings. Observe-first mode is quiet.").foregroundStyle(Palette.textSecondary)
                        } else {
                            ForEach(store.alerts.prefix(5)) { AlertRow(alert: $0) }
                        }
                    }
                    }
                }
            }
        }
    }
}

struct AlertRow: View {
    let alert: NivoraAlert
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle().fill(alert.severity == .critical ? Palette.danger : alert.severity == .warning ? Palette.amber : Palette.cyan)
                .frame(width: 8, height: 8).padding(.top, 6)
            VStack(alignment: .leading, spacing: 2) {
                Text(alert.title).font(.callout.weight(.medium))
                Text(alert.detail).font(.caption).foregroundStyle(Palette.textSecondary)
            }
        }
    }
}
