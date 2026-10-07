// Scan photos on-device with Apple Vision (no upload, no API cost): labels or text.
//
//   swiftc -O vision_scan.swift -o ~/.local/bin/vision_scan   # not under /tmp: there --text fails (e5rtError 13)
//   ./vision_scan [--text | --text-fast] FOLDER_OR_FILE... > out.tsv
//
// One line per image: path<TAB>result. Unreadable images get "ERROR".
//   default      what the photo shows: label:confidence,... (best first, >= 0.1). 1,303 labels exist,
//                e.g. document, printed_page, passport, screenshot, receipt, handwriting.
//                awk -F'\t' '$2 ~ /(document|printed_page|passport):0\.[3-9]/' out.tsv
//   --text       text in the photo, lines joined by " | ". Reads textLanguages (English, French);
//                no Khmer. grep -i 'carnet' out.tsv
//                UNRELIABLE on macOS 27.0: after a few dozen images every request can start failing
//                with e5rtError 13 (seen: 569 of 1,181 read, even in 25-image batches). Check the
//                ERROR count; for large jobs prefer --text-fast or Cloud Vision (ocr_tools/ocr_images.py).
//   --text-fast  same, much faster and reliable, misses small or skewed text.
import Foundation
import ImageIO
import Vision

enum Mode { case labels, text, textFast }

let imageExtensions: Set<String> = ["heic", "jpg", "jpeg", "png"]
let minConfidence: Float = 0.1
let labelPixels = 512   // classification works fine from the embedded thumbnail
let textPixels = 2000   // text needs real resolution
let textLanguages = ["en-US", "fr-FR"]

func imageFiles(under paths: [String]) -> [URL] {
    var found: [URL] = []
    for path in paths {
        let root = URL(fileURLWithPath: path)
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &isDir) else {
            FileHandle.standardError.write("not found: \(path)\n".data(using: .utf8)!)
            continue
        }
        let candidates = isDir.boolValue
            ? (FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])?
                .compactMap { $0 as? URL } ?? [])
            : [root]
        found += candidates.filter { imageExtensions.contains($0.pathExtension.lowercased()) }
    }
    return found.sorted { $0.path < $1.path }
}

func loadImage(_ url: URL, maxPixels: Int, fromEmbeddedThumbnail: Bool) -> CGImage? {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
    let sourceKey = fromEmbeddedThumbnail ? kCGImageSourceCreateThumbnailFromImageIfAbsent : kCGImageSourceCreateThumbnailFromImageAlways
    return CGImageSourceCreateThumbnailAtIndex(source, 0, [
        sourceKey: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: maxPixels,
    ] as CFDictionary)
}

func labels(_ image: CGImage) throws -> String {
    let request = VNClassifyImageRequest()
    try VNImageRequestHandler(cgImage: image).perform([request])
    return (request.results ?? [])
        .filter { $0.confidence >= minConfidence }
        .map { "\($0.identifier):\(String(format: "%.2f", $0.confidence))" }
        .joined(separator: ",")
}

func text(_ image: CGImage, fast: Bool) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = fast ? .fast : .accurate
    request.usesLanguageCorrection = false  // keep names and codes as printed
    // On macOS 27.0 accurate mode fails (e5rtError 13) with revision 3, and with revision 2
    // unless languages are set explicitly. Revision 2 + explicit languages works.
    // Set the revision first: setting it resets recognitionLanguages.
    if !fast { request.revision = VNRecognizeTextRequestRevision2 }
    request.recognitionLanguages = textLanguages
    try VNImageRequestHandler(cgImage: image).perform([request])
    return (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string.replacingOccurrences(of: "\t", with: " ") }
        .joined(separator: " | ")
}

func scan(_ url: URL, mode: Mode) -> String {
    let isLabels = mode == .labels
    guard let image = loadImage(url, maxPixels: isLabels ? labelPixels : textPixels, fromEmbeddedThumbnail: isLabels) else {
        return "ERROR"
    }
    do {
        switch mode {
        case .labels: return try labels(image)
        case .text: return try text(image, fast: false)
        case .textFast: return try text(image, fast: true)
        }
    } catch {
        return "ERROR \(error)".replacingOccurrences(of: "\n", with: " ")
    }
}

var args = Array(CommandLine.arguments.dropFirst())
var mode = Mode.labels
if let flag = args.first, flag.hasPrefix("--") {
    switch flag {
    case "--text": mode = .text
    case "--text-fast": mode = .textFast
    default:
        FileHandle.standardError.write("unknown option \(flag)\n".data(using: .utf8)!)
        exit(2)
    }
    args.removeFirst()
}
let files = imageFiles(under: args)
if files.isEmpty {
    FileHandle.standardError.write("usage: vision_scan [--text | --text-fast] FOLDER_OR_FILE... > out.tsv\n".data(using: .utf8)!)
    exit(2)
}
let outputLock = NSLock()
var done = 0
func emit(_ url: URL, _ result: String) {
    outputLock.lock()
    FileHandle.standardOutput.write("\(url.path)\t\(result)\n".data(using: .utf8)!)
    done += 1
    if done % 250 == 0 { FileHandle.standardError.write("\(done)/\(files.count)\n".data(using: .utf8)!) }
    outputLock.unlock()
}
// After a rebuild or cache clear, the first process to run text recognition compiles Vision's model
// into ~/Library/Caches/<binary name> and every request in that process fails (e5rtError 13); the
// next process works. So text mode first runs a throwaway child on one image to warm the cache.
if mode != .labels && ProcessInfo.processInfo.environment["VISION_SCAN_WARMUP"] == nil {
    let child = Process()
    child.executableURL = Bundle.main.executableURL
    child.arguments = [CommandLine.arguments[1], files[0].path]
    child.environment = ProcessInfo.processInfo.environment.merging(["VISION_SCAN_WARMUP": "1"]) { $1 }
    child.standardOutput = FileHandle.nullDevice
    child.standardError = FileHandle.nullDevice
    try? child.run()
    child.waitUntilExit()
}
DispatchQueue.concurrentPerform(iterations: files.count) { i in
    emit(files[i], scan(files[i], mode: mode))
}
