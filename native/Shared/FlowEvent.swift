// SPDX-License-Identifier: BUSL-1.1
import Foundation
import CryptoKit
import NetworkExtension
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

enum FlowIdentity {
    static func id(for flow: NEFilterFlow) -> String {
        var data = Data()
        if let token = flow.sourceProcessAuditToken { data.append(token) }
        if let bundle = flow.sourceAppIdentifier?.data(using: .utf8) { data.append(bundle) }
        if let url = flow.url?.absoluteString.data(using: .utf8) { data.append(url) }
        if let socket = flow as? NEFilterSocketFlow {
            let remote = String(describing: socket.remoteEndpoint)
            if let d = remote.data(using: .utf8) { data.append(d) }
        }
        let digest = SHA256.hash(data: data)
        return digest.prefix(10).map { String(format: "%02x", $0) }.joined()
    }

    static func endpoint(_ endpoint: Any?) -> String {
        guard let endpoint else { return "" }
        return String(describing: endpoint)
            .replacingOccurrences(of: "NWEndpoint.hostPort(host: ", with: "")
            .replacingOccurrences(of: ")", with: "")
    }

    static func make(flow: NEFilterFlow, event: String, bytesIn: Int = 0, bytesOut: Int = 0) -> FlowEvent {
        let socket = flow as? NEFilterSocketFlow
        let bundle = flow.sourceAppIdentifier ?? ""
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
            bundleID: bundle,
            process: bundle.isEmpty ? "Unknown" : bundle,
            pid: 0,
            proto: proto,
            local: endpoint(socket?.localEndpoint),
            remote: socket?.remoteHostname ?? endpoint(socket?.remoteEndpoint),
            bytesIn: bytesIn,
            bytesOut: bytesOut,
            interface: ""
        )
    }
}
