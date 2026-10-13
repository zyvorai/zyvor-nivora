// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct SecurityView: View {
    @EnvironmentObject var store: NivoraStore
    @EnvironmentObject var filter: NivoraFilterManager
    var body: some View {
        if let s = store.snapshot {
            Page {
                Panel(title: "Visibility") {
                    LabeledContent("Collector", value: s.capabilities.nettop ? "nettop" : "lsof / fallback")
                    LabeledContent("NetworkExtension", value: s.capabilities.network_extension ? "Reporting" : "Not reporting")
                    Toggle("Enable NetworkExtension inspector", isOn: Binding(get: { filter.enabled }, set: { v in Task { await filter.setEnabled(v) } }))
                    Text("Blocking rules are observe-first until the signed content-filter extension is enabled. Apple approval and signing are required for shipping.")
                        .font(.caption).foregroundStyle(Palette.textSecondary)
                }
                Panel(title: "Findings") {
                    if s.findings.isEmpty { Text("No current findings.").foregroundStyle(Palette.textSecondary) }
                    ForEach(store.alerts.filter { $0.id.hasPrefix("finding-") }) { AlertRow(alert: $0) }
                }
                Panel(title: "Rules", subtitle: "Block rules default to a one-hour lease") {
                    let rules = s.rules ?? []
                    if rules.isEmpty { Text("No rules yet. Open an application to add one.").foregroundStyle(Palette.textSecondary) }
                    ForEach(rules) { r in
                        HStack {
                            StatusPill(text: r.action.capitalized, kind: r.action == "block" ? "critical" : r.action == "allow" ? "good" : "neutral")
                            Text(r.app ?? r.domain ?? r.ip ?? r.port.map { "port \($0)" } ?? "rule")
                            Spacer()
                            Button { Task { await store.deleteRule(r.id) } } label: { Image(systemName: "xmark.circle") }.buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}

struct AlertsView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        Page {
            if store.alerts.isEmpty {
                ContentUnavailableView("All quiet", systemImage: "checkmark.seal", description: Text("No findings or threshold alerts right now."))
            }
            ForEach(store.alerts) { a in
                Panel {
                    HStack(alignment: .top) {
                        AlertRow(alert: a)
                        Spacer()
                        if let app = a.app { Button("Show app") { store.selectedApp = app } }
                        Button("Dismiss") { store.dismiss(a.id) }
                    }
                }
            }
        }
    }
}

struct InvestigatorView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var question = ""
    var body: some View {
        Page {
            Panel(title: "Ask Nivora", subtitle: "The built-in investigator reasons over local telemetry only. No cloud, no API key.") {
                HStack {
                    TextField("Why is Slack slow?", text: $question).textFieldStyle(.roundedBorder).onSubmit(ask)
                    Button("Ask", action: ask).keyboardShortcut(.defaultAction)
                }
                Text(store.investigatorAnswer).textSelection(.enabled).padding(.top, 4)
            }
        }
    }
    private func ask() {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return }
        Task { await store.ask(q) }
    }
}
