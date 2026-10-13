// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension

final class FilterDataProvider: NEFilterDataProvider {
    override func startFilter(completionHandler: @escaping (Error?) -> Void) {
        completionHandler(nil)
    }

    override func stopFilter(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        completionHandler()
    }

    override func handleNewFlow(_ flow: NEFilterFlow) -> NEFilterNewFlowVerdict {
        EventWriter.shared.append(FlowIdentity.make(flow: flow, event: "new"))
        let verdict: NEFilterNewFlowVerdict
        if RuleMatcher.shared.shouldBlock(flow) {
            verdict = .drop()
        } else {
            verdict = .allow()
        }
        verdict.shouldReport = true
        return verdict
    }
}

private struct FilterRule: Decodable {
    let id: String?
    let app: String?
    let domain: String?
    let ip: String?
    let port: Int?
    let action: String?
    let expires_at: String?
}

private final class RuleMatcher {
    static let shared = RuleMatcher()
    private var cached: [FilterRule] = []
    private var mtime: Date = .distantPast
    private let lock = NSLock()

    func shouldBlock(_ flow: NEFilterFlow) -> Bool {
        let rules = load()
        let app = flow.sourceAppIdentifier ?? ""
        let socket = flow as? NEFilterSocketFlow
        let domain = flow.url?.host ?? socket?.remoteHostname ?? ""
        let remote = socket.map { String(describing: $0.remoteEndpoint) } ?? ""

        // Explicit allow is an escape hatch over a broader block.
        for rule in rules where rule.action == "allow" {
            if matches(rule, app: app, domain: domain, remote: remote) { return false }
        }
        for rule in rules where rule.action == "block" {
            if matches(rule, app: app, domain: domain, remote: remote) { return true }
        }
        return false
    }

    private func matches(_ rule: FilterRule, app: String, domain: String, remote: String) -> Bool {
        if let exp = rule.expires_at, let date = ISO8601DateFormatter().date(from: exp), date <= Date() { return false }
        if let a = rule.app, !app.localizedCaseInsensitiveContains(a) { return false }
        if let d = rule.domain, !(domain == d || domain.hasSuffix("." + d) || remote.contains(d)) { return false }
        if let ip = rule.ip, !remote.contains(ip) { return false }
        if let p = rule.port, !remote.contains(":\(p)") { return false }
        return true
    }

    private func load() -> [FilterRule] {
        lock.lock(); defer { lock.unlock() }
        guard let base = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: NivoraShared.appGroup) else { return cached }
        let url = base.appendingPathComponent(NivoraShared.rulesFile)
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path), let changed = attrs[.modificationDate] as? Date else { return cached }
        if changed <= mtime { return cached }
        mtime = changed
        guard let data = try? Data(contentsOf: url), let parsed = try? JSONDecoder().decode([FilterRule].self, from: data) else { return cached }
        cached = parsed
        return cached
    }
}
