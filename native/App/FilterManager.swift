// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension

@MainActor
final class NivoraFilterManager: ObservableObject {
    @Published var enabled = false
    @Published var status = "Collector fallback"

    func load() async {
        do {
            let manager = NEFilterManager.shared()
            try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
                manager.loadFromPreferences { error in error.map { c.resume(throwing: $0) } ?? c.resume() }
            }
            enabled = manager.isEnabled
            status = enabled ? "NetworkExtension enabled" : "Collector fallback"
        } catch { status = error.localizedDescription }
    }

    func setEnabled(_ value: Bool) async {
        let manager = NEFilterManager.shared()
        do {
            try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
                manager.loadFromPreferences { error in error.map { c.resume(throwing: $0) } ?? c.resume() }
            }
            let config = NEFilterProviderConfiguration()
            config.filterSockets = true
            config.filterPackets = false
            manager.providerConfiguration = config
            manager.localizedDescription = "Nivora Network Intelligence"
            manager.grade = .inspector
            manager.isEnabled = value
            try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
                manager.saveToPreferences { error in error.map { c.resume(throwing: $0) } ?? c.resume() }
            }
            enabled = value
            status = value ? "NetworkExtension enabled" : "Collector fallback"
        } catch { status = error.localizedDescription }
    }
}
