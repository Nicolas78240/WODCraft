"""Markdown rendering, for blogs, chat and documentation."""

from __future__ import annotations

from wodcraft.emit.board import SCORE_LABEL, _block, _range


def to_markdown(document: dict) -> str:
    if document.get("kind") == "session":
        lines = [f"# {document.get('title') or 'Session'}"]
        head = " · ".join(x for x in (document.get("date"), document.get("time")) if x)
        if head:
            lines += ["", f"*{head}*"]
        for section in document.get("sections", []):
            lines += ["", f"## {section['title']}", "", _workout_body(section["workout"])]
        return "\n".join(lines).rstrip() + "\n"
    return f"# {document.get('title') or 'Workout'}\n\n{_workout_body(document)}\n"


def _workout_body(workout: dict) -> str:
    lines: list[str] = ["```"]
    for block in workout.get("blocks", []):
        lines += _block(block, 0, 40)
    lines.append("```")
    meta = workout.get("meta") or {}
    score = (workout.get("score") or {}).get("type")
    if score and score != "none":
        lines.append("")
        lines.append(f"**Score** — {SCORE_LABEL.get(score, score)}")
    if workout.get("estimate"):
        lines.append(f"**Estimate** — {_range(workout['estimate'])}")
    for stimulus in meta.get("stimulus", []):
        lines.append("")
        lines.append(f"> {stimulus}")
    for note in meta.get("notes", []):
        lines.append("")
        lines.append(f"*{note}*")
    return "\n".join(lines)
