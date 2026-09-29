"""WI14-AC07/AC08: the real run's register set against the owner's hand-made
register of the same meeting, by minute, printing only ids, minutes, counts
and statuses (never what was said: it is client data).

    python docs/evidence/01M3Q46RMB70H2F5NE56SVQD5M/coverage.py <qa.json> <build_qa_docx.py> [<confirmed.json>]

build_qa_docx.py is the owner's script that built his Word: each question is a
q("<id>", "<topic>", "<minute>", "<status>", ...) call. A reference question
has candidates in the register when its minute falls within a registered
question's span, or its start is within WINDOW seconds of it. The minute alone
cannot say that two questions are the same one, so confirmed.json, when
given, holds the reading made by hand ({reference id: register id or null});
the count that decides AC07 is the confirmed one.
"""

import json
import re
import sys
from pathlib import Path

WINDOW = 120
REFERENCE = re.compile(r'^q\("([^"]+)", "[^"]*", "([\d:]+)", "([^"]+)"', re.MULTILINE)


def seconds(clock):
    parts = [int(part) for part in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def minute(value):
    hours, rest = divmod(value, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def main(register_path, reference_path, confirmed_path=None):
    register = json.loads(Path(register_path).read_text(encoding="utf-8"))
    questions = register["questions"]
    reference = REFERENCE.findall(Path(reference_path).read_text(encoding="utf-8"))
    confirmed = json.loads(Path(confirmed_path).read_text(encoding="utf-8")) if confirmed_path else None
    print(f"register: {len(questions)} question(s); reference: {len(reference)} question(s)")
    statuses = {}
    for question in questions:
        statuses[question["status"]] = statuses.get(question["status"], 0) + 1
    print("register statuses: " + ", ".join(f"{name} {count}" for name, count in sorted(statuses.items())))
    on_screen = [q for q in questions if q["screen"]]
    print(f"on screen: {len(on_screen)} -> " + (", ".join(
        f"{q['id']} ({minute(q['start'])}-{minute(q['end'])}, span {len(q['span'])} frame(s), named "
        f"{len((q.get('seen') or {}).get('frames', []))})" for q in on_screen) or "none"))
    covered_by_minute = 0
    covered = 0
    for identifier, clock, status in reference:
        at = seconds(clock)
        candidates = [q["id"] for q in questions
                      if q["start"] <= at <= max(q["end"], q["start"]) or abs(q["start"] - at) <= WINDOW]
        covered_by_minute += bool(candidates)
        line = f"- {identifier} ({clock}, {status}): candidates {', '.join(candidates) or 'none'}"
        if confirmed is not None:
            match = confirmed.get(identifier)
            covered += match is not None
            line += f"; confirmed by reading: {match or 'NOT COVERED'}"
        print(line)
    print(f"reference questions with a candidate by minute: {covered_by_minute} of {len(reference)}")
    if confirmed is not None:
        print(f"reference questions covered, confirmed by reading: {covered} of {len(reference)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
