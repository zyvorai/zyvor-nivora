// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct FlowsView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var order = [KeyPathComparator(\NivoraSnapshot.Flow.rx_bps, order: .reverse)]

    var body: some View {
        let flows = store.flows.sorted(using: order)
        Table(flows, sortOrder: $order) {
            TableColumn("Application", value: \.process) { f in
                Button { store.selectedApp = f.process } label: { Text(f.process).fontWeight(.medium) }.buttonStyle(.plain)
            }
            TableColumn("Proto", value: \.protocol) { StatusPill(text: $0.protocol.uppercased(), kind: "neutral") }
            TableColumn("Remote", value: \.remote) { Text($0.remote).font(.system(.callout, design: .monospaced)) }
            TableColumn("State", value: \.state) { Text($0.state).foregroundStyle(Palette.textSecondary) }
            TableColumn("Interface", value: \.interface) { Text($0.interface) }
            TableColumn("RTT", value: \.rtt_ms) { Text($0.rtt_ms > 0 ? String(format: "%.1f ms", $0.rtt_ms) : "—").monospacedDigit() }
            TableColumn("↓ Live", value: \.rx_bps) { Text(rateString($0.rx_bps)).monospacedDigit() }
            TableColumn("↑ Live", value: \.tx_bps) { Text(rateString($0.tx_bps)).monospacedDigit() }
        }
        .toolbar {
            ToolbarItem {
                Menu {
                    ForEach(store.savedViews) { v in
                        Button(v.name) { store.apply(v) }
                    }
                    if !store.savedViews.isEmpty { Divider() }
                    Button("Save current filter") { store.saveCurrentView() }
                        .disabled(store.search.trimmingCharacters(in: .whitespaces).isEmpty)
                    Menu("Delete view") {
                        ForEach(store.savedViews) { v in Button(v.name, role: .destructive) { store.deleteView(v) } }
                    }
                    .disabled(store.savedViews.isEmpty)
                    Divider()
                    Text("Syntax: app: host: port: proto: iface: state: source: >1mbps !negate")
                } label: { Label("Views", systemImage: "line.3.horizontal.decrease.circle") }
            }
            ToolbarItem {
                ShareLink(item: FlowExport.csv(flows), preview: SharePreview("Nivora flows.csv")) {
                    Label("Export CSV", systemImage: "square.and.arrow.up")
                }
                .disabled(flows.isEmpty)
            }
        }
        .overlay { if flows.isEmpty { ContentUnavailableView("No flows", systemImage: "arrow.left.arrow.right", description: Text(store.search.isEmpty ? "No flows in the current sample." : "Nothing matches your search.")) } }
    }
}
