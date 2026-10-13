// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct HealthView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            Page {
                HStack(alignment: .top, spacing: 16) {
                    Panel(title: "Network health", subtitle: s.health.status.capitalized) {
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text("\(s.health.score)").font(.system(size: 56, weight: .semibold)).tracking(-1).monospacedDigit()
                                .foregroundStyle(Palette.status(s.health.status))
                            Text("/ 100").foregroundStyle(Palette.textSecondary)
                        }
                        Text("Median RTT \(String(format: "%.0f", s.health.median_rtt_ms)) ms").font(.callout).foregroundStyle(Palette.textSecondary)
                    }
                    Panel(title: "Components", subtitle: "Every score is explained") {
                        ForEach(s.health.components) { c in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack { Text(c.name).font(.callout.weight(.medium)); Spacer(); Text("\(c.score)").monospacedDigit().foregroundStyle(Palette.textSecondary) }
                                Meter(fraction: Double(c.score) / 100, tint: c.score >= 80 ? Palette.green : c.score >= 50 ? Palette.amber : Palette.danger)
                                Text(c.detail).font(.caption).foregroundStyle(Palette.textSecondary)
                            }
                        }
                    }
                }
                Panel(title: "Health history") {
                    ChartHealth(samples: store.history)
                }
            }
        }
    }
}

import Charts
private struct ChartHealth: View {
    let samples: [Sample]
    var body: some View {
        Chart(samples) { LineMark(x: .value("Time", $0.time), y: .value("Score", $0.health)).foregroundStyle(Palette.accent) }
            .chartYScale(domain: 0...100).frame(height: 160)
    }
}
