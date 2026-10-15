// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var store: NivoraStore
    @AppStorage("nivora.promptNewDestinations") private var promptNewDestinations = false
    var body: some View {
        Form {
            Section("Appearance") {
                Picker("Theme", selection: $store.appearance) { ForEach(AppearanceChoice.allCases) { Text($0.label).tag($0) } }
                    .pickerStyle(.segmented)
                Picker("Accent", selection: $store.accent) {
                    ForEach(AccentChoice.allCases) { a in Label(a.label, systemImage: "circle.fill").foregroundStyle(a.color).tag(a) }
                }
            }
            Section("Alerts") {
                Stepper(value: $store.thresholdMbps, in: 0...10_000, step: 5) {
                    Text(store.thresholdMbps == 0 ? "Per-app throughput alert: off" : "Per-app throughput alert: \(Int(store.thresholdMbps)) Mbit/s")
                }
                Toggle("Notify when an app reaches a new destination", isOn: $promptNewDestinations)
                Text("Notifications offer Observe or a one-hour block after the fact; connections are not paused.").font(.caption).foregroundStyle(Palette.textSecondary)
                Text("Alerts observe and explain; they never block traffic.").font(.caption).foregroundStyle(Palette.textSecondary)
            }
            Section("Data") {
                Button(store.demo ? "Monitor This Mac" : "Show Demo Data") { store.demo ? store.useThisMac() : store.useDemo() }
                Text("Nivora is local-first. No telemetry is uploaded and no account is required.").font(.caption).foregroundStyle(Palette.textSecondary)
            }
            Section("About") {
                LegalLine().frame(maxWidth: .infinity, alignment: .leading)
                Link("Licence (Business Source License 1.1)", destination: URL(string: "https://github.com/zyvorai/zyvor-nivora/blob/main/LICENSE")!)
                Text("Production and commercial deployments require a commercial licence from Zyvor AI Labs Private Limited.")
                    .font(.caption).foregroundStyle(Palette.textSecondary)
            }
        }
        .formStyle(.grouped)
    }
}
