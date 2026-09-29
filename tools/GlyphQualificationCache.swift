import Foundation
import CryptoKit

/// Disposable build-host state. Never changes the signed qualification receipt.
final class GlyphQualificationCache {
    private let root: URL?
    private let context: String
    private(set) var hits = 0
    private(set) var misses = 0
    private let maximumBytes = 512 * 1024 * 1024

    init(source: URL) throws {
        let env = ProcessInfo.processInfo.environment
        root = env["RERIME_QUALIFICATION_CACHE"].map { URL(fileURLWithPath: $0, isDirectory: true) }
        let declared = env["RERIME_QUALIFICATION_CONTEXT"] ?? "disabled"
        // Runtime build and conversion inputs are part of identity, not just marketing OS.
        var parts = [declared, ProcessInfo.processInfo.operatingSystemVersionString]
        for name in ["s2t.json", "STCharacters.ocd2", "STPhrases.ocd2"] {
            parts.append(try Qualifier.digest(source.appendingPathComponent("opencc/" + name)))
        }
        context = Self.hash(Data(parts.joined(separator: "\n").utf8))
        if let root { try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true) }
    }
    private static func hash(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
    private func key(_ source: URL) throws -> String {
        Self.hash(Data((context + ":" + (try Qualifier.digest(source))).utf8))
    }
    func restore(source: URL, target: URL, path: String) -> [String: Any]? {
        guard let root else { misses += 1; return nil }
        do {
            let identity = try key(source)
            let metadata = root.appendingPathComponent(identity + ".json")
            let content = root.appendingPathComponent(identity + ".data")
            let info = try metadata.resourceValues(forKeys: [.fileSizeKey, .isSymbolicLinkKey])
            guard info.isSymbolicLink != true, (info.fileSize ?? Int.max) <= 4096,
                  let value = try JSONSerialization.jsonObject(with: Data(contentsOf: metadata)) as? [String: Any],
                  value["key"] as? String == identity,
                  let rows = value["rows"] as? Int, let excluded = value["excluded"] as? Int,
                  rows >= 0, excluded >= 0, excluded <= rows,
                  let size = try content.resourceValues(forKeys: [.fileSizeKey, .isSymbolicLinkKey]).fileSize,
                  size > 0, size <= maximumBytes,
                  try content.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink != true,
                  value["sha256"] as? String == (try Qualifier.digest(content)) else {
                misses += 1; return nil
            }
            try FileManager.default.removeItem(at: target)
            try FileManager.default.copyItem(at: content, to: target)
            try? FileManager.default.setAttributes([.modificationDate: Date()], ofItemAtPath: metadata.path)
            hits += 1
            return ["path": path, "rows": rows, "excluded": excluded, "sha256": value["sha256"]!]
        } catch { misses += 1; return nil }
    }
    func store(source: URL, qualified: URL, report: [String: Any]) {
        guard let root else { return }
        do {
            let identity = try key(source)
            let data = try Data(contentsOf: qualified)
            guard data.count <= maximumBytes else { return }
            try data.write(to: root.appendingPathComponent(identity + ".data"), options: .atomic)
            let metadata: [String: Any] = ["key": identity, "sha256": Self.hash(data),
                "rows": report["rows"]!, "excluded": report["excluded"]!]
            try JSONSerialization.data(withJSONObject: metadata, options: [.sortedKeys]).write(
                to: root.appendingPathComponent(identity + ".json"), options: .atomic)
            trim()
        } catch { /* Cache failure must not fail qualification. */ }
    }
    private func trim() {
        guard let root, let files = try? FileManager.default.contentsOfDirectory(at: root,
            includingPropertiesForKeys: [.fileSizeKey, .contentModificationDateKey]) else { return }
        let records = files.compactMap { file -> (URL, Int, Date)? in
            guard let values = try? file.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey]) else { return nil }
            return (file, values.fileSize ?? 0, values.contentModificationDate ?? .distantPast)
        }.sorted { $0.2 < $1.2 }
        var total = records.reduce(0) { $0 + $1.1 }
        for (file, size, _) in records where total > maximumBytes {
            try? FileManager.default.removeItem(at: file); total -= size
        }
    }
}
