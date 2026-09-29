import CryptoKit
import Foundation
import Darwin

// The key is read from an owner-only file or the dedicated publish environment.
// No command prints private bytes. Verification takes an explicit trusted key.
enum SignError: Error { case arguments, key, domain, signature, size }
struct Envelope: Codable { let key_id: String; let payload_base64: String; let signature_base64: String }
func read(_ path: String, maximum: Int) throws -> Data {
    let url = URL(fileURLWithPath: path)
    let info = try url.resourceValues(forKeys: [.fileSizeKey, .isSymbolicLinkKey, .isRegularFileKey])
    guard info.isRegularFile == true, info.isSymbolicLink != true, (info.fileSize ?? Int.max) <= maximum else { throw SignError.size }
    return try Data(contentsOf: url)
}
func key(_ path: String) throws -> Curve25519.Signing.PrivateKey {
    let encoded: String
    if path == "environment" {
        guard let value = ProcessInfo.processInfo.environment["RERIME_SIGNING_KEY"] else { throw SignError.key }; encoded = value
    } else {
        let attributes = try FileManager.default.attributesOfItem(atPath: path)
        guard let mode = attributes[.posixPermissions] as? Int, mode & 0o077 == 0 else { throw SignError.key }
        encoded = String(decoding: try read(path, maximum: 256), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    guard let bytes = Data(base64Encoded: encoded), bytes.count == 32 else { throw SignError.key }
    return try Curve25519.Signing.PrivateKey(rawRepresentation: bytes)
}
let arguments = Array(CommandLine.arguments.dropFirst())
do {
    guard let command = arguments.first else { throw SignError.arguments }
    switch command {
    case "generate":
        guard arguments.count == 3 else { throw SignError.arguments }
        let value = Curve25519.Signing.PrivateKey()
        let fd = open(arguments[1], O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        guard fd >= 0 else { throw SignError.key }
        let output = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        try output.write(contentsOf: Data(value.rawRepresentation.base64EncodedString().utf8)); try output.synchronize(); try output.close()
        try Data(value.publicKey.rawRepresentation.base64EncodedString().utf8).write(to: URL(fileURLWithPath: arguments[2]), options: [.withoutOverwriting])
    case "public":
        guard arguments.count == 3 else { throw SignError.arguments }
        try Data(key(arguments[1]).publicKey.rawRepresentation.base64EncodedString().utf8).write(to: URL(fileURLWithPath: arguments[2]))
    case "sign":
        guard arguments.count == 6 else { throw SignError.arguments }
        let domain = arguments[3]
        guard ["rerime.precompiled.package.v1", "rerime.precompiled.channel.v1"].contains(domain) else { throw SignError.domain }
        let payload = try read(arguments[4], maximum: domain.contains("channel") ? 65_536 : 262_144)
        let privateKey = try key(arguments[1])
        let signature = try privateKey.signature(for: Data((domain + "\n").utf8) + payload)
        let value = Envelope(key_id: arguments[2], payload_base64: payload.base64EncodedString(), signature_base64: signature.base64EncodedString())
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        try encoder.encode(value).write(to: URL(fileURLWithPath: arguments[5]), options: [.withoutOverwriting])
    case "verify":
        guard arguments.count == 5 else { throw SignError.arguments }
        let encoded = String(decoding: try read(arguments[1], maximum: 256), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        guard let raw = Data(base64Encoded: encoded), raw.count == 32 else { throw SignError.key }
        let envelope = try JSONDecoder().decode(Envelope.self, from: read(arguments[4], maximum: 524_288))
        guard envelope.key_id == arguments[2], let payload = Data(base64Encoded: envelope.payload_base64),
              let signature = Data(base64Encoded: envelope.signature_base64), signature.count == 64,
              try Curve25519.Signing.PublicKey(rawRepresentation: raw).isValidSignature(signature, for: Data((arguments[3] + "\n").utf8) + payload) else { throw SignError.signature }
        print("PASS Ed25519 envelope")
    default: throw SignError.arguments
    }
} catch { fputs("Signing operation failed: \(error)\n", stderr); exit(1) }
