// SPDX-License-Identifier: BUSL-1.1
import Darwin
import Foundation
import SystemConfiguration

/// Privileged capture helper (root launchd daemon, registered through SMAppService).
///
/// It exposes a tiny JSON-lines protocol on a unix socket, validates every request with `CaptureValidator`,
/// and only ever executes `/usr/sbin/tcpdump` with a fixed argv: no shell and no caller-supplied BPF.
/// Captures are headers-only by default (snaplen 96), time and size capped, stored root-owned (0600) and
/// retained for 24 hours. This file is compile-verified only; it has not been run under a signed install.
final class Helper: @unchecked Sendable {
    static let tcpdump = "/usr/sbin/tcpdump"
    static let retention: TimeInterval = 24 * 3600

    private let socketPath: String
    private let directory: String
    private let lock = NSLock()
    private var sessions: [String: CaptureSession] = [:]
    private var processes: [String: Process] = [:]
    private var stopRequested: Set<String> = []

    init(socketPath: String, directory: String) {
        self.socketPath = socketPath
        self.directory = directory
    }

    // MARK: server

    func run() -> Never {
        try? FileManager.default.createDirectory(atPath: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        chmod(directory, 0o700)
        purgeExpired()
        unlink(socketPath)
        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { fputs("socket failed\n", stderr); exit(1) }
        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let bytes = Array(socketPath.utf8CString)
        guard bytes.count <= MemoryLayout.size(ofValue: addr.sun_path) else { fputs("socket path too long\n", stderr); exit(1) }
        withUnsafeMutableBytes(of: &addr.sun_path) { raw in
            for (i, b) in bytes.enumerated() { raw[i] = UInt8(bitPattern: b) }
        }
        let bound = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
        }
        guard bound == 0, listen(fd, 8) == 0 else { fputs("bind/listen failed\n", stderr); exit(1) }
        // World-connectable on purpose; every connection is authorised by peer credentials below.
        chmod(socketPath, 0o666)
        let queue = DispatchQueue(label: "nivora.capture.clients", attributes: .concurrent)
        while true {
            let client = accept(fd, nil, nil)
            if client < 0 { continue }
            queue.async { self.serve(client) }
        }
    }

    private func consoleUID() -> uid_t? {
        var uid: uid_t = 0
        guard SCDynamicStoreCopyConsoleUser(nil, &uid, nil) != nil else { return nil }
        return uid
    }

    private func authorised(_ fd: Int32) -> Bool {
        var uid: uid_t = 0, gid: gid_t = 0
        guard getpeereid(fd, &uid, &gid) == 0 else { return false }
        return uid == 0 || uid == consoleUID()
    }

    private func serve(_ fd: Int32) {
        defer { close(fd) }
        guard authorised(fd) else { send(fd, ["ok": false, "error": "not authorised"]); return }
        var buffer = Data()
        var byte: UInt8 = 0
        while buffer.count < 4096, read(fd, &byte, 1) == 1, byte != 0x0A { buffer.append(byte) }
        guard let request = try? JSONDecoder().decode(CaptureRequest.self, from: buffer) else {
            send(fd, ["ok": false, "error": "malformed request"]); return
        }
        switch request.op {
        case "status":
            send(fd, ["ok": true, "tcpdump": FileManager.default.isExecutableFile(atPath: Helper.tcpdump), "max_seconds": CaptureValidator.maxSeconds])
        case "list":
            purgeExpired()
            send(fd, ["ok": true, "sessions": snapshotSessions().map(encodeSession)])
        case "start":
            start(request, fd)
        case "stop":
            guard let id = request.id, CaptureValidator.isSessionID(id) else { send(fd, ["ok": false, "error": "invalid id"]); return }
            stop(id); send(fd, ["ok": true])
        case "delete":
            guard let id = request.id, CaptureValidator.isSessionID(id) else { send(fd, ["ok": false, "error": "invalid id"]); return }
            stop(id); remove(id); send(fd, ["ok": true])
        case "fetch":
            guard let id = request.id, CaptureValidator.isSessionID(id) else { send(fd, ["ok": false, "error": "invalid id"]); return }
            fetch(id, fd)
        default:
            send(fd, ["ok": false, "error": "unknown operation"])
        }
    }

    // MARK: operations

    private func interfaces() -> Set<String> {
        var out = Set<String>()
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0 else { return out }
        defer { freeifaddrs(head) }
        var p = head
        while let cur = p {
            out.insert(String(cString: cur.pointee.ifa_name))
            p = cur.pointee.ifa_next
        }
        return out
    }

    private func start(_ request: CaptureRequest, _ fd: Int32) {
        let plan: CaptureValidator.Plan
        do { plan = try CaptureValidator.plan(for: request, knownInterfaces: interfaces()) }
        catch { send(fd, ["ok": false, "error": "\(error)"]); return }
        guard FileManager.default.isExecutableFile(atPath: Helper.tcpdump) else { send(fd, ["ok": false, "error": "tcpdump not found"]); return }
        lock.lock()
        if sessions.values.contains(where: { $0.state == "running" }) {
            lock.unlock(); send(fd, ["ok": false, "error": "a capture is already running"]); return
        }
        var raw = [UInt8](repeating: 0, count: 8)
        arc4random_buf(&raw, raw.count)
        let id = raw.map { String(format: "%02x", $0) }.joined()
        let path = "\(directory)/\(id).pcap"
        let session = CaptureSession(id: id, iface: plan.iface, filter: plan.filterText, snaplen: plan.snaplen,
                                     started: ISO8601DateFormatter().string(from: Date()), seconds: plan.seconds,
                                     maxBytes: plan.maxBytes, state: "running", bytes: 0)
        sessions[id] = session
        lock.unlock()

        let process = Process()
        process.executableURL = URL(fileURLWithPath: Helper.tcpdump)
        process.arguments = CaptureValidator.argv(plan, outputPath: path)
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        process.terminationHandler = { [weak self] proc in self?.finished(id, status: proc.terminationStatus, path: path) }
        do { try process.run() } catch {
            lock.lock(); sessions[id]?.state = "failed"; lock.unlock()
            send(fd, ["ok": false, "error": "could not start tcpdump"]); return
        }
        lock.lock(); processes[id] = process; lock.unlock()
        chmod(path, 0o600)
        DispatchQueue.global().async { [weak self] in self?.watch(id, path: path, deadline: Date().addingTimeInterval(TimeInterval(plan.seconds)), cap: plan.maxBytes) }
        send(fd, ["ok": true, "session": encodeSession(session)])
    }

    /// Enforces the duration and size caps independently of tcpdump's own flags.
    private func watch(_ id: String, path: String, deadline: Date, cap: Int) {
        while true {
            lock.lock(); let proc = processes[id]; lock.unlock()
            guard let proc, proc.isRunning else { return }
            let size = (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? Int) ?? 0
            lock.lock(); sessions[id]?.bytes = size; lock.unlock()
            if Date() >= deadline || size >= cap { proc.terminate(); return }
            Thread.sleep(forTimeInterval: 0.5)
        }
    }

    private func finished(_ id: String, status: Int32, path: String) {
        let size = (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? Int) ?? 0
        lock.lock()
        sessions[id]?.bytes = size
        if sessions[id]?.state == "running" {
            sessions[id]?.state = stopRequested.contains(id) ? "stopped" : (status == 0 || status == 15 || status == 2 ? "finished" : "failed")
        }
        processes[id] = nil
        lock.unlock()
    }

    private func stop(_ id: String) {
        lock.lock(); stopRequested.insert(id); let proc = processes[id]; lock.unlock()
        proc?.terminate()
    }

    private func remove(_ id: String) {
        lock.lock(); sessions[id] = nil; processes[id] = nil; stopRequested.remove(id); lock.unlock()
        unlink("\(directory)/\(id).pcap")
    }

    private func fetch(_ id: String, _ fd: Int32) {
        let path = "\(directory)/\(id).pcap"
        lock.lock(); let known = sessions[id] != nil; lock.unlock()
        guard known, let data = FileManager.default.contents(atPath: path) else { send(fd, ["ok": false, "error": "no such capture"]); return }
        send(fd, ["ok": true, "size": data.count])
        data.withUnsafeBytes { raw in
            var offset = 0
            while offset < raw.count {
                let n = write(fd, raw.baseAddress! + offset, raw.count - offset)
                if n <= 0 { break }
                offset += n
            }
        }
    }

    private func purgeExpired() {
        let cutoff = Date().addingTimeInterval(-Helper.retention)
        for name in (try? FileManager.default.contentsOfDirectory(atPath: directory)) ?? [] where name.hasSuffix(".pcap") {
            let path = "\(directory)/\(name)"
            if let m = (try? FileManager.default.attributesOfItem(atPath: path))?[.modificationDate] as? Date, m < cutoff {
                unlink(path)
                lock.lock(); sessions[String(name.dropLast(5))] = nil; lock.unlock()
            }
        }
    }

    // MARK: helpers

    private func snapshotSessions() -> [CaptureSession] {
        lock.lock(); defer { lock.unlock() }
        return sessions.values.sorted { $0.started > $1.started }
    }

    private func encodeSession(_ s: CaptureSession) -> [String: Any] {
        guard let data = try? JSONEncoder().encode(s),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        return obj
    }

    private func send(_ fd: Int32, _ object: [String: Any]) {
        guard var data = try? JSONSerialization.data(withJSONObject: object) else { return }
        data.append(0x0A)
        data.withUnsafeBytes { raw in
            var offset = 0
            while offset < raw.count {
                let n = write(fd, raw.baseAddress! + offset, raw.count - offset)
                if n <= 0 { break }
                offset += n
            }
        }
    }
}

let socketPath = ProcessInfo.processInfo.environment["NIVORA_CAPTURE_SOCKET"] ?? "/var/run/dev.zyvor.nivora.capture.sock"
let captureDirectory = ProcessInfo.processInfo.environment["NIVORA_CAPTURE_DIR"] ?? "/Library/Application Support/Nivora/captures"
Helper(socketPath: socketPath, directory: captureDirectory).run()
