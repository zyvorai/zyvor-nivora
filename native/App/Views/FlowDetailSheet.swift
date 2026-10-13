// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import Charts

/// Inspector for one flow: live rates, endpoints, related flows and leased observe-first rules.
struct FlowDetailSheet: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.dismiss) private var dismiss
    let flowID: String

    var body: some View {
        let flow = store.snapshot?.flows.first { $0.id == flowID }
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                Monogram(name: flow?.process ?? "?", size: 44)
                VStack(alignment: .leading) {
                    Text(flow?.process ?? "Flow ended").netraTitle(20)
                    Text(flow.map { "\($0.protocol.uppercased()) → \($0.remote)" } ?? "This flow is no longer in the current sample.").caption2Style()
                }
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.cancelAction)
            }
            if let flow {
                let host = FlowFilter.host(of: flow.remote)
                let same = (store.snapshot?.flows ?? []).filter { $0.id != flow.id && FlowFilter.host(of: $0.remote) == host }
                HStack(spacing: 12) {
                    stat("↓ Live", rateString(flow.rx_bps)); stat("↑ Live", rateString(flow.tx_bps)); stat("Total", byteString(flow.bytes_in + flow.bytes_out))
                }
                if let series = store.flowRates[flowID], series.count > 1 {
                    Panel(title: "Live rate", subtitle: "Last \(series.count) samples") {
                        Chart(Array(series.enumerated()), id: \.offset) {
                            AreaMark(x: .value("t", $0.offset), y: .value("bytes/s", $0.element)).foregroundStyle(Palette.accent.opacity(0.15))
                            LineMark(x: .value("t", $0.offset), y: .value("bytes/s", $0.element)).foregroundStyle(Palette.accent)
                        }
                        .chartXAxis(.hidden)
                        .chartYAxis { AxisMarks(position: .trailing) { v in AxisValueLabel { if let d = v.as(Double.self) { Text(rateString(d)) } } } }
                        .frame(height: 70)
                    }
                }
                Panel(title: "Details") {
                    row("Local", flow.local); row("Remote", flow.remote); row("State", flow.state)
                    row("Interface", flow.interface); row("RTT", flow.rtt_ms > 0 ? String(format: "%.1f ms", flow.rtt_ms) : "—")
                    row("Source", flow.source); row("Bundle", flow.bundle_id ?? "—"); row("First seen", flow.first_seen ?? "—")
                }
                Panel(title: "Same host (\(same.count))") {
                    if same.isEmpty { Text("No other flows to this host.").foregroundStyle(Palette.textSecondary) }
                    ForEach(same.prefix(6)) { f in
                        HStack { Text(f.process); Spacer(); Text(f.remote).font(.system(.callout, design: .monospaced)).foregroundStyle(Palette.textSecondary) }
                    }
                }
                Panel(title: "Actions", subtitle: "Observe-first. Blocking is leased for one hour and needs the signed NetworkExtension to take effect.") {
                    HStack {
                        Button("Filter to this host") { store.search = "host:\(host)"; store.selectedFlow = nil }
                        Button("Observe") { Task { await store.addRule(action: "observe", app: flow.process) } }
                        Button("Block app for 1 h") { Task { await store.addRule(action: "block", app: flow.process) } }
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(minWidth: 520, minHeight: 520)
        .background(Palette.page)
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack { Text(k).foregroundStyle(Palette.textSecondary); Spacer(); Text(v).font(.system(.callout, design: .monospaced)).textSelection(.enabled) }
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
