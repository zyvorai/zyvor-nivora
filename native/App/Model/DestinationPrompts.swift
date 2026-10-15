// SPDX-License-Identifier: BUSL-1.1
import Foundation
import UserNotifications

/// Opt-in notifications for destinations an app has not used before. This is a *post-hoc* prompt: the
/// connection is not paused (that would need the signed content filter). Choosing "Block 1 h" adds a
/// leased rule; "Observe" adds an observe rule; ignoring the notification does nothing.
@MainActor
final class DestinationPrompts: NSObject, UNUserNotificationCenterDelegate {
    static let shared = DestinationPrompts()
    static let enabledKey = "nivora.promptNewDestinations"
    private let category = "NIVORA_NEW_DESTINATION"
    private var seen = Set<String>()
    private var registered = false

    var enabled: Bool { UserDefaults.standard.bool(forKey: Self.enabledKey) }

    private func register() {
        guard !registered else { return }
        registered = true
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        let observe = UNNotificationAction(identifier: "observe", title: "Observe", options: [])
        let block = UNNotificationAction(identifier: "block", title: "Block for 1 h", options: [.destructive])
        center.setNotificationCategories([UNNotificationCategory(identifier: category, actions: [observe, block], intentIdentifiers: [])])
        center.requestAuthorization(options: [.alert]) { _, _ in }
    }

    /// Called with each snapshot; posts at most 3 new prompts per call and never for simulated data.
    func consider(_ s: NivoraSnapshot) {
        guard enabled, !s.host.demo else { return }
        register()
        var posted = 0
        for f in s.findings where f.kind == "behavior" {
            guard posted < 3, let app = f.app, let remote = f.remote, seen.insert(f.id).inserted else { continue }
            posted += 1
            let content = UNMutableNotificationContent()
            content.title = "\(app) reached a new destination"
            content.body = f.detail
            content.categoryIdentifier = category
            content.userInfo = ["app": app, "remote": remote]
            UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: f.id, content: content, trigger: nil))
        }
        if seen.count > 500 { seen.removeAll() }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard ["observe", "block"].contains(response.actionIdentifier),
              let app = response.notification.request.content.userInfo["app"] as? String,
              let remote = response.notification.request.content.userInfo["remote"] as? String else { return }
        let action = response.actionIdentifier
        await MainActor.run {
            guard let store = NivoraStore.current else { return }
            Task { await store.addRule(action: action, app: app, destination: remote) }
        }
    }
}
