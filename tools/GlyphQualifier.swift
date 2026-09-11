import CoreText
import CryptoKit
import Foundation
import UIKit

// Public build executable. Evaluated text never appears in its output receipt.
enum QualificationError: Error { case arguments, runtime, shape, conversion, glyphs }

final class Glyphs {
    private let font = UIFont.systemFont(ofSize: 25, weight: .regular) as CTFont
    private var cache: [String: Bool] = [:]
    private var order: [String] = []
    private var cursor = 0
    func supports(_ text: String) -> Bool {
        guard !text.isEmpty, text.utf16.count <= 512 else { return false }
        if text.utf8.allSatisfy({ (32...126).contains($0) }) { return true }
        if let result = cache[text] { return result }
        let string = NSAttributedString(string: text, attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font])
        let line = CTLineCreateWithAttributedString(string)
        var valid = true, total = 0
        for case let run as CTRun in CTLineGetGlyphRuns(line) as NSArray {
            let attributes = CTRunGetAttributes(run) as NSDictionary
            guard let rawFont = attributes[kCTFontAttributeName] else { valid = false; continue }
            let name = CTFontCopyPostScriptName(rawFont as! CTFont) as String
            if name.localizedCaseInsensitiveContains("LastResort") || name.localizedCaseInsensitiveContains("ColorEmoji") { valid = false }
            let count = CTRunGetGlyphCount(run); total += count
            var glyphs = [CGGlyph](repeating: 0, count: count)
            if count > 0 { CTRunGetGlyphs(run, CFRange(location: 0, length: 0), &glyphs) }
            if glyphs.contains(0) { valid = false }
        }
        let result = valid && total > 0
        if order.count < 2048 { order.append(text) }
        else { cache.removeValue(forKey: order[cursor]); order[cursor] = text; cursor = (cursor + 1) % 2048 }
        cache[text] = result
        return result
    }
}

@main enum Qualifier {
    static func lines(_ file: URL, body: (Data) throws -> Void) throws {
        let stream = try FileHandle(forReadingFrom: file)
        defer { try? stream.close() }
        var pending = Data()
        while let chunk = try stream.read(upToCount: 65_536), !chunk.isEmpty {
            pending.append(chunk)
            try autoreleasepool {
                while let end = pending.firstIndex(of: 10) {
                    guard end - pending.startIndex <= 16_384 else { throw QualificationError.shape }
                    try body(Data(pending[..<end])); pending.removeSubrange(...end)
                }
            }
            guard pending.count <= 16_384 else { throw QualificationError.shape }
        }
        if !pending.isEmpty { try body(pending) }
    }
    static func digest(_ file: URL) throws -> String {
        let input = try FileHandle(forReadingFrom: file); defer { try? input.close() }
        var hash = SHA256()
        while let bytes = try input.read(upToCount: 262_144), !bytes.isEmpty { hash.update(data: bytes) }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
    static func main() throws {
        guard CommandLine.arguments.count == 3 else { throw QualificationError.arguments }
        let version = UIDevice.current.systemVersion.split(separator: ".").prefix(2).joined(separator: ".")
        guard version == "26.5" else { throw QualificationError.runtime }
        let source = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let destination = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
        try FileManager.default.copyItem(at: source, to: destination)
        guard let converter = opencc_open(source.appendingPathComponent("opencc/s2t.json").path),
              converter != UnsafeMutableRawPointer(bitPattern: -1) else { throw QualificationError.conversion }
        defer { opencc_close(converter) }
        let glyphs = Glyphs()
        guard let enumeration = FileManager.default.enumerator(at: source, includingPropertiesForKeys: [.isRegularFileKey]) else { throw QualificationError.shape }
        let files = enumeration.compactMap { $0 as? URL }.filter { $0.lastPathComponent.hasSuffix(".dict.yaml") }.sorted { $0.path < $1.path }
        var report: [[String: Any]] = [], total = 0, excludedTotal = 0
        for file in files {
            let path = String(file.path.dropFirst(source.path.count + 1))
            let target = destination.appendingPathComponent(path)
            let output = try FileHandle(forWritingTo: target); try output.truncate(atOffset: 0)
            var header = true, rows = 0, excluded = 0, buffer = Data()
            try lines(file) { data in
                guard let text = String(data: data, encoding: .utf8) else { throw QualificationError.shape }
                if header {
                    buffer.append(data); buffer.append(10)
                    if text == "..." { header = false }
                } else if !text.isEmpty && !text.hasPrefix("#") {
                    guard let first = text.split(separator: "\t", omittingEmptySubsequences: false).first else { throw QualificationError.shape }
                    let original = String(first); rows += 1
                    var supported = glyphs.supports(original)
                    if supported {
                        guard let converted = original.withCString({ opencc_convert_utf8(converter, $0, original.utf8.count) }) else {
                            throw QualificationError.conversion
                        }
                        supported = glyphs.supports(String(cString: converted)); opencc_convert_utf8_free(converted)
                    }
                    if supported { buffer.append(data); buffer.append(10) } else { excluded += 1 }
                }
                if buffer.count >= 65_536 { try output.write(contentsOf: buffer); buffer.removeAll(keepingCapacity: true) }
            }
            try output.write(contentsOf: buffer); try output.close()
            guard !header, rows == 0 || rows > excluded else { throw QualificationError.glyphs }
            report.append(["path": path, "rows": rows, "excluded": excluded, "sha256": try digest(target)])
            total += rows; excludedTotal += excluded
            print("qualified files=\(report.count) rows=\(total) excluded=\(excludedTotal)")
        }
        let receipt: [String: Any] = ["format_version": 1, "glyph_policy_version": 1, "platform": "iOS Simulator",
            "qualified_os": [version], "font_size": 25, "checks": "original-and-opencc-traditional-no-color-emoji",
            "rows": total, "excluded": excludedTotal, "files": report]
        let data = try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys, .withoutEscapingSlashes])
        try data.write(to: destination.appendingPathComponent("qualification.json"))
    }
}
