/// Markdown rendering, for blogs, chat and documentation.
///
/// A port of `src/wodcraft/emit/markdown.py`. The block body is the whiteboard renderer at a
/// width of 40, inside a fenced code block.
import Foundation

public enum Markdown {
    /// The Markdown text of a document.
    public static func render(_ document: Document) -> String {
        switch document {
        case let .session(session):
            var lines: [String] = ["# " + (session.title ?? "Session")]
            var head: [String] = []
            if let date = session.date, !date.isEmpty { head.append(date) }
            if let time = session.time, !time.isEmpty { head.append(time) }
            if !head.isEmpty {
                lines.append("")
                lines.append("*" + head.joined(separator: " · ") + "*")
            }
            for section in session.sections {
                lines.append("")
                lines.append("## " + section.title)
                lines.append("")
                lines.append(workoutBody(section.workout))
            }
            var text = lines.joined(separator: "\n")
            while let last = text.last, last == " " || last == "\n" || last == "\t" || last == "\r" {
                text.removeLast()
            }
            return text + "\n"
        case let .workout(workout):
            return "# " + (workout.title ?? "Workout") + "\n\n" + workoutBody(workout) + "\n"
        }
    }

    static func workoutBody(_ workout: Workout) -> String {
        var lines: [String] = ["```"]
        for block in workout.blocks {
            lines.append(contentsOf: Board.blockLines(block, depth: 0, width: 40))
        }
        lines.append("```")
        let meta = workout.meta
        let score = workout.score.type
        if score != Score.Kind.none {
            lines.append("")
            lines.append("**Score** — " + Board.scoreLabel(score))
        }
        if let estimate = workout.estimate {
            lines.append("**Estimate** — " + Board.rangeText(estimate))
        }
        for stimulus in meta?.stimulus ?? [] {
            lines.append("")
            lines.append("> " + stimulus)
        }
        for note in meta?.notes ?? [] {
            lines.append("")
            lines.append("*" + note + "*")
        }
        return lines.joined(separator: "\n")
    }
}

// MARK: - Sugar

public extension Workout {
    /// The Markdown text of this workout.
    func markdown() -> String {
        return Markdown.render(.workout(self))
    }
}

public extension Session {
    /// The Markdown text of this session.
    func markdown() -> String {
        return Markdown.render(.session(self))
    }
}

public extension Document {
    /// The Markdown text of this document.
    func markdown() -> String {
        return Markdown.render(self)
    }
}
