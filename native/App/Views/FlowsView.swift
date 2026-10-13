// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct FlowsView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var order = [KeyPathComparator(\NivoraSnapshot.Flow.rx_bps, order: .reverse)]
    @State private var grouping: FlowGroup.By = .flat

    var body: some View {
        let flows = store.flows.sorted(using: order)
        VStack(spacing: 0) {
            FilterBar(shown: flows.count, total: store.snapshot?.flows.count ?? 0)
            Divider()
            BaselineCard().padding(.horizontal, 16).padding(.top, store.baseline == nil ? 0 : 12)
            Group {
                if grouping == .flat { flowTable(flows) } else { groupTable(flows) }
            }
        }
        .toolbar {
            ToolbarItem {
                Picker("Group", selection: $grouping) {
                    ForEach(FlowGroup.By.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.menu)
            }
            ToolbarItem {
                Button { store.baseline == nil ? store.pinBaseline() : store.clearBaseline() } label: {
                    Label(store.baseline == nil ? "Pin baseline" : "Clear baseline", systemImage: store.baseline == nil ? "pin" : "pin.slash")
                }
                .help("Remember the current flows and show what changes")
            }
        }
        .modifier(FlowsToolbar(flows: flows))
    }

    private func groupTable(_ flows: [NivoraSnapshot.Flow]) -> some View {
        let groups = FlowGroup.group(flows, by: grouping)
        return Table(groups) {
            TableColumn(grouping == .app ? "Application" : grouping == .host ? "Host" : "Interface") { g in
                Button { store.search = "\(grouping == .app ? "app" : grouping == .host ? "host" : "iface"):\(g.key.contains(" ") ? "\"\(g.key)\"" : g.key)"; grouping = .flat } label: { Text(g.key).fontWeight(.medium) }
                    .buttonStyle(.plain)
            }
            TableColumn("Flows") { Text("\($0.count)").monospacedDigit() }
            TableColumn("↓ Live") { Text(rateString($0.rx)).monospacedDigit() }
            TableColumn("↑ Live") { Text(rateString($0.tx)).monospacedDigit() }
            TableColumn("↓") { Text(byteString($0.bytesIn)).monospacedDigit() }
            TableColumn("↑") { Text(byteString($0.bytesOut)).monospacedDigit() }
        }
    }

    private func flowTable(_ flows: [NivoraSnapshot.Flow]) -> some View {
        Table(flows, sortOrder: $order) {
            TableColumn("Application", value: \.process) { f in
                HStack {
                    Button { store.selectedApp = f.process } label: { Text(f.process).fontWeight(.medium) }.buttonStyle(.plain)
                    Spacer()
                    Button { store.selectedFlow = f.id } label: { Image(systemName: "info.circle") }
                        .buttonStyle(.plain).help("Flow details").accessibilityLabel("Flow details")
                }
            }
            .width(min: 150, ideal: 210)
            TableColumn("Proto", value: \.protocol) { StatusPill(text: $0.protocol.uppercased(), kind: "neutral") }
                .width(min: 56, ideal: 64, max: 80)
            TableColumn("Remote", value: \.remote) { Text($0.remote).font(.system(.callout, design: .monospaced)).lineLimit(1).truncationMode(.middle) }
                .width(min: 180, ideal: 260)
            TableColumn("State", value: \.state) { Text($0.state).foregroundStyle(Palette.textSecondary).lineLimit(1) }
                .width(min: 90, ideal: 120)
            TableColumn("Interface", value: \.interface) { Text($0.interface) }
                .width(min: 70, ideal: 90, max: 120)
            TableColumn("RTT", value: \.rtt_ms) { Text($0.rtt_ms > 0 ? String(format: "%.1f ms", $0.rtt_ms) : "—").monospacedDigit() }
                .width(min: 70, ideal: 80, max: 110)
            TableColumn("↓ Live", value: \.rx_bps) { Text(rateString($0.rx_bps)).monospacedDigit() }
                .width(min: 90, ideal: 100)
            TableColumn("↑ Live", value: \.tx_bps) { Text(rateString($0.tx_bps)).monospacedDigit() }
                .width(min: 90, ideal: 100)
        }
    }
}

/// Toolbar items, export alert and empty overlay shared by the flat and grouped Flows layouts.
private struct FlowsToolbar: ViewModifier {
    @EnvironmentObject var store: NivoraStore
    let flows: [NivoraSnapshot.Flow]

    func body(content: Content) -> some View {
        content
        .toolbar {
            ToolbarItem {
                Menu {
                    Button("Flows as CSV (current filter)") { Task { await store.export(kind: "flows", format: "csv", redact: false) } }
                    Button("Flows as CSV, redacted") { Task { await store.export(kind: "flows", format: "csv", redact: true) } }
                    Button("Flows as NDJSON") { Task { await store.export(kind: "flows", format: "ndjson", redact: false) } }
                    Divider()
                    Button("Bundle (.zip)") { Task { await store.export(kind: "bundle", format: "zip", redact: false) } }
                    Button("Bundle (.zip), redacted") { Task { await store.export(kind: "bundle", format: "zip", redact: true) } }
                } label: { Label("Export", systemImage: "square.and.arrow.up") }
                .disabled(flows.isEmpty)
            }
        }
        .alert("Export", isPresented: Binding(get: { store.exportError != nil }, set: { if !$0 { store.exportError = nil } })) {
            Button("OK", role: .cancel) {}
        } message: { Text(store.exportError ?? "") }
        .overlay { if flows.isEmpty { FilteredEmpty(title: "No flows", symbol: "arrow.left.arrow.right", idle: "No flows in the current sample.") } }
    }
}
