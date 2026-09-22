/// Builds documents from source text: indentation tree, then block ownership (SPEC §3–§4).
import Foundation

private final class TreeNode {
    var line: SourceLine
    var children: [TreeNode] = []
    /// The sibling before it, so a meta line can hand its body over.
    weak var previous: TreeNode?

    init(_ line: SourceLine, previous: TreeNode? = nil) {
        self.line = line
        self.previous = previous
    }
}

private func buildTree(_ lines: [SourceLine], _ diags: DiagnosticBag, _ file: String?) -> [TreeNode] {
    let root = TreeNode(SourceLine(0, 0, "", ""))
    var stack: [(indent: Int, parent: TreeNode)] = [(lines.first?.indent ?? 0, root)]
    var last: [TreeNode?] = [nil]
    for original in lines {
        var line: SourceLine = original
        while stack.count > 1, line.indent < stack[stack.count - 1].indent {
            stack.removeLast()
            last.removeLast()
        }
        if line.indent > stack[stack.count - 1].indent {
            var parent: TreeNode? = last[last.count - 1]
            while let current = parent, classify(current.line) == "meta", current.previous != nil {
                // a meta line is transparent: its body belongs to the block above
                parent = current.previous
            }
            if let parent {
                stack.append((line.indent, parent))
                last.append(nil)
            } else {
                diags.add("E004", "Unexpected indentation.", Span(line.number, 1, line.col0, file))
                line = SourceLine(line.number, stack[stack.count - 1].indent, line.text, line.raw)
            }
        } else if line.indent != stack[stack.count - 1].indent {
            diags.add("E004", "Inconsistent indentation.", Span(line.number, 1, line.col0, file))
            line = SourceLine(line.number, stack[stack.count - 1].indent, line.text, line.raw)
        }
        let node = TreeNode(line, previous: last[last.count - 1])
        stack[stack.count - 1].parent.children.append(node)
        last[last.count - 1] = node
    }
    return root.children
}

/// `format` | `format_timed` | `label` | `level` | `meta` | `other` — cheap look-ahead,
/// diagnostics discarded.
private func classify(_ line: SourceLine) -> String {
    let tokens: [Token] = Lexer.tokenize(line, DiagnosticBag(), nil)
    if tokens.isEmpty { return "other" }
    if let found = metaOrLabel(line, tokens, nil) {
        if found.kind == .meta { return "meta" }
        if levelLabels.contains(found.name) { return "level" }
        return found.kind == .label ? "label" : "other"
    }
    if isFormatStart(tokens) {
        return formatIsTimed(tokens) ? "format_timed" : "format"
    }
    return "other"
}

private func group(
    _ nodes: [TreeNode],
    _ diags: DiagnosticBag,
    _ file: String?,
    top: Bool,
    inLevel: Bool = false
) -> (statements: [Statement], levels: [BlockNode]) {
    var statements: [Statement] = []
    var levels: [BlockNode] = []
    let kinds: [String] = nodes.map { classify($0.line) }
    var firstFormatUsed: Bool = false
    var i: Int = 0
    while i < nodes.count {
        let node: TreeNode = nodes[i]
        let kind: String = kinds[i]
        let statement: Statement? = parseLine(node.line, diags, file, inLevel)
        i += 1
        guard let statement else { continue }
        guard let block = statement as? BlockNode else {
            if !node.children.isEmpty {
                let first: SourceLine = node.children[0].line
                diags.add(
                    "E004",
                    "Only a format or label line can have indented children.",
                    Span(first.number, first.col0, 0, file)
                )
                let inner = group(node.children, diags, file, top: false, inLevel: inLevel)
                statements.append(contentsOf: inner.statements)
                levels.append(contentsOf: inner.levels)
            }
            statements.append(statement)
            continue
        }

        let isLevel: Bool = kind == "level"
        var owned: [TreeNode] = []
        if !node.children.isEmpty {
            owned = node.children
        } else if !block.children.isEmpty {
            // inline content, e.g. "Odd: 10 Burpee"
        } else if isLevel {
            while i < nodes.count, kinds[i] != "level" {
                owned.append(nodes[i])
                i += 1
            }
        } else if top, !firstFormatUsed, !block.isLabel {
            // rule 2: the main format owns the rest of the body, up to the next timed format
            while i < nodes.count, kinds[i] != "level", kinds[i] != "format_timed" {
                owned.append(nodes[i])
                i += 1
            }
            firstFormatUsed = true
        } else {
            // a format block also owns the labels that follow it (Buy-in:, Odd:, …);
            // a label block stops at the next label, which starts a sibling of its own
            let stop: Set<String> = block.isLabel
                ? ["format", "format_timed", "label", "level"]
                : ["format", "format_timed", "level"]
            while i < nodes.count, !stop.contains(kinds[i]) {
                owned.append(nodes[i])
                i += 1
            }
            if i < nodes.count, kinds[i] == "format", !block.isLabel, owned.isEmpty {
                owned.append(nodes[i]) // "For time" directly followed by "21-15-9"
                i += 1
            }
        }
        if !owned.isEmpty {
            let inner = group(owned, diags, file, top: false, inLevel: inLevel || isLevel)
            block.children.append(contentsOf: inner.statements)
            levels.append(contentsOf: inner.levels)
        }
        if isLevel {
            levels.append(block)
        } else {
            statements.append(block)
        }
    }
    return (statements, levels)
}

private func makeBody(_ nodes: [TreeNode], _ diags: DiagnosticBag, _ file: String?) -> WorkoutBody {
    let grouped = group(nodes, diags, file, top: true)
    return WorkoutBody(grouped.statements, grouped.levels)
}

private func headingLevel(_ line: SourceLine) -> Int {
    let text: String = line.text
    guard text.hasPrefix("#") else { return 0 }
    var count: Int = 0
    for character in text {
        if character == "#" { count += 1 } else { break }
    }
    return count
}

func parseSource(_ source: String, _ file: String? = nil) -> (file: SourceFileNode, diags: DiagnosticBag) {
    let diags = DiagnosticBag()
    let split = Lexer.splitLines(source, diags, file)
    var documents: [DocumentNode] = []
    var current: [SourceLine] = []
    var title: String?
    var titleSpan = Span(1, 1, 0, file)

    func flush() {
        if current.isEmpty, title == nil { return }
        documents.append(makeDocument(title, titleSpan, current, diags, file))
    }

    for line in split.lines {
        let level: Int = headingLevel(line)
        if level == 1 {
            flush()
            current = []
            let stripped = String(Array(line.text).drop(while: { $0 == "#" }))
            title = stripped.trimmingCharacters(in: .whitespaces)
            titleSpan = Span(line.number, line.col0, 0, file)
            if line.indent > 0 {
                diags.add("E004", "A heading must start at the beginning of the line.", titleSpan)
            }
        } else {
            current.append(line)
        }
    }
    flush()
    return (SourceFileNode(documents, split.raw, file), diags)
}

private func makeDocument(
    _ title: String?,
    _ span: Span,
    _ lines: [SourceLine],
    _ diags: DiagnosticBag,
    _ file: String?
) -> DocumentNode {
    var sectionStarts: [Int] = []
    for (index, line) in lines.enumerated() where headingLevel(line) == 2 {
        sectionStarts.append(index)
    }
    if sectionStarts.isEmpty {
        let body = makeBody(buildTree(lines, diags, file), diags, file)
        return DocumentNode(title, span, body: body)
    }

    let preamble: [SourceLine] = Array(lines[0..<sectionStarts[0]])
    var meta: [MetaLine] = []
    for line in preamble {
        let statement: Statement? = parseLine(line, diags, file)
        if let metaLine = statement as? MetaLine {
            meta.append(metaLine)
        } else if statement != nil {
            diags.add(
                "E014",
                "Only meta lines are allowed between a session title and its first section.",
                Span(line.number, line.col0, 0, file),
                "move this line under a '## Section' heading"
            )
        }
    }
    var sections: [SectionNode] = []
    for (k, start) in sectionStarts.enumerated() {
        let end: Int = k + 1 < sectionStarts.count ? sectionStarts[k + 1] : lines.count
        let head: SourceLine = lines[start]
        let bodyLines: [SourceLine] = Array(lines[(start + 1)..<end])
        let stripped = String(Array(head.text).drop(while: { $0 == "#" }))
        let sectionTitle: String = stripped.trimmingCharacters(in: .whitespaces)
        let body = makeBody(buildTree(bodyLines, diags, file), diags, file)
        sections.append(SectionNode(sectionTitle, Span(head.number, head.col0, 0, file), body))
    }
    return DocumentNode(title, span, meta: meta, sections: sections)
}
