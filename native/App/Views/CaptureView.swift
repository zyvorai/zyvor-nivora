// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct CaptureView: View {
    @EnvironmentObject var store: NivoraStore
    @StateObject private var helper = CaptureHelperManager()
    @State private var iface = "en0"
    @State private var host = ""
    @State private var proto = "any"
    @State private var port = ""
    @State private var seconds = 60
    @State private var snaplen = 96
    @State private var confirmed = false

    var body: some View {
        let info = store.captures
        let interfaces = store.snapshot?.interfaces.filter { $0.status == "active" || $0.name.hasPrefix("lo") }.map(\.name) ?? ["en0"]
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Panel(title: "Helper", subtitle: "Packet capture needs a small privileged helper. It runs tcpdump with a fixed argument list, headers only, and never starts on its own.") {
                    HStack {
                        StatusPill(text: info?.demo == true ? "Simulated" : (info?.available == true ? "Running" : helper.label), kind: info?.available == true ? "good" : "neutral")
                        Spacer()
                        if info?.demo != true {
                            Button("Install helper…") { helper.install() }
                            Button("Remove") { helper.uninstall() }
                        }
                    }
                    if let m = helper.message { Text(m).font(.callout).foregroundStyle(Palette.textSecondary) }
                }
                Panel(title: "New capture", subtitle: "Records the first bytes of each matching packet, stored locally for 24 hours.") {
                    Form {
                        Picker("Interface", selection: $iface) { ForEach(interfaces, id: \.self) { Text($0) } }
                        TextField("Host (IP address)", text: $host, prompt: Text("optional"))
                        Picker("Protocol", selection: $proto) { ForEach(["any", "tcp", "udp", "icmp"], id: \.self) { Text($0) } }
                        TextField("Port", text: $port, prompt: Text("optional"))
                        Picker("Duration", selection: $seconds) { ForEach([10, 30, 60, 120, 300], id: \.self) { Text("\($0) s").tag($0) } }
                        Picker("Bytes per packet", selection: $snaplen) { ForEach([64, 96, 128, 256], id: \.self) { Text("\($0)").tag($0) } }
                        Toggle("I understand this records packet headers of the matching traffic.", isOn: $confirmed)
                    }
                    Button("Start capture") {
                        let r = CaptureRequest(op: "start", iface: iface, host: host.isEmpty ? nil : host, port: Int(port),
                                               proto: proto, snaplen: snaplen, seconds: seconds)
                        Task { await store.startCapture(r) }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!confirmed || info?.available != true)
                }
                Panel(title: "Captures") {
                    if (info?.sessions ?? []).isEmpty { Text("No captures yet.").foregroundStyle(Palette.textSecondary) }
                    ForEach(info?.sessions ?? []) { s in
                        HStack {
                            VStack(alignment: .leading) {
                                Text("\(s.iface) · \(s.filter)").font(.system(.callout, design: .monospaced))
                                Text("\(s.state) · \(byteString(s.bytes))").caption2Style()
                            }
                            Spacer()
                            if s.state == "running" {
                                Button("Stop") { Task { await store.stopCapture(s.id) } }
                            } else {
                                Button("Download…") { Task { await store.downloadCapture(s.id) } }
                            }
                            Button("Delete", role: .destructive) { Task { await store.deleteCapture(s.id) } }
                        }
                    }
                }
            }
            .padding(24)
        }
        .background(Palette.page)
        .task {
            helper.refresh()
            while !Task.isCancelled {
                await store.refreshCaptures()
                try? await Task.sleep(for: .seconds(1.5))
            }
        }
        .alert("Capture", isPresented: Binding(get: { store.captureError != nil }, set: { if !$0 { store.captureError = nil } })) {
            Button("OK", role: .cancel) {}
        } message: { Text(store.captureError ?? "") }
    }
}
