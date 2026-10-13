// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import Charts

struct MenuBarView: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.openWindow) private var openWindow

    private func show(_ pane: Pane? = nil, app: String? = nil) {
        if let pane { store.pane = pane }
        if let app { store.selectedApp = app }
        openWindow(id: "main")
        NSApp.activate(ignoringOtherApps: true)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Nivora").netraTitle(15)
                if store.snapshot?.host.demo == true { StatusPill(text: "Demo", kind: "neutral") }
                Spacer()
                if let s = store.snapshot { StatusPill(text: "\(s.health.score)/100", kind: s.health.status) }
            }
            if let s = store.snapshot {
                HStack {
                    Label(rateString(s.traffic.rx_bps), systemImage: "arrow.down").monospacedDigit().foregroundStyle(Palette.accent)
                    Spacer()
                    Label(rateString(s.traffic.tx_bps), systemImage: "arrow.up").monospacedDigit().foregroundStyle(Palette.purple)
                }.font(.callout)
                if store.history.count > 1 {
                    Chart(store.history) {
                        AreaMark(x: .value("t", $0.time), y: .value("rx", $0.rx)).foregroundStyle(Palette.accent.opacity(0.15))
                        LineMark(x: .value("t", $0.time), y: .value("rx", $0.rx), series: .value("k", "rx")).foregroundStyle(Palette.accent)
                        LineMark(x: .value("t", $0.time), y: .value("tx", $0.tx), series: .value("k", "tx")).foregroundStyle(Palette.purple)
                    }
                    .chartXAxis(.hidden).chartYAxis(.hidden)
                    .frame(height: 38)
                    .accessibilityHidden(true)
                }
                Divider()
                ForEach(s.apps.sorted { $0.total_bps > $1.total_bps }.prefix(4)) { app in
                    Button { show(.applications, app: app.name) } label: {
                        HStack { Monogram(name: app.name, size: 20); Text(app.name).lineLimit(1); Spacer()
                            Text(rateString(app.total_bps)).font(.caption).monospacedDigit().foregroundStyle(Palette.textSecondary) }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
                if !store.alerts.isEmpty {
                    Divider()
                    Button { show(.alerts) } label: {
                        Label("\(store.alerts.count) item(s) need attention", systemImage: "bell.badge")
                            .font(.caption).foregroundStyle(Palette.amber)
                    }
                    .buttonStyle(.plain)
                }
            } else {
                Text("Starting…").foregroundStyle(Palette.textSecondary)
            }
            Divider()
            HStack {
                Button("Open Nivora") { show() }.keyboardShortcut(.defaultAction)
                Spacer()
                Button(store.paused ? "Resume" : "Pause") { store.paused.toggle() }
                Button("Quit") { NSApp.terminate(nil) }
            }
        }
        .padding(14).frame(width: 300)
    }
}
