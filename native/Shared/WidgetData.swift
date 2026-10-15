// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// What the widget and App Intents show: a few totals and the busiest apps from the latest sample.
/// No tokens, no process IDs or paths; absent readings stay absent.
struct WidgetData: Codable, Equatable {
    struct App: Codable, Equatable { var name: String; var bps: Double }
    var updated: Date
    var host: String
    var simulated: Bool
    var health: Int
    var download: Double        // bytes per second
    var upload: Double
    var flows: Int
    var findings: Int
    var topApps: [App]

    /// Older than this and the app is probably not running: say so instead of showing old numbers as current.
    static let staleAfter: TimeInterval = 120

    func isStale(now: Date = Date()) -> Bool { now.timeIntervalSince(updated) > Self.staleAfter }

    func age(now: Date = Date()) -> String {
        let s = Int(max(0, now.timeIntervalSince(updated)))
        return s < 60 ? "\(s) s ago" : s < 3600 ? "\(s / 60) min ago" : "\(s / 3600) h ago"
    }
}

/// The file the app writes and the widget reads.
///
/// The widget extension is sandboxed, so it reads from its own container. The app is not sandboxed, so it
/// writes into that container, and only once the widget has run and created it (it never creates it).
/// A signed build with an App Group can move this without changing the model.
enum WidgetStore {
    static let widgetBundleID = "dev.zyvor.nivora.widgets"
    static let fileName = "widget.json"

    static var sandboxed: Bool { ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] != nil }

    /// Directory holding the file, or nil when the widget's container does not exist yet.
    static func directory(home: URL = FileManager.default.homeDirectoryForCurrentUser, sandboxed: Bool = WidgetStore.sandboxed) -> URL? {
        if sandboxed {
            return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?
                .appendingPathComponent("Nivora", isDirectory: true)
        }
        let container = home.appendingPathComponent("Library/Containers/\(widgetBundleID)/Data", isDirectory: true)
        guard FileManager.default.fileExists(atPath: container.path) else { return nil }
        return container.appendingPathComponent("Library/Application Support/Nivora", isDirectory: true)
    }

    static func encoder() -> JSONEncoder {
        let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601; e.outputFormatting = [.sortedKeys]; return e
    }
    static func decoder() -> JSONDecoder {
        let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601; return d
    }

    @discardableResult
    static func write(_ data: WidgetData, in directory: URL? = directory()) -> Bool {
        guard let dir = directory else { return false }
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            try encoder().encode(data).write(to: dir.appendingPathComponent(fileName), options: .atomic)
            return true
        } catch { return false }
    }

    static func read(in directory: URL? = directory()) -> WidgetData? {
        guard let dir = directory, let raw = try? Data(contentsOf: dir.appendingPathComponent(fileName)) else { return nil }
        return try? decoder().decode(WidgetData.self, from: raw)
    }
}
