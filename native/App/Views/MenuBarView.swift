// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Nivora").netraTitle(15)
                Spacer()
                if let s = store.snapshot { StatusPill(text: "\(s.health.score)/100", kind: s.health.status) }
            }
            if let s = store.snapshot {
                HStack {
                    Label(rateString(s.traffic.rx_bps), systemImage: "arrow.down").monospacedDigit()
                    Spacer()
                    Label(rateString(s.traffic.tx_bps), systemImage: "arrow.up").monospacedDigit()
                }.font(.callout)
                Divider()
                ForEach(s.apps.sorted { $0.total_bps > $1.total_bps }.prefix(4)) { app in
                    HStack { Monogram(name: app.name, size: 20); Text(app.name).lineLimit(1); Spacer()
                        Text(rateString(app.total_bps)).font(.caption).monospacedDigit().foregroundStyle(Palette.textSecondary) }
                }
                if !store.alerts.isEmpty { Divider(); Text("\(store.alerts.count) item(s) need attention").font(.caption).foregroundStyle(Palette.amber) }
            } else {
                Text("Starting…").foregroundStyle(Palette.textSecondary)
            }
            Divider()
            HStack {
                Button("Open Nivora") { openWindow(id: "main"); NSApp.activate() }
                Spacer()
                Button(store.paused ? "Resume" : "Pause") { store.paused.toggle() }
            }
        }
        .padding(14).frame(width: 300)
    }
}
