// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Wire protocol between the collector and the privileged capture helper: one JSON object per line.
/// The helper treats every field as untrusted and re-validates it with `CaptureValidator`.
struct CaptureRequest: Codable, Equatable {
    var op: String                 // start | stop | list | delete | fetch | status
    var id: String?                // session id for stop/delete/fetch
    var iface: String?
    var host: String?              // literal IP address only; never a hostname
    var port: Int?
    var proto: String?             // tcp | udp | icmp | any
    var snaplen: Int?
    var seconds: Int?
    var maxMB: Int?

    enum CodingKeys: String, CodingKey { case op, id, iface, host, port, proto, snaplen, seconds, maxMB = "max_mb" }
}

struct CaptureSession: Codable, Equatable, Identifiable {
    var id: String
    var iface: String
    var filter: String
    var snaplen: Int
    var started: String
    var seconds: Int
    var maxBytes: Int
    var state: String              // running | finished | stopped | failed
    var bytes: Int

    enum CodingKeys: String, CodingKey { case id, iface, filter, snaplen, started, seconds, maxBytes = "max_bytes", state, bytes }
}
