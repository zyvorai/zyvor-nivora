// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Runs the bundled stdlib-only Python collector on loopback with a random in-memory token.
final class CollectorProcess {
    private var process: Process?
    /// 9857 when free, else the next free loopback port (a stale collector must not block a new launch).
    let port: Int = {
        for candidate in 9857..<9957 where CollectorProcess.isFree(candidate) { return candidate }
        return 9857
    }()

    private static func isFree(_ port: Int) -> Bool {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { return false }
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        return withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0 }
        }
    }
    let token = UUID().uuidString.replacingOccurrences(of: "-", with: "")

    func start(demo: Bool = false) throws {
        guard process == nil else { return }
        guard let resources = Bundle.main.resourceURL else { throw NSError(domain: "Nivora", code: 1, userInfo: [NSLocalizedDescriptionKey: "bundle resources missing"]) }
        let script = resources.appendingPathComponent("nivora.py")
        let web = resources.appendingPathComponent("web")
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw NSError(domain: "Nivora", code: 2, userInfo: [NSLocalizedDescriptionKey: "bundled nivora.py missing"])
        }
        let python = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"].first { FileManager.default.isExecutableFile(atPath: $0) }
        guard let python else { throw NSError(domain: "Nivora", code: 3, userInfo: [NSLocalizedDescriptionKey: "Python 3 was not found"])}
        let p = Process()
        p.executableURL = URL(fileURLWithPath: python)
        var args = [script.path, "--bind", "127.0.0.1", "--port", String(port), "--token", token, "--web-root", web.path, "--quiet", "--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
        if demo { args.append("--demo") }
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = resources.path
        env["PYTHONDONTWRITEBYTECODE"] = "1"   // never write __pycache__ into the (signed) app bundle
        p.environment = env
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        try p.run()
        process = p
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    deinit { stop() }
}
