// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Runs the bundled stdlib-only Python collector on loopback with a random in-memory token.
final class CollectorProcess {
    private var process: Process?
    let port = 9857
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
        var args = [script.path, "--bind", "127.0.0.1", "--port", String(port), "--token", token, "--web-root", web.path, "--quiet"]
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
