// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension
import Network
import Darwin

struct FlowEvent: Codable, Identifiable {
    let id: String
    let timestamp: String
    let event: String
    let bundleID: String
    let process: String
    let pid: Int
    let proto: String
    let local: String
    let remote: String
    let bytesIn: Int
    let bytesOut: Int
    let interface: String

    enum CodingKeys: String, CodingKey {
        case id = "flow_id"
        case timestamp, event
        case bundleID = "bundle_id"
        case process, pid
        case proto = "protocol"
        case local, remote
        case bytesIn = "bytes_in"
        case bytesOut = "bytes_out"
        case interface
    }
}

/// Who owns a flow. identity comes from the source audit token (macOS has no bundle-id property on flows).
struct SourceApp: Equatable {
    let pid: Int
    let name: String
    let bundleID: String

    /// Best human-readable identity for rule matching (bundle id when known, else process name).
    var identifier: String { bundleID.isEmpty ? name : bundleID }

    /// `audit_token_t` is eight 32-bit words; word 5 is the pid.
    static func pid(fromAuditToken data: Data?) -> Int? {
        guard let data, data.count >= MemoryLayout<audit_token_t>.size else { return nil }
        var token = audit_token_t()
        withUnsafeMutableBytes(of: &token) { _ = data.copyBytes(to: $0, count: MemoryLayout<audit_token_t>.size) }
        return Int(token.val.5)
    }

    static func resolve(pid: Int) -> SourceApp {
        var buffer = [CChar](repeating: 0, count: 4096)
        let length = proc_pidpath(Int32(pid), &buffer, UInt32(buffer.count))
        guard length > 0 else { return SourceApp(pid: pid, name: "pid \(pid)", bundleID: "") }
        let path = String(decoding: buffer.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }, as: UTF8.self)
        return SourceApp(pid: pid, name: (path as NSString).lastPathComponent, bundleID: bundleID(forExecutable: path))
    }

    /// Walks up to the enclosing `.app` and reads its bundle identifier.
    static func bundleID(forExecutable path: String) -> String {
        var url = URL(fileURLWithPath: path)
        while url.path != "/" {
            if url.pathExtension == "app" { return Bundle(url: url)?.bundleIdentifier ?? "" }
            url.deleteLastPathComponent()
        }
        return ""
    }

    static func of(_ flow: NEFilterFlow) -> SourceApp {
        let token = flow.sourceAppAuditToken ?? flow.sourceProcessAuditToken
        guard let pid = pid(fromAuditToken: token) else { return SourceApp(pid: 0, name: "Unknown", bundleID: "") }
        return resolve(pid: pid)
    }
}

enum FlowIdentity {
    static func id(for flow: NEFilterFlow) -> String { flow.identifier.uuidString.lowercased() }

    /// "host:port" or "[v6]:port". Takes `Any?` because the SDK types flow endpoints as either
    /// `Network.NWEndpoint` or `nw_endpoint_t` depending on the Xcode version.
    static func describe(_ endpoint: Any?) -> String {
        guard let endpoint else { return "" }
        if let typed = endpoint as? NWEndpoint, case .hostPort(let host, let port) = typed {
            let text = "\(host)"
            return text.contains(":") ? "[\(text)]:\(port.rawValue)" : "\(text):\(port.rawValue)"
        }
        return String(describing: endpoint)
    }

    static func remote(of socket: NEFilterSocketFlow?) -> String {
        guard let socket else { return "" }
        if #available(macOS 15.0, *) {
            let text = describe(socket.remoteFlowEndpoint)
            if !text.isEmpty { return text }
        }
        return socket.remoteHostname ?? ""
    }

    static func local(of socket: NEFilterSocketFlow?) -> String {
        guard let socket else { return "" }
        if #available(macOS 15.0, *) { return describe(socket.localFlowEndpoint) }
        return ""
    }

    static func make(flow: NEFilterFlow, event: String, bytesIn: Int = 0, bytesOut: Int = 0) -> FlowEvent {
        let socket = flow as? NEFilterSocketFlow
        let app = SourceApp.of(flow)
        let proto: String
        if let socket {
            switch socket.socketProtocol {
            case Int32(IPPROTO_TCP): proto = "tcp"
            case Int32(IPPROTO_UDP): proto = "udp"
            default: proto = "ip"
            }
        } else {
            proto = "web"
        }
        return FlowEvent(
            id: id(for: flow),
            timestamp: ISO8601DateFormatter().string(from: Date()),
            event: event,
            bundleID: app.bundleID,
            process: app.name,
            pid: app.pid,
            proto: proto,
            local: local(of: socket),
            remote: remote(of: socket),
            bytesIn: bytesIn,
            bytesOut: bytesOut,
            interface: ""
        )
    }
}
