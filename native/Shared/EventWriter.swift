// SPDX-License-Identifier: BUSL-1.1
import Foundation

enum NivoraShared {
    static let appGroup = "group.dev.zyvor.nivora"
    static let flowLog = "flows.jsonl"
    static let rulesFile = "rules.json"
}

final class EventWriter {
    static let shared = EventWriter()
    private let queue = DispatchQueue(label: "dev.zyvor.nivora.event-writer")

    func append(_ event: FlowEvent) {
        queue.async {
            guard let base = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: NivoraShared.appGroup) else { return }
            let url = base.appendingPathComponent(NivoraShared.flowLog)
            guard let encoded = try? JSONEncoder().encode(event) else { return }
            var line = encoded
            line.append(0x0a)
            if !FileManager.default.fileExists(atPath: url.path) {
                FileManager.default.createFile(atPath: url.path, contents: line)
                return
            }
            guard let handle = try? FileHandle(forWritingTo: url) else { return }
            defer { try? handle.close() }
            do {
                try handle.seekToEnd()
                try handle.write(contentsOf: line)
                let attrs = try FileManager.default.attributesOfItem(atPath: url.path)
                if let size = attrs[.size] as? NSNumber, size.intValue > 16 * 1024 * 1024 {
                    try Self.rotate(url)
                }
            } catch { }
        }
    }

    private static func rotate(_ url: URL) throws {
        let data = try Data(contentsOf: url)
        let keep = data.suffix(8 * 1024 * 1024)
        try Data(keep).write(to: url, options: .atomic)
    }
}
