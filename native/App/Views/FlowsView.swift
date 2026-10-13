// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct FlowsView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var order = [KeyPathComparator(\NivoraSnapshot.Flow.rx_bps, order: .reverse)]
    @State private var grouping: FlowGroup.By = .flat

    var body: some View {
        let flows = store.flows.sorted(using: order)
        Group {
            if grouping == .flat { flowTable(flows) } else { groupTable(flows) }
        }
        .toolbar {
            ToolbarItem {
                Picker("Group", selection: $grouping) {
                    ForEach(FlowGroup.By.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.menu)
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
            TableColumn("Proto", value: \.protocol) { StatusPill(text: $0.protocol.uppercased(), kind: "neutral") }
            TableColumn("Remote", value: \.remote) { Text($0.remote).font(.system(.callout, design: .monospaced)) }
            TableColumn("State", value: \.state) { Text($0.state).foregroundStyle(Palette.textSecondary) }
            TableColumn("Interface", value: \.interface) { Text($0.interface) }
            TableColumn("RTT", value: \.rtt_ms) { Text($0.rtt_ms > 0 ? String(format: "%.1f ms", $0.rtt_ms) : "—").monospacedDigit() }
            TableColumn("↓ Live", value: \.rx_bps) { Text(rateString($0.rx_bps)).monospacedDigit() }
            TableColumn("↑ Live", value: \.tx_bps) { Text(rateString($0.tx_bps)).monospacedDigit() }
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
        .overlay { if flows.isEmpty { ContentUnavailableView("No flows", systemImage: "arrow.left.arrow.right", description: Text(store.search.isEmpty ? "No flows in the current sample." : "Nothing matches your search.")) } }
    }
}
