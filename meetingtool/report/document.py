"""Build the meeting report as a Word document (INGOL D-177).

The original MeetingTool exported its report to Word with python-docx
(tools/exporter.py): only the frames the report names are embedded, where
they are named, and a named frame that is missing stops the export. That is
kept. What is new: no network and no key, so the report can be rebuilt at no
cost after the summary is edited by hand; the document is opened again and
counted before it is delivered (the original left a note in place of an image
it could not embed and delivered anyway); a mention that looks like a frame
but names none stops it too; and the company that runs the analysis can give
its own Word template, one per installation, whose page becomes the cover and
whose header, footer and styles the report keeps.

A template saved by Word (measured on Word in Spanish) defines the heading
and title styles but no list or table style and no numbering, so lists and
tables here use direct formatting, never a named style a template may lack.
A template with macros is refused: the report is sent to third parties.
"""

import collections
import dataclasses
import hashlib
import io
import os
import re
import time
import zipfile
from pathlib import Path

import docx
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from meetingtool.projects import store
from meetingtool.summary import writer

SUMMARY_NAME = writer.OUTPUT_NAME
OUTPUT_NAME = "summary.docx"
TEMPLATE_NAME = "report-template.docx"
TEMPLATE_EXTENSIONS = {".docx", ".dotx"}
MACRO_EXTENSIONS = {".docm", ".dotm"}
DOCUMENT_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
TEMPLATE_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"

FRAME_REF = re.compile(r"\[(frame_\d+_t(\d{2})-(\d{2})-(\d{2})\.jpg)\]")
FRAME_LIKE = re.compile(r"frames?_", re.IGNORECASE)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
INLINE = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*\s][^*]*\*|`[^`]+`)")

LABELS = {
    "es": {"title": "Resumen de la reunión", "date": "Fecha", "project": "Proyecto",
           "mention": "imagen {clock}", "caption": "Imagen del minuto {clock} de la reunión"},
    "en": {"title": "Meeting summary", "date": "Date", "project": "Project",
           "mention": "frame {clock}", "caption": "Frame at {clock} into the meeting"},
}
INDENT = Cm(0.63)


class ReportError(Exception):
    """A report that could not be built; nothing was written."""


@dataclasses.dataclass
class ReportResult:
    output: Path
    language: str
    images: int
    sections: int
    size_bytes: int
    seconds: float
    template: Path | None
    cover: bool


# ── The company's template ───────────────────────────────────────────────────

def template_bytes(path):
    """The template at path as a Word document's bytes, or ReportError saying
    why it cannot be used. A .dotx is given the document content type, which
    python-docx needs; nothing else in it changes."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in MACRO_EXTENSIONS:
        raise ReportError(f"the template {path.name} can carry macros ({suffix}); save it in Word as .docx or .dotx")
    if suffix not in TEMPLATE_EXTENSIONS:
        raise ReportError(f"the template {path.name} is not a Word document or template (.docx or .dotx)")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            types = archive.read("[Content_Types].xml")
            parts = {name: archive.read(name) for name in names}
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ReportError(f"the template {path.name} cannot be opened: {error}") from None
    if b"macroEnabled" in types or any(Path(name).name.lower().startswith("vbaproject") for name in names):
        raise ReportError(f"the template {path.name} carries macros; save it in Word as .docx or .dotx")
    if TEMPLATE_TYPE in types:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                data = parts[name]
                archive.writestr(name, data.replace(TEMPLATE_TYPE, DOCUMENT_TYPE) if name == "[Content_Types].xml"
                                 else data)
        data = buffer.getvalue()
    else:
        data = path.read_bytes()
    try:
        docx.Document(io.BytesIO(data))
    except Exception as error:  # python-docx raises several kinds for a broken package
        raise ReportError(f"the template {path.name} cannot be opened as a Word document: {error}") from None
    return data


def stored_template(data_dir=None):
    """The installation's template, or None when there is none."""
    path = Path(data_dir or store.default_data_dir()) / TEMPLATE_NAME
    return path if path.is_file() else None


def set_template(path, data_dir=None):
    """Check the template and keep a copy of it in the data folder."""
    data = template_bytes(path)
    folder = store.check_data_dir(data_dir or store.default_data_dir())
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / TEMPLATE_NAME
    partial = folder / (TEMPLATE_NAME + ".partial")
    partial.write_bytes(data)
    os.replace(partial, target)
    return target


def remove_template(data_dir=None):
    """Remove the installation's template; True if there was one."""
    path = stored_template(data_dir)
    if path is None:
        return False
    path.unlink()
    return True


# ── Reading the summary ──────────────────────────────────────────────────────

def plain(text):
    """Text without Markdown emphasis markers."""
    return re.sub(r"\*\*|__|`", "", text).replace("*", "").strip()


def summary_headings(text):
    return [plain(match.group(2)) for match in map(HEADING.match, text.splitlines()) if match]


def summary_language(text):
    """'es' or 'en': the language whose section names the summary uses most,
    or else the language of its words."""
    headings = set(summary_headings(text))
    counts = {language: len(headings & set(names)) for language, names in writer.SECTIONS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] else writer.detect_language(text)


def clock(hours, minutes, seconds):
    hours = int(hours)
    return f"{hours}:{minutes}:{seconds}" if hours else f"{int(minutes)}:{seconds}"


def cited_frames(text, frames_dir):
    """The frames the summary names, in order of first mention, as {name:
    path}. A missing frame, or text that mentions a frame in any other way,
    is a ReportError naming every case."""
    frames, problems = {}, []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in FRAME_REF.finditer(line):
            name = match.group(1)
            if name not in frames:
                frames[name] = Path(frames_dir) / name
                if not frames[name].is_file():
                    problems.append(f"line {number}: {name} is not in {Path(frames_dir).resolve()}")
        leftover = FRAME_REF.sub("", line)
        if FRAME_LIKE.search(leftover):
            problems.append(f"line {number}: a frame mention that names no frame file "
                            f"(expected [frame_NNN_tHH-MM-SS.jpg]): {leftover.strip()[:80]}")
    if problems:
        raise ReportError("the report was not built:\n  " + "\n  ".join(problems))
    return frames


# ── Writing the document ─────────────────────────────────────────────────────

def _has_style(document, name):
    try:
        document.styles[name]
    except KeyError:
        return False
    return True


def _add_text(paragraph, text):
    for part in INLINE.split(text):
        if not part:
            continue
        if (part.startswith("**") and part.endswith("**")) or (part.startswith("__") and part.endswith("__")):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            paragraph.add_run(part[1:-1]).font.name = "Courier New"
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            paragraph.add_run(part[1:-1]).italic = True
        else:
            paragraph.add_run(part)


def _heading(document, text, level):
    if _has_style(document, f"Heading {level}"):
        document.add_heading(text, level=level)
        return
    run = document.add_paragraph().add_run(text)
    run.bold = True
    run.font.size = Pt({1: 16, 2: 13}.get(level, 12))


def _list_item(document, marker, text, depth):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = INDENT * (depth + 1)
    paragraph.paragraph_format.first_line_indent = -INDENT
    paragraph.add_run(f"{marker}\t")
    _add_text(paragraph, text)
    return paragraph


def _borders(table):
    properties = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "A0A0A0")
        borders.append(element)
    properties.append(borders)


def _table(document, lines, mention):
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in lines if not TABLE_SEPARATOR.match(line)]
    if not rows:
        return
    width = max(len(row) for row in rows)
    table = document.add_table(rows=len(rows), cols=width)
    _borders(table)
    for r, row in enumerate(rows):
        for c in range(width):
            paragraph = table.rows[r].cells[c].paragraphs[0]
            _add_text(paragraph, mention(row[c]) if c < len(row) else "")
            for run in paragraph.runs:
                run.font.size = Pt(9.5)
                if r == 0:
                    run.bold = True


def _picture(document, path, caption, width):
    holder = document.add_paragraph()
    holder.paragraph_format.keep_with_next = True
    holder.add_run().add_picture(str(path), width=width)
    run = document.add_paragraph().add_run(caption)
    run.italic = True
    run.font.size = Pt(9)


def _blocks(text):
    """The summary as (kind, payload) blocks: heading, bullet, numbered,
    table or paragraph. Blank lines and horizontal rules are dropped."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or RULE.match(line):
            i += 1
        elif (match := HEADING.match(line)):
            yield "heading", (max(1, min(len(match.group(1)) - 1, 3)), plain(match.group(2)))
            i += 1
        elif line.lstrip().startswith("|"):
            start = i
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                i += 1
            yield "table", lines[start:i]
        elif (match := BULLET.match(line)):
            yield "bullet", (len(match.group(1).expandtabs(4)) // 2, match.group(2))
            i += 1
        elif (match := NUMBERED.match(line)):
            yield "numbered", (len(match.group(1).expandtabs(4)) // 2, f"{match.group(2)}.", match.group(3))
            i += 1
        else:
            yield "paragraph", line.strip()
            i += 1


def node_text(element):
    """The text of a document element, from its w:t nodes."""
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def _body_is_empty(document):
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:sectPr"):
            continue
        if child.tag != qn("w:p") or node_text(child).strip() or child.findall(".//" + qn("w:drawing")):
            return False
    return True


def _clear_body(document):
    body = document.element.body
    for child in list(body.iterchildren()):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def _body_images(document):
    """The sha256 of every image drawn in the document's body, in order."""
    digests = []
    for blip in document.element.body.iter(qn("a:blip")):
        target = blip.get(qn("r:embed"))
        if target:
            digests.append(hashlib.sha256(document.part.related_parts[target].blob).hexdigest())
    return digests


def check_report(path, headings, cover_images, frames):
    """ReportError unless the document at path has every summary heading, in
    order, and exactly the cover's images plus one of each cited frame."""
    document = docx.Document(str(path))
    texts = iter(paragraph.text.strip() for paragraph in document.paragraphs)
    missing = [heading for heading in headings if not any(text == heading for text in texts)]
    if missing:
        raise ReportError(f"the Word document is missing the section(s) {missing}; it was not delivered")
    expected = collections.Counter(cover_images)
    expected.update(hashlib.sha256(Path(frame).read_bytes()).hexdigest() for frame in frames)
    found = collections.Counter(_body_images(document))
    if found != expected:
        lacking = sum((expected - found).values())
        extra = sum((found - expected).values())
        raise ReportError(f"the Word document has {lacking} image(s) missing and {extra} unexpected; "
                          "it was not delivered")


def build_report(frames_dir, *, title=None, date=None, project_name=None, data_dir=None, neutral=False,
                 template=None):
    """Write OUTPUT_NAME next to the summary in frames_dir and return what was
    built. `template` overrides the installation's; `neutral` uses none."""
    started = time.monotonic()
    frames_dir = Path(frames_dir)
    work_tree = store.enclosing_git_work_tree(frames_dir)
    if work_tree is not None:
        raise ReportError(f"folder {frames_dir.resolve()} is inside the git work tree {work_tree}; "
                          "the report is client data and must live outside any repository")
    summary = frames_dir / SUMMARY_NAME
    if not summary.is_file():
        raise ReportError(f"there is no {SUMMARY_NAME} in {frames_dir.resolve()}: write the summary first "
                          "with python -m meetingtool.summary")
    text = summary.read_text(encoding="utf-8")
    headings = summary_headings(text)
    if not headings:
        raise ReportError(f"{summary.resolve()} has no section heading; it does not look like a summary")
    frames = cited_frames(text, frames_dir)
    language = summary_language(text)
    labels = LABELS[language]

    template = None if neutral else (Path(template) if template else stored_template(data_dir))
    if template is not None:
        document = docx.Document(io.BytesIO(template_bytes(template)))
        cover = not _body_is_empty(document)
        if not cover:
            _clear_body(document)
    else:
        document = docx.Document()
        document.styles["Normal"].font.name = "Arial"
        document.styles["Normal"].font.size = Pt(11)
        for section in document.sections:
            section.top_margin = section.bottom_margin = Cm(2.5)
            section.left_margin = section.right_margin = Cm(2.5)
        cover = False
    cover_images = _body_images(document)
    if cover:
        document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    section = document.sections[-1]
    try:
        width = section.page_width - section.left_margin - section.right_margin
    except TypeError:
        width = Cm(16)

    heading_title = title.strip() if title and title.strip() else labels["title"]
    if _has_style(document, "Title"):
        document.add_paragraph(heading_title, style="Title")
    else:
        run = document.add_paragraph().add_run(heading_title)
        run.bold = True
        run.font.size = Pt(20)
    facts = [f"{labels['date']}: {date}" if date else "", f"{labels['project']}: {project_name}" if project_name else ""]
    if any(facts):
        document.add_paragraph(" · ".join(fact for fact in facts if fact))

    embedded = set()

    def mention(line):
        found = [match.group(1) for match in FRAME_REF.finditer(line)]
        pending.extend(name for name in found if name not in embedded and name not in pending)
        return FRAME_REF.sub(lambda m: labels["mention"].format(clock=clock(*m.groups()[1:])), line)

    for kind, payload in _blocks(text):
        pending = []
        if kind == "heading":
            _heading(document, payload[1], payload[0])
        elif kind == "table":
            _table(document, payload, mention)
        elif kind == "bullet":
            _list_item(document, "•", mention(payload[1]), payload[0])
        elif kind == "numbered":
            _list_item(document, payload[1], mention(payload[2]), payload[0])
        else:
            _add_text(document.add_paragraph(), mention(payload))
        for name in pending:
            match = FRAME_REF.match(f"[{name}]")
            _picture(document, frames[name], labels["caption"].format(clock=clock(*match.groups()[1:])), width)
            embedded.add(name)

    output = frames_dir / OUTPUT_NAME
    partial = frames_dir / (OUTPUT_NAME + ".partial")
    try:
        document.save(str(partial))
        check_report(partial, headings, cover_images, frames.values())
        os.replace(partial, output)
    except PermissionError:
        partial.unlink(missing_ok=True)
        raise ReportError(f"{output.resolve()} could not be replaced; if it is open in Word, close it and "
                          "try again") from None
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return ReportResult(output, language, len(frames), len(headings), output.stat().st_size,
                        time.monotonic() - started, template, cover)
