// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Shown once on first launch: what Nivora sees, what it never does, and how to start.
struct WelcomeView: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 22) {
            VStack(spacing: 8) {
                Image(nsImage: NSApp.applicationIconImage).resizable().frame(width: 72, height: 72)
                Text("Welcome to Nivora").netraTitle(26)
                Text("See every connection on your Mac.").foregroundStyle(Palette.textSecondary)
            }
            HStack(alignment: .top, spacing: 14) {
                card("eye", "What it sees",
                     "Which apps talk to what, over which interface: flows, DNS, routes, VPNs, listeners and local neighbours.")
                card("lock.shield", "What it never does",
                     "No packet payloads, no uploads, no blocking by default. Everything stays on this Mac and starts in observe mode.")
                card("slider.horizontal.3", "Go further",
                     "Add the signed content filter for per-app attribution, or the opt-in capture helper. Both ask for your approval.")
            }
            .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button("Explore with demo data") { store.useDemo(); finish() }
                Spacer()
                Button("Start monitoring this Mac") { store.useThisMac(); finish() }
                    .buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
            }
            LegalLine()
        }
        .padding(28)
        .frame(width: 640)
        .background(Palette.page)
    }

    private func finish() {
        UserDefaults.standard.set(true, forKey: WelcomeGate.defaultsKey)
        dismiss()
    }

    private func card(_ symbol: String, _ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: symbol).font(.system(size: 20, weight: .medium)).foregroundStyle(Palette.accent)
            Text(title).font(.headline)
            Text(body).font(.callout).foregroundStyle(Palette.textSecondary).fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Palette.panel, in: RoundedRectangle(cornerRadius: 14))
    }
}

/// ⌘/ cheat sheet.
struct ShortcutsView: View {
    @Environment(\.dismiss) private var dismiss
    private let rows: [(String, String)] = [
        ("⌘1 … ⌘9", "Jump to a pane"), ("⌘,", "Settings"), ("⌘R", "Refresh now"), ("⌘P", "Pause or resume sampling"),
        ("⇧⌘1 / ⇧⌘2", "Monitor this Mac / demo data"), ("⌘F", "Filter flows and apps (app: host: port: proto: >1mbps)"),
        ("⌘/", "This list"),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { Text("Keyboard shortcuts").netraTitle(18); Spacer(); Button("Done") { dismiss() }.keyboardShortcut(.cancelAction) }
            ForEach(rows, id: \.0) { k, v in
                HStack { Text(k).font(.system(.callout, design: .monospaced)).frame(width: 110, alignment: .leading); Text(v).foregroundStyle(Palette.textSecondary) }
            }
        }
        .padding(24).frame(width: 460).background(Palette.page)
    }
}

/// "Zyvor Nivora · © 2026 Zyvor AI Labs Private Limited · BUSL-1.1", same wording as Zyvor Vytrix.
struct LegalLine: View {
    private var version: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "" }
    var body: some View {
        VStack(spacing: 2) {
            Text("Zyvor Nivora \(version)").font(.caption.weight(.medium))
            HStack(spacing: 4) {
                Text("© 2026 Zyvor AI Labs Private Limited · BUSL-1.1 ·")
                Link("zyvor.dev", destination: URL(string: "https://zyvor.dev")!)
            }
        }
        .font(.caption).foregroundStyle(Palette.textSecondary)
    }
}
