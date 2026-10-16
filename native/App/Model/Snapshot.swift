// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// The collector's `/v1/snapshot` contract. Optional fields tolerate older/newer collectors.
struct NivoraSnapshot: Decodable {
    struct Host: Decodable { let name: String; let os: String; let release: String; let arch: String; let demo: Bool }
    struct AppItem: Decodable, Identifiable {
        var id: String { "\(name)-\(pid)" }
        let name: String; let pid: Int; let bundle_id: String?; let connections: Int
        let bytes_in: Int; let bytes_out: Int; let rx_bps: Double; let tx_bps: Double; let total_bps: Double
        let domains: [String]; let interfaces: [String]
        var total: Int { bytes_in + bytes_out }
    }
    struct Flow: Decodable, Identifiable {
        let id: String; let process: String; let pid: Int; let bundle_id: String?
        let `protocol`: String; let local: String; let remote: String; let state: String
        let bytes_in: Int; let bytes_out: Int; let rx_bps: Double; let tx_bps: Double; let total_bps: Double
        let interface: String; let rtt_ms: Double; let source: String
        let first_seen: String?
    }
    struct Interface: Decodable, Identifiable {
        var id: String { name }
        let name: String; let ipv4: [String]; let ipv6: [String]; let mac: String; let mtu: Int; let status: String; let kind: String
    }
    struct Finding: Decodable, Identifiable {
        var id: String { "\(kind)-\(title)-\(detail)" }
        let severity: String; let kind: String; let title: String; let detail: String
        let app: String?; let remote: String?
    }
    struct VPN: Decodable, Identifiable { var id: String { service_id }; let name: String; let service_id: String; let status: String; let active: Bool }
    struct DNS: Decodable { let servers: [String] }
    struct Capabilities: Decodable { let nettop: Bool; let network_extension: Bool; let fluxvm: Bool; let blocking: Bool }
    struct Traffic: Decodable { let rx_bps: Double; let tx_bps: Double; let total_bps: Double; let active_flows: Int; let internet_flows: Int; let vpn_flows: Int; let top_interface: String }
    struct Health: Decodable {
        struct Component: Decodable, Identifiable { var id: String { name }; let name: String; let score: Int; let detail: String }
        let score: Int; let status: String; let median_rtt_ms: Double; let components: [Component]
    }
    struct Neighbor: Decodable, Identifiable { let id: String; let family: String; let ip: String; let mac: String; let interface: String; let state: String }
    struct Listener: Decodable, Identifiable { let id: String; let process: String; let pid: Int; let `protocol`: String; let address: String; let port: Int; let state: String; let exposure: String }
    struct WiFi: Decodable { let interface: String?; let ssid: String? }
    struct Route: Decodable, Identifiable {
        var id: String { "\(family)-\(destination)-\(gateway)-\(interface)" }
        let family: String; let destination: String; let gateway: String; let interface: String; let flags: String; let `default`: Bool
    }
    struct Behavior: Decodable { let known_destinations: Int? }
    struct FluxVM: Decodable {
        struct Workload: Decodable, Identifiable {
            var id: String { ident ?? UUID().uuidString }; let ident: String?; let state: String?; let backend: String?
            enum CodingKeys: String, CodingKey { case ident = "id", state, status, backend }
            init(from decoder: Decoder) throws {
                let c = try decoder.container(keyedBy: CodingKeys.self)
                ident = try? c.decode(String.self, forKey: .ident)
                // FluxVM names it `status`; the collector copies it to `state`, but accept either.
                state = (try? c.decode(String.self, forKey: .state)) ?? (try? c.decode(String.self, forKey: .status))
                backend = try? c.decode(String.self, forKey: .backend)
            }
        }
        private struct Envelope: Decodable { let items: [Workload]? }
        private enum Keys: String, CodingKey { case connected, base_url, vms, sandboxes }
        let connected: Bool; let base_url: String?
        let vms: [Workload]?; let sandboxes: [Workload]?

        /// Tolerant on purpose: a shape this app does not expect in the optional FluxVM section must never make the
        /// whole snapshot undecodable (that shows "Collector unavailable" for a collector that is running fine).
        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: Keys.self)
            connected = (try? c.decode(Bool.self, forKey: .connected)) ?? false
            base_url = try? c.decode(String.self, forKey: .base_url)
            vms = Self.workloads(c, .vms)
            sandboxes = Self.workloads(c, .sandboxes)
        }

        private static func workloads(_ c: KeyedDecodingContainer<Keys>, _ key: Keys) -> [Workload]? {
            if let list = try? c.decode([Workload].self, forKey: key) { return list }
            return (try? c.decode(Envelope.self, forKey: key))?.items
        }
    }
    struct Event: Decodable, Identifiable {
        var id: String { "\(ts)-\(kind)-\(title)" }
        let ts: String; let kind: String; let title: String; let detail: String?
    }
    struct TrustItem: Decodable, Identifiable {
        struct Component: Decodable, Identifiable { var id: String { name }; let name: String; let points: Int; let max: Int; let detail: String }
        var id: String { app }
        let app: String; let score: Int; let level: String; let flows: Int; let components: [Component]
    }
    struct Privacy: Decodable {
        struct Tracker: Decodable, Identifiable { var id: String { "\(app)-\(host)" }; let app: String; let host: String; let category: String }
        struct Cleartext: Decodable, Identifiable { var id: String { "\(app)-\(host)-\(port)" }; let app: String; let host: String; let port: Int; let `protocol`: String }
        let score: Int; let trackers: [Tracker]; let cleartext: [Cleartext]
        let dns_vpn_leak: Bool; let unsigned_apps: [String]; let notes: [String]
    }
    struct Egress: Decodable {
        struct Destination: Decodable, Identifiable { var id: String { host }; let host: String; let count: Int; let scope: String }
        struct Workload: Decodable, Identifiable { var id: String { self.ident }; let ident: String; let kind: String; let external: Int; let destinations: [Destination]
            enum CodingKeys: String, CodingKey { case ident = "id", kind, external, destinations } }
        let connected: Bool; let workloads: [Workload]; let note: String?
    }
    struct Profile: Decodable { let name: String; let label: String }
    struct Rule: Decodable, Identifiable { let id: String; let action: String; let app: String?; let domain: String?; let ip: String?; let port: Int?; let expires_at: String? }

    let timestamp: String
    let host: Host
    let apps: [AppItem]
    let flows: [Flow]
    let interfaces: [Interface]
    let findings: [Finding]
    let vpn: [VPN]
    let dns: DNS
    let capabilities: Capabilities
    let traffic: Traffic
    let health: Health
    let neighbors: [Neighbor]
    let listeners: [Listener]
    let wifi: WiFi?
    let routes: [Route]?
    let behavior: Behavior?
    let fluxvm: FluxVM?
    let rules: [Rule]?
    let recent_events: [Event]?
    let trust: [TrustItem]?
    let privacy: Privacy?
    let egress: Egress?
    let profile: Profile?
}

struct QueryResponse: Decodable { let answer: String }

/// One point of rate history, kept by the store for charts.
struct Sample: Identifiable {
    let id = UUID()
    let time: Date
    let rx: Double
    let tx: Double
    let health: Int
    var flows: Int = 0
}

func byteString(_ value: Int) -> String {
    let f = ByteCountFormatter(); f.countStyle = .file
    f.allowsNonnumericFormatting = false   // "0 bytes", not "Zero KB"
    return f.string(fromByteCount: Int64(value))
}

func rateString(_ value: Double) -> String {
    let f = ByteCountFormatter(); f.countStyle = .file
    f.allowsNonnumericFormatting = false
    return f.string(fromByteCount: Int64(max(0, value))) + "/s"
}
