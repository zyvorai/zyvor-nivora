// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import AppKit

/// Closing the window keeps Nivora (and its bundled collector) running in the menu bar.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

@main
struct NivoraApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store = NivoraStore()
    @StateObject private var filter = NivoraFilterManager()

    /// `--appearance light|dark` pins the colour scheme (screenshots).
    static var forcedScheme: ColorScheme? {
        let a = CommandLine.arguments
        guard let i = a.firstIndex(of: "--appearance"), i + 1 < a.count else { return nil }
        return a[i + 1] == "dark" ? .dark : a[i + 1] == "light" ? .light : nil
    }

    /// `--section applications` opens that section (screenshots).
    static var initialSection: Pane {
        let a = CommandLine.arguments
        guard let i = a.firstIndex(of: "--section"), i + 1 < a.count else { return .overview }
        return Pane.allCases.first { $0.rawValue.lowercased() == a[i + 1].lowercased() } ?? .overview
    }

    var body: some Scene {
        Window("Nivora", id: "main") {
            RootView()
                .environmentObject(store)
                .environmentObject(filter)
                .frame(minWidth: 960, minHeight: 640)
                .preferredColorScheme(Self.forcedScheme ?? store.appearance.scheme)
                .tint(store.accent.color)
                .task { store.start() }
        }
        .defaultSize(width: 1180, height: 760)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("Go") {
                ForEach(Array(Pane.allCases.prefix(9).enumerated()), id: \.element) { i, pane in
                    Button(pane.rawValue) { store.pane = pane }
                        .keyboardShortcut(KeyEquivalent(Character("\(i + 1)")), modifiers: .command)
                }
                Divider()
                Button("Settings") { store.pane = .settings }.keyboardShortcut(",", modifiers: .command)
            }
            CommandMenu("Source") {
                Button("Monitor This Mac") { store.useThisMac() }.keyboardShortcut("1", modifiers: [.command, .shift])
                Button("Show Demo Data") { store.useDemo() }.keyboardShortcut("2", modifiers: [.command, .shift])
                Divider()
                Button(store.paused ? "Resume" : "Pause") { store.paused.toggle() }.keyboardShortcut("p")
                Button("Refresh") { Task { await store.refresh() } }.keyboardShortcut("r")
            }
        }

        MenuBarExtra {
            MenuBarView().environmentObject(store)
        } label: {
            Label("Nivora", systemImage: store.alerts.isEmpty ? "network" : "network.badge.shield.half.filled")
        }
        .menuBarExtraStyle(.window)
    }
}
