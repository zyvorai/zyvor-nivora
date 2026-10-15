// SPDX-License-Identifier: BUSL-1.1
import AppIntents

/// Shortcuts / Siri actions. They run inside the app process and talk to the bundled loopback collector.
struct NetworkStatusIntent: AppIntent {
    static let title: LocalizedStringResource = "How is my network?"
    static let description = IntentDescription("Health, live rates and the busiest app, from local telemetry.")

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog & ReturnsValue<String> {
        let text = NivoraStore.current?.statusSentence ?? "Open Nivora first so it can start observing."
        return .result(value: text, dialog: IntentDialog(stringLiteral: text))
    }
}

struct BlockAppIntent: AppIntent {
    static let title: LocalizedStringResource = "Block an app for one hour"
    static let description = IntentDescription("Adds a one-hour block rule. Needs the NetworkExtension to enforce; otherwise it is only recorded.")

    @Parameter(title: "App name") var app: String

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await requestConfirmation(result: .result(dialog: IntentDialog(stringLiteral: "Block \(app) for one hour?")))
        guard let store = NivoraStore.current else { return .result(dialog: "Open Nivora first.") }
        await store.addRule(action: "block", app: app)
        return .result(dialog: IntentDialog(stringLiteral: "\(app) is blocked for one hour."))
    }
}

struct NivoraShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: NetworkStatusIntent(), phrases: ["How is my network in \(.applicationName)", "What is using my network in \(.applicationName)"],
                    shortTitle: "Network status", systemImageName: "network")
    }
}
