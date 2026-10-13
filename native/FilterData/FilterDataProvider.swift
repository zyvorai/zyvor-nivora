// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension

/// macOS content filter (system extension). New flows are reported and checked against leased rules;
/// byte counts arrive through `handle(_:)` on this same provider (macOS has no control provider).
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
        verdict.statisticsReportFrequency = .medium   // ~1 s byte-count reports via handle(_:)
        return verdict
    }

    override func handle(_ report: NEFilterReport) {
        let event: String
        switch report.event {
        case .newFlow: event = "new"
        case .dataDecision: event = "data"
        case .flowClosed: event = "closed"
        case .statistics: event = "statistics"
        @unknown default: event = "report"
        }
        guard let flow = report.flow else { return }
        EventWriter.shared.append(
            FlowIdentity.make(flow: flow, event: event,
                              bytesIn: Int(report.bytesInboundCount), bytesOut: Int(report.bytesOutboundCount))
        )
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

/// Lock-protected cache of the App Group rules file.
private final class RuleMatcher: @unchecked Sendable {
    static let shared = RuleMatcher()
    private var cached: [FilterRule] = []
    private var mtime: Date = .distantPast
    private let lock = NSLock()

    func shouldBlock(_ flow: NEFilterFlow) -> Bool {
        let rules = load()
        let source = SourceApp.of(flow)
        let socket = flow as? NEFilterSocketFlow
        let remote = FlowIdentity.remote(of: socket)
        let domain = flow.url?.host ?? socket?.remoteHostname ?? ""

        // Explicit allow is an escape hatch over a broader block.
        for rule in rules where rule.action == "allow" {
            if matches(rule, app: source, domain: domain, remote: remote) { return false }
        }
        for rule in rules where rule.action == "block" {
            if matches(rule, app: source, domain: domain, remote: remote) { return true }
        }
        return false
    }

    private func matches(_ rule: FilterRule, app: SourceApp, domain: String, remote: String) -> Bool {
        if let exp = rule.expires_at, let date = ISO8601DateFormatter().date(from: exp), date <= Date() { return false }
        if let a = rule.app, !(app.name.localizedCaseInsensitiveContains(a) || app.bundleID.localizedCaseInsensitiveContains(a)) { return false }
        if let d = rule.domain, !(domain == d || domain.hasSuffix("." + d) || remote.contains(d)) { return false }
        if let ip = rule.ip, !remote.contains(ip) { return false }
        if let p = rule.port, !remote.hasSuffix(":\(p)") { return false }
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
