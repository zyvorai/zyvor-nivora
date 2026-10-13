// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct ApplicationsView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var order = [KeyPathComparator(\NivoraSnapshot.AppItem.total_bps, order: .reverse)]

    var body: some View {
        let apps = store.apps.sorted(using: order)
        Table(apps, sortOrder: $order) {
            TableColumn("Application", value: \.name) { app in
                Button { store.selectedApp = app.name } label: {
                    HStack(spacing: 8) { Monogram(name: app.name, size: 24); Text(app.name).fontWeight(.medium) }
                }.buttonStyle(.plain)
            }
            TableColumn("Connections", value: \.connections) { Text("\($0.connections)").monospacedDigit() }
            TableColumn("↓ Live", value: \.rx_bps) { Text(rateString($0.rx_bps)).monospacedDigit() }
            TableColumn("↑ Live", value: \.tx_bps) { Text(rateString($0.tx_bps)).monospacedDigit() }
            TableColumn("Received", value: \.bytes_in) { Text(byteString($0.bytes_in)).monospacedDigit().foregroundStyle(Palette.textSecondary) }
            TableColumn("Sent", value: \.bytes_out) { Text(byteString($0.bytes_out)).monospacedDigit().foregroundStyle(Palette.textSecondary) }
            TableColumn("Destinations") { Text($0.domains.prefix(2).joined(separator: ", ")).foregroundStyle(Palette.textSecondary) }
        }
        .overlay { if apps.isEmpty { ContentUnavailableView("No applications", systemImage: "square.stack.3d.up", description: Text(store.search.isEmpty ? "No network activity yet." : "Nothing matches your search.")) } }
    }
}

/// Evidence for one application: rates, destinations, flows and leased rule buttons.
struct AppDetailSheet: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.dismiss) private var dismiss
    let name: String

    var body: some View {
        let app = store.snapshot?.apps.first { $0.name == name }
        let flows = store.snapshot?.flows.filter { $0.process == name } ?? []
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                Monogram(name: name, size: 44)
                VStack(alignment: .leading) {
                    Text(name).netraTitle(20)
                    Text(app.map { "PID \($0.pid) · \($0.connections) connections" } ?? "No current network activity").caption2Style()
                }
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.cancelAction)
            }
            if let app {
                HStack(spacing: 12) {
                    stat("↓ Live", rateString(app.rx_bps)); stat("↑ Live", rateString(app.tx_bps)); stat("Total", byteString(app.total))
                }
                Panel(title: "Destinations") {
                    Text(app.domains.isEmpty ? "None" : app.domains.joined(separator: " · ")).foregroundStyle(Palette.textSecondary)
                }
            }
            Panel(title: "Flows") {
                ForEach(flows) { f in
                    HStack { StatusPill(text: f.protocol.uppercased(), kind: "neutral"); Text(f.remote).font(.system(.callout, design: .monospaced)); Spacer(); Text(f.interface).foregroundStyle(Palette.textSecondary) }
                }
                if flows.isEmpty { Text("No flows in the current sample.").foregroundStyle(Palette.textSecondary) }
            }
            Panel(title: "Rules", subtitle: "Observe-first. Blocking is leased for one hour and needs the signed NetworkExtension to take effect.") {
                HStack {
                    Button("Observe") { Task { await store.addRule(action: "observe", app: name) } }
                    Button("Allow") { Task { await store.addRule(action: "allow", app: name) } }
                    Button("Block for 1 h") { Task { await store.addRule(action: "block", app: name) } }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(minWidth: 520, minHeight: 520)
        .background(Palette.page)
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption).foregroundStyle(Palette.textSecondary)
            Text(value).font(.system(size: 18, weight: .semibold)).monospacedDigit()
        }
        .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.panel, in: RoundedRectangle(cornerRadius: 12))
    }
}
