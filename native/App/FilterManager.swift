// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension
import SystemExtensions

/// Activates the bundled content-filter system extension, then enables the filter configuration.
/// Observe-first: nothing here runs until the person flips the toggle.
@MainActor
final class NivoraFilterManager: ObservableObject {
    static let extensionID = "dev.zyvor.nivora.filter"

    @Published var enabled = false
    @Published var status = "Collector fallback"

    private var activation: ActivationRequest?

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
        do {
            if value { try await activateExtension() }
            try await configure(enabled: value)
            enabled = value
            status = value ? "NetworkExtension enabled" : "Collector fallback"
        } catch {
            status = error.localizedDescription
            enabled = false
        }
    }

    private func configure(enabled value: Bool) async throws {
        let manager = NEFilterManager.shared()
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            manager.loadFromPreferences { error in error.map { c.resume(throwing: $0) } ?? c.resume() }
        }
        let config = NEFilterProviderConfiguration()
        config.filterSockets = true
        config.filterPackets = false
        manager.providerConfiguration = config
        manager.localizedDescription = "Nivora Network Intelligence"
        manager.isEnabled = value
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            manager.saveToPreferences { error in error.map { c.resume(throwing: $0) } ?? c.resume() }
        }
    }

    private func activateExtension() async throws {
        status = "Waiting for approval in System Settings…"
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            let request = ActivationRequest(identifier: Self.extensionID) { result in c.resume(with: result) }
            activation = request
            request.submit()
        }
        activation = nil
    }
}

/// Bridges `OSSystemExtensionRequest`'s delegate callbacks to a single completion.
private final class ActivationRequest: NSObject, OSSystemExtensionRequestDelegate, @unchecked Sendable {
    private let identifier: String
    private var completion: ((Result<Void, Error>) -> Void)?

    init(identifier: String, completion: @escaping (Result<Void, Error>) -> Void) {
        self.identifier = identifier
        self.completion = completion
    }

    func submit() {
        let request = OSSystemExtensionRequest.activationRequest(forExtensionWithIdentifier: identifier, queue: .main)
        request.delegate = self
        OSSystemExtensionManager.shared.submitRequest(request)
    }

    private func finish(_ result: Result<Void, Error>) {
        completion?(result)
        completion = nil
    }

    func request(_ request: OSSystemExtensionRequest, actionForReplacingExtension existing: OSSystemExtensionProperties,
                 withExtension ext: OSSystemExtensionProperties) -> OSSystemExtensionRequest.ReplacementAction { .replace }
    func requestNeedsUserApproval(_ request: OSSystemExtensionRequest) {}
    func request(_ request: OSSystemExtensionRequest, didFinishWithResult result: OSSystemExtensionRequest.Result) { finish(.success(())) }
    func request(_ request: OSSystemExtensionRequest, didFailWithError error: Error) { finish(.failure(error)) }
}
