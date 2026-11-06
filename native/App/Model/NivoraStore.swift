// SPDX-License-Identifier: BUSL-1.1
import AppKit
import Foundation
import SwiftUI

@MainActor
final class NivoraStore: ObservableObject {
    enum Status: Equatable { case starting, live, failed(String) }

    @Published private(set) var snapshot: NivoraSnapshot?
    @Published private(set) var history: [Sample] = []
    @Published private(set) var status: Status = .starting
    @Published var paused = false
    @Published var search = ""
    @Published var selectedApp: String?
    @Published var selectedFlow: String?
    @Published var pane: Pane? = {
        if CommandLine.arguments.contains("--section") { return NivoraApp.initialSection }
        return UserDefaults.standard.string(forKey: "nivora.pane").flatMap { Pane(rawValue: $0) } ?? .overview
    }() {
        didSet { if let pane { UserDefaults.standard.set(pane.rawValue, forKey: "nivora.pane") } }
    }
    @Published private(set) var baseline: (time: Date, flows: [NivoraSnapshot.Flow])?
    @Published private(set) var flowRates: [String: [Double]] = [:]
    @Published private(set) var appRates = RateHistory()

    func pinBaseline() { if let s = snapshot { baseline = (Date(), s.flows) } }
    func clearBaseline() { baseline = nil }
    @Published var exportError: String?
    @Published var investigatorAnswer = "Ask what is happening on this Mac."
    @Published var thresholdMbps: Double = UserDefaults.standard.double(forKey: "nivora.thresholdMbps") {
        didSet { UserDefaults.standard.set(thresholdMbps, forKey: "nivora.thresholdMbps") }
    }
    @Published var accent: AccentChoice = AccentChoice(rawValue: UserDefaults.standard.string(forKey: "nivora.accent") ?? "") ?? .blue {
        didSet { UserDefaults.standard.set(accent.rawValue, forKey: "nivora.accent") }
    }
    @Published var appearance: AppearanceChoice = AppearanceChoice(rawValue: UserDefaults.standard.string(forKey: "nivora.appearance") ?? "") ?? .auto {
        didSet { UserDefaults.standard.set(appearance.rawValue, forKey: "nivora.appearance") }
    }
    @Published private(set) var dismissed: Set<String> = []
    @Published private(set) var demo = CommandLine.arguments.contains("--demo")

    private let collector = CollectorProcess()
    private let widgetBridge = WidgetBridge()
    private var loop: Task<Void, Never>?
    private let maxSamples = 600
    private let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 5
        return URLSession(configuration: c)
    }()

    var alerts: [NivoraAlert] {
        guard let s = snapshot else { return [] }
        return AlertRules.compute(s, thresholdMbps: thresholdMbps).filter { !dismissed.contains($0.id) }
            .sorted { $0.severity > $1.severity }
    }
    func dismiss(_ id: String) { dismissed.insert(id) }

    var apps: [NivoraSnapshot.AppItem] {
        guard let s = snapshot else { return [] }
        let terms = FlowFilter.parse(search)
        return terms.isEmpty ? s.apps : s.apps.filter { FlowFilter.matches($0.filterSubject, terms) }
    }
    var flows: [NivoraSnapshot.Flow] {
        guard let s = snapshot else { return [] }
        let terms = FlowFilter.parse(search)
        return terms.isEmpty ? s.flows : s.flows.filter { FlowFilter.matches($0.filterSubject, terms) }
    }

    // MARK: saved views

    @Published private(set) var savedViews: [SavedView] = {
        guard let data = UserDefaults.standard.data(forKey: "nivora.savedViews"),
              let v = try? JSONDecoder().decode([SavedView].self, from: data) else { return [] }
        return SavedView.sanitized(v)
    }()

    func saveCurrentView() {
        let q = search.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return }
        let name = q.count > 28 ? String(q.prefix(27)) + "…" : q
        setViews(savedViews + [SavedView(name: name, query: q)])
    }
    func deleteView(_ v: SavedView) { setViews(savedViews.filter { $0 != v }) }
    func apply(_ v: SavedView) { search = v.query }
    private func setViews(_ views: [SavedView]) {
        savedViews = SavedView.sanitized(views)
        if let data = try? JSONEncoder().encode(savedViews) { UserDefaults.standard.set(data, forKey: "nivora.savedViews") }
    }

    // MARK: lifecycle

    /// The running store, for App Intents (they execute inside the app process).
    static weak var current: NivoraStore?

    private var startedAt = Date()

    func start() {
        NivoraStore.current = self
        guard loop == nil else { return }
        startedAt = Date()
        do { try collector.start(demo: demo) } catch { status = .failed(error.localizedDescription) }
        loop = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                if !self.paused { await self.refresh() }
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func stop() { loop?.cancel(); loop = nil; collector.stop() }

    func useDemo() { restart(demo: true) }
    func useThisMac() { restart(demo: false) }
    private func restart(demo: Bool) {
        stop(); self.demo = demo; snapshot = nil; history = []; status = .starting; start()
    }

    // MARK: API (loopback only; the token stays in memory)

    private func request(_ path: String, method: String = "GET", body: [String: Any]? = nil) async throws -> Data {
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(collector.port)/\(path)")!)
        req.httpMethod = method
        req.setValue("Bearer \(collector.token)", forHTTPHeaderField: "Authorization")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await session.data(for: req)
        guard let code = (response as? HTTPURLResponse)?.statusCode, (200..<300).contains(code) else { throw URLError(.badServerResponse) }
        return data
    }

    func refresh() async {
        do {
            let s = try JSONDecoder().decode(NivoraSnapshot.self, from: try await request("v1/snapshot"))
            snapshot = s
            DestinationPrompts.shared.consider(s)
            widgetBridge.publish(s)
            var rates = flowRates
            for f in s.flows { rates[f.id, default: []].append(f.total_bps); if rates[f.id]!.count > 60 { rates[f.id]!.removeFirst() } }
            for k in rates.keys where !s.flows.contains(where: { $0.id == k }) { rates[k] = nil }
            flowRates = rates
            var appBuf = appRates
            appBuf.record(Dictionary(s.apps.map { ($0.name, $0.total_bps) }, uniquingKeysWith: { a, b in a + b }))
            appRates = appBuf
            history.append(Sample(time: Date(), rx: s.traffic.rx_bps, tx: s.traffic.tx_bps, health: s.health.score, flows: s.flows.count))
            if history.count > maxSamples { history.removeFirst(history.count - maxSamples) }
            status = .live
        } catch {
            switch CollectorStartup.outcome(hasSnapshot: snapshot != nil, sinceStart: Date().timeIntervalSince(startedAt), message: error.localizedDescription) {
            case .keep: break
            case .starting: status = .starting
            case .failed(let message): status = .failed(message)
            }
        }
    }

    func ask(_ question: String) async {
        investigatorAnswer = "Investigating…"
        do {
            let data = try await request("v1/query", method: "POST", body: ["question": question])
            investigatorAnswer = try JSONDecoder().decode(QueryResponse.self, from: data).answer
        } catch { investigatorAnswer = error.localizedDescription }
    }

    /// Adds a rule for an app. `block` is leased for one hour by the collector unless made permanent.
    func addRule(action: String, app: String, destination: String? = nil) async {
        var body: [String: Any] = ["action": action, "app": app]
        if let d = destination, !d.isEmpty {
            // IP literals match `ip`; anything else is treated as a domain.
            body[d.contains(where: { $0.isLetter && $0 != ":" }) ? "domain" : "ip"] = d
        }
        _ = try? await request("v1/rules", method: "POST", body: body)
        await refresh()
    }

    /// Situation profiles only change alert posture; they never relax blocking rules or leases.
    func setProfile(_ name: String) async {
        _ = try? await request("v1/profiles", method: "POST", body: ["name": name])
        await refresh()
    }

    /// Plain-language status for Shortcuts and Siri.
    var statusSentence: String {
        guard let s = snapshot else { return "Nivora is still starting." }
        let top = s.apps.max { $0.total_bps < $1.total_bps }
        var out = "Network health is \(s.health.score) out of 100. Downloading \(rateString(s.traffic.rx_bps)), uploading \(rateString(s.traffic.tx_bps))."
        if let top, top.total_bps > 0 { out += " \(top.name) is the busiest app." }
        if !s.findings.isEmpty { out += " \(s.findings.count) finding\(s.findings.count == 1 ? "" : "s")." }
        return out
    }

    /// Top apps by live rate, as a sentence for Shortcuts and Siri.
    func topAppsSentence(limit: Int = 3) -> String {
        guard let s = snapshot else { return "Nivora is still starting." }
        let top = s.apps.filter { $0.total_bps > 0 }.sorted { $0.total_bps > $1.total_bps }.prefix(limit)
        if top.isEmpty { return "No application is moving noticeable traffic right now." }
        return "Busiest apps: " + top.map { "\($0.name) \(rateString($0.total_bps))" }.joined(separator: ", ") + "."
    }

    /// Deletes the block rules for an app (case-insensitive); returns how many were removed.
    @discardableResult
    func unblock(app: String) async -> Int {
        let ids = (snapshot?.rules ?? []).filter { $0.action == "block" && $0.app?.lowercased() == app.lowercased() }.map(\.id)
        for id in ids { await deleteRule(id) }
        return ids.count
    }

    func deleteRule(_ id: String) async {
        _ = try? await request("v1/rules/\(id)", method: "DELETE")
        await refresh()
    }

    /// The latest sample as JSON for Export.
    // MARK: packet capture (collector /v1/captures; helper is a separate privileged daemon)

    struct CaptureInfo: Decodable {
        let available: Bool
        let demo: Bool
        let sessions: [CaptureSession]
    }
    @Published private(set) var captures: CaptureInfo?
    @Published var captureError: String?

    func refreshCaptures() async {
        guard let data = try? await request("v1/captures"), let info = try? JSONDecoder().decode(CaptureInfo.self, from: data) else { return }
        captures = info
    }

    func startCapture(_ r: CaptureRequest) async {
        // Validate locally first so errors are immediate; the helper re-validates as the authority.
        let ifaces = Set(snapshot?.interfaces.map(\.name) ?? [])
        do { _ = try CaptureValidator.plan(for: r, knownInterfaces: ifaces) }
        catch { captureError = "\(error)"; return }
        var body: [String: Any] = ["iface": r.iface ?? "", "confirm": true]
        if let v = r.host, !v.isEmpty { body["host"] = v }
        if let v = r.port { body["port"] = v }
        if let v = r.proto { body["proto"] = v }
        if let v = r.snaplen { body["snaplen"] = v }
        if let v = r.seconds { body["seconds"] = v }
        if let v = r.maxMB { body["max_mb"] = v }
        do { _ = try await request("v1/captures", method: "POST", body: body) }
        catch { captureError = "The collector refused the capture. The helper may not be installed or approved." }
        await refreshCaptures()
    }

    func stopCapture(_ id: String) async {
        _ = try? await request("v1/captures/\(id)/stop", method: "POST", body: [:])
        await refreshCaptures()
    }

    func deleteCapture(_ id: String) async {
        _ = try? await request("v1/captures/\(id)", method: "DELETE")
        await refreshCaptures()
    }

    func downloadCapture(_ id: String) async {
        guard let data = try? await request("v1/captures/\(id)/pcap") else { captureError = "Could not fetch the capture."; return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "nivora-\(id).pcap"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { try data.write(to: url, options: .atomic) } catch { captureError = error.localizedDescription }
    }

    // MARK: time machine

    @Published private(set) var timeline: [NivoraSnapshot.Event] = []

    func refreshTimeline() async {
        guard let data = try? await request("v1/timeline"),
              let events = try? JSONDecoder().decode([NivoraSnapshot.Event].self, from: data) else { return }
        timeline = events
    }

    func exportSnapshotData() async -> Data? { try? await request("v1/snapshot") }

    /// Server-side export (`/v1/export`): honours the current filter and optional redaction, then asks where to save.
    func export(kind: String, format: String, redact: Bool, filtered: Bool = true) async {
        var items = [URLQueryItem(name: "kind", value: kind), URLQueryItem(name: "format", value: format)]
        let q = search.trimmingCharacters(in: .whitespaces)
        if filtered, !q.isEmpty, kind != "timeline" { items.append(URLQueryItem(name: "filter", value: q)) }
        if redact { items.append(URLQueryItem(name: "redact", value: "1")) }
        var comps = URLComponents(); comps.queryItems = items
        guard let data = try? await request("v1/export?" + (comps.percentEncodedQuery ?? "")) else {
            exportError = "Export failed. The collector did not return data."
            return
        }
        let stamp = Int(Date().timeIntervalSince1970)
        let ext = format == "zip" ? "zip" : format
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "nivora-\(kind)-\(stamp).\(ext)"
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { try data.write(to: url, options: .atomic) } catch { exportError = error.localizedDescription }
    }
}
