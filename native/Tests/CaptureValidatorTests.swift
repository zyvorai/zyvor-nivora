// SPDX-License-Identifier: BUSL-1.1
import XCTest

final class CaptureValidatorTests: XCTestCase {
    private let ifaces: Set<String> = ["en0", "lo0", "utun4"]

    private func plan(_ r: CaptureRequest) throws -> CaptureValidator.Plan {
        try CaptureValidator.plan(for: r, knownInterfaces: ifaces)
    }

    func testDefaultsAreHeadersOnlyAndBounded() throws {
        let p = try plan(CaptureRequest(op: "start", iface: "en0"))
        XCTAssertEqual(p.snaplen, 96)
        XCTAssertEqual(p.seconds, 60)
        XCTAssertEqual(p.maxBytes, 16 * 1_048_576)
        XCTAssertEqual(p.filterText, "all traffic")
    }

    func testFilterIsBuiltFromClosedTokens() throws {
        let p = try plan(CaptureRequest(op: "start", iface: "en0", host: "142.250.183.14", port: 443, proto: "tcp"))
        XCTAssertEqual(p.filterTokens, ["host", "142.250.183.14", "and", "tcp", "and", "port", "443"])
        let argv = CaptureValidator.argv(p, outputPath: "/x/y.pcap")
        XCTAssertEqual(Array(argv.prefix(8)), ["-n", "-p", "-i", "en0", "-s", "96", "-w", "/x/y.pcap"])
        XCTAssertEqual(argv.last, "443")
    }

    func testRejectsInjectionAndOutOfRange() {
        let bad: [CaptureRequest] = [
            CaptureRequest(op: "start", iface: "en0; rm -rf /"),
            CaptureRequest(op: "start", iface: "../en0"),
            CaptureRequest(op: "start", iface: "en9"),                       // not on this Mac
            CaptureRequest(op: "start", iface: "en0", host: "example.com"),
            CaptureRequest(op: "start", iface: "en0", host: "1.2.3.4 or port 22"),
            CaptureRequest(op: "start", iface: "en0", proto: "ip proto 47"),
            CaptureRequest(op: "start", iface: "en0", port: 70000),
            CaptureRequest(op: "start", iface: "en0", port: 53, proto: "icmp"),
            CaptureRequest(op: "start", iface: "en0", snaplen: 65535),
            CaptureRequest(op: "start", iface: "en0", seconds: 3600),
            CaptureRequest(op: "start", iface: "en0", maxMB: 4096),
            CaptureRequest(op: "start"),
        ]
        for r in bad {
            XCTAssertThrowsError(try plan(r), "\(r)")
        }
    }

    func testSessionIDsAndLiteralIPs() {
        XCTAssertTrue(CaptureValidator.isSessionID("0123456789abcdef"))
        for bad in ["", "../etc/passwd", "0123456789ABCDEF", "short"] { XCTAssertFalse(CaptureValidator.isSessionID(bad)) }
        XCTAssertTrue(CaptureValidator.isLiteralIP("2001:db8::7"))
        XCTAssertFalse(CaptureValidator.isLiteralIP("localhost"))
    }

    func testRequestWireNamesMatchCollector() throws {
        let data = try JSONEncoder().encode(CaptureRequest(op: "start", iface: "en0", maxMB: 8))
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(obj["max_mb"] as? Int, 8)
    }
}
