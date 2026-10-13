// SPDX-License-Identifier: BUSL-1.1
import AppKit
import Foundation
import SwiftUI

enum PaneSection: String, CaseIterable, Identifiable {
    case monitor = "Monitor", network = "Network", zyvor = "Zyvor", system = "System"
    var id: Self { self }
}

enum Pane: String, CaseIterable, Identifiable {
    case overview = "Overview", health = "Health", applications = "Applications", flows = "Flows"
    case interfaces = "Interfaces", local = "Local Network"
    case fluxvm = "FluxVM", security = "Security", capture = "Capture", investigator = "Investigator"
    case alerts = "Alerts", settings = "Settings"
    var id: Self { self }
    var section: PaneSection {
        switch self {
        case .overview, .health, .applications, .flows: return .monitor
        case .interfaces, .local: return .network
        case .fluxvm, .security, .capture, .investigator: return .zyvor
        case .alerts, .settings: return .system
        }
    }
    var symbol: String {
        switch self {
        case .overview: return "gauge.with.dots.needle.bottom.50percent"
        case .health: return "heart.text.square"
        case .applications: return "square.stack.3d.up"
        case .flows: return "arrow.left.arrow.right"
        case .interfaces: return "network"
        case .local: return "macwindow.on.rectangle"
        case .fluxvm: return "shippingbox"
        case .security: return "lock.shield"
        case .capture: return "record.circle"
        case .investigator: return "sparkles"
        case .alerts: return "bell.badge"
        case .settings: return "gearshape"
        }
    }
    var subtitle: String {
        switch self {
        case .overview: return "What is talking to what, through which network"
        case .health: return "Route, DNS, latency, interfaces and safety"
        case .applications: return "Every app, its connections and traffic"
        case .flows: return "Live TCP and UDP conversations"
        case .interfaces: return "Wi‑Fi, Ethernet, VPN and virtual interfaces"
        case .local: return "Neighbors, listeners and exposure"
        case .fluxvm: return "VMs and sandboxes beside host traffic"
        case .security: return "Observe-first findings and rules"
        case .capture: return "Opt-in, headers-only packet capture"
        case .investigator: return "Ask the local telemetry"
        case .alerts: return "Findings and threshold checks"
        case .settings: return "Appearance, alerts and data"
        }
    }
}

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

    func start() {
        guard loop == nil else { return }
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
            history.append(Sample(time: Date(), rx: s.traffic.rx_bps, tx: s.traffic.tx_bps, health: s.health.score))
            if history.count > maxSamples { history.removeFirst(history.count - maxSamples) }
            status = .live
        } catch {
            if snapshot == nil { status = .failed(error.localizedDescription) }
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
    func addRule(action: String, app: String) async {
        _ = try? await request("v1/rules", method: "POST", body: ["action": action, "app": app])
        await refresh()
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
