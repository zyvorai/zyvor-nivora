// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Turns an untrusted `CaptureRequest` into a fixed tcpdump argv. No shell, no free-form BPF:
/// every value is parsed into a closed set of tokens, so nothing user-controlled reaches tcpdump as syntax.
enum CaptureValidator {
    enum Failure: Error, Equatable, CustomStringConvertible {
        case invalid(String)
        var description: String { if case .invalid(let m) = self { return m } else { return "invalid" } }
    }

    static let defaultSnaplen = 96, maxSnaplen = 256, minSnaplen = 54
    static let defaultSeconds = 60, maxSeconds = 300
    static let defaultMB = 16, maxMB = 64
    static let protocols: Set<String> = ["tcp", "udp", "icmp", "any"]

    struct Plan: Equatable {
        let iface: String
        let filterTokens: [String]
        let snaplen: Int
        let seconds: Int
        let maxBytes: Int
        var filterText: String { filterTokens.isEmpty ? "all traffic" : filterTokens.joined(separator: " ") }
    }

    static func isInterfaceName(_ s: String) -> Bool {
        // en0, utun4, bridge100, lo0, awdl0 ...
        guard (2...16).contains(s.count) else { return false }
        let letters = s.prefix { $0.isLetter && $0.isASCII }
        let digits = s.dropFirst(letters.count)
        return !letters.isEmpty && letters.allSatisfy { $0.isLowercase } && !digits.isEmpty && digits.allSatisfy { $0.isNumber && $0.isASCII }
    }

    static func isLiteralIP(_ s: String) -> Bool {
        var v4 = in_addr(), v6 = in6_addr()
        return s.withCString { inet_pton(AF_INET, $0, &v4) == 1 || inet_pton(AF_INET6, $0, &v6) == 1 }
    }

    /// `knownInterfaces` is supplied by the caller (the helper passes getifaddrs; tests pass a fixed set).
    static func plan(for r: CaptureRequest, knownInterfaces: Set<String>) throws -> Plan {
        guard let iface = r.iface, isInterfaceName(iface) else { throw Failure.invalid("interface name is not valid") }
        guard knownInterfaces.contains(iface) else { throw Failure.invalid("unknown interface \(iface)") }
        var tokens: [String] = []
        if let host = r.host, !host.isEmpty {
            guard isLiteralIP(host) else { throw Failure.invalid("host must be a literal IP address") }
            tokens += ["host", host]
        }
        let proto = (r.proto ?? "any").lowercased()
        guard protocols.contains(proto) else { throw Failure.invalid("protocol must be tcp, udp, icmp or any") }
        if proto != "any" { tokens += tokens.isEmpty ? [proto] : ["and", proto] }
        if let port = r.port {
            guard (1...65535).contains(port) else { throw Failure.invalid("port out of range") }
            guard proto == "tcp" || proto == "udp" || proto == "any" else { throw Failure.invalid("ports apply to tcp/udp only") }
            tokens += tokens.isEmpty ? ["port", String(port)] : ["and", "port", String(port)]
        }
        let snaplen = r.snaplen ?? defaultSnaplen
        guard (minSnaplen...maxSnaplen).contains(snaplen) else { throw Failure.invalid("snaplen must be \(minSnaplen)-\(maxSnaplen) bytes") }
        let seconds = r.seconds ?? defaultSeconds
        guard (1...maxSeconds).contains(seconds) else { throw Failure.invalid("duration must be 1-\(maxSeconds) seconds") }
        let mb = r.maxMB ?? defaultMB
        guard (1...maxMB).contains(mb) else { throw Failure.invalid("size cap must be 1-\(maxMB) MB") }
        return Plan(iface: iface, filterTokens: tokens, snaplen: snaplen, seconds: seconds, maxBytes: mb * 1_048_576)
    }

    /// Fixed argv for `/usr/sbin/tcpdump`; the helper additionally enforces the time and size caps itself.
    static func argv(_ p: Plan, outputPath: String) -> [String] {
        ["-n", "-p", "-i", p.iface, "-s", String(p.snaplen), "-w", outputPath] + p.filterTokens
    }

    static func isSessionID(_ s: String) -> Bool {
        s.count == 16 && s.allSatisfy { $0.isHexDigit && ($0.isNumber || $0.isLowercase) }
    }
}
