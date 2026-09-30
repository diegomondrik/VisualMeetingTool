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
import json
import os
import re
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import docx
from docx.enum.text import WD_BREAK
from docx.image.exceptions import UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from meetingtool.projects import store
from meetingtool.report import layout
from meetingtool.summary import qa, writer

SUMMARY_NAME = writer.OUTPUT_NAME
OUTPUT_NAME = "summary.docx"
TEMPLATE_NAME = "report-template.docx"
TEMPLATE_RECORD = "report-template.json"
TEMPLATE_EXTENSIONS = {".docx", ".dotx"}
MACRO_EXTENSIONS = {".docm", ".dotm"}
DOCUMENT_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
TEMPLATE_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"

# Relationship types that bring an embedded object, a control or a macro
# project into the document, or another template or document into it.
ACTIVE_RELATIONSHIPS = frozenset({"attachedTemplate", "oleObject", "package", "control", "activeXControl",
                                  "activeXControlBinary", "vbaProject", "wordVbaData", "aFChunk", "subDocument",
                                  "frame"})
ACTIVE_FIELDS = re.compile(r"\b(DDEAUTO|DDE|INCLUDETEXT|INCLUDEPICTURE|INCLUDE|IMPORT|LINK)\b", re.IGNORECASE)
FIELD_TEXT = re.compile(rb"<w:instrText[^>]*>([^<]*)</w:instrText>")
FIELD_ATTRIBUTE = re.compile(rb'w:instr="([^"]*)"')

FRAME_REF = re.compile(r"\[(frame_\d+_t(\d{2})-(\d{2})-(\d{2})\.jpg)\]")
FRAME_LIKE = re.compile(r"\bframes?_", re.IGNORECASE)
# As the summary's own check reads a heading (meetingtool.summary.writer):
# up to the text, the space after the hashes is optional.
HEADING = re.compile(r"^(#{1,6})\s*(\S.*?)\s*#*\s*$")
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
    fields: list = dataclasses.field(default_factory=list)  # the template's fields that were filled
    contents: int = 0    # entries written in the template's tables of contents
    dropped: int = 0     # paragraphs with text of the template's model, left out


# ── The company's template ───────────────────────────────────────────────────

def active_content(parts):
    """What in a Word package would be loaded or run from outside it when the
    document opens, one line each: an external relationship other than a
    hyperlink (an attached template, which may be a .dotm with macros; a
    linked picture), a relationship to an embedded object, control or macro
    project, and a field that pulls or runs outside content (DDE, INCLUDE...).
    The fields of a part are joined before matching, so a field code split
    across runs is still found."""
    found = []
    for name, data in sorted(parts.items()):
        if name.endswith(".rels"):
            try:
                relationships = ElementTree.fromstring(data)
            except ElementTree.ParseError as error:
                found.append(f"{name}: unreadable relationships ({error})")
                continue
            for relationship in relationships:
                kind = relationship.get("Type", "").rsplit("/", 1)[-1]
                target = relationship.get("Target", "")
                if relationship.get("TargetMode") == "External" and kind != "hyperlink":
                    found.append(f"{name}: an external {kind} ({target})")
                elif kind in ACTIVE_RELATIONSHIPS:
                    found.append(f"{name}: a {kind} ({target})")
        elif name.startswith("word/") and name.endswith(".xml"):
            codes = b" ".join(FIELD_ATTRIBUTE.findall(data)) + b" " + b"".join(FIELD_TEXT.findall(data))
            for field in sorted({match.upper() for match in ACTIVE_FIELDS.findall(codes.decode("utf-8", "replace"))}):
                found.append(f"{name}: a {field} field")
    return found


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
    active = active_content(parts)
    if active:
        raise ReportError(f"the template {path.name} has content that Word would load or run from outside it when "
                          "a report is opened, and every report would carry it to the client:\n  "
                          + "\n  ".join(active) + "\nRemove it in Word and save the template again (attach the "
                          "Normal template, embed pictures instead of linking them, delete linked fields and "
                          "embedded objects).")
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
        opened = docx.Document(io.BytesIO(data))
    except Exception as error:  # python-docx raises several kinds for a broken package
        raise ReportError(f"the template {path.name} cannot be opened as a Word document: {error}") from None
    try:
        layout.read_layout(opened)
    except layout.LayoutError as error:
        raise ReportError(f"the template {path.name} cannot be used: {error}") from None
    return data


@dataclasses.dataclass
class TemplateInfo:
    """What the installation's template is, and what was understood of it."""
    path: Path
    name: str | None      # the file's name when it was set; None if it was set before that was recorded
    set_utc: str | None
    fields: list
    tables_of_contents: int
    start: str | None     # "index", "marker" or None
    dropped: int          # paragraphs with text of the template's model, dropped from every report


def stored_template(data_dir=None):
    """The installation's template, or None when there is none."""
    path = Path(data_dir or store.default_data_dir()) / TEMPLATE_NAME
    return path if path.is_file() else None


def template_info(data_dir=None):
    """The installation's template as TemplateInfo, or None when there is
    none; ReportError if it can no longer be used."""
    path = stored_template(data_dir)
    if path is None:
        return None
    found = layout.read_layout(docx.Document(io.BytesIO(template_bytes(path))))
    try:
        record = json.loads((path.parent / TEMPLATE_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    name = record.get("name") if isinstance(record, dict) and isinstance(record.get("name"), str) else None
    set_utc = record.get("set_utc") if name and isinstance(record.get("set_utc"), str) else None
    return TemplateInfo(path, name, set_utc, found.fields, len(found.tocs), found.start_kind, found.dropped)


def set_template(path, data_dir=None, name=None):
    """Check the template and keep a copy of it in the data folder, with the
    name it was given (by default, its own file name)."""
    data = template_bytes(path)
    folder = store.check_data_dir(data_dir or store.default_data_dir())
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / TEMPLATE_NAME
    partial = folder / (TEMPLATE_NAME + ".partial")
    partial.write_bytes(data)
    record = {"name": Path(name or Path(path).name).name[:200], "set_utc": store._now_utc()}
    (folder / (TEMPLATE_RECORD + ".partial")).write_text(json.dumps(record, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
    os.replace(partial, target)
    os.replace(folder / (TEMPLATE_RECORD + ".partial"), folder / TEMPLATE_RECORD)
    return target


def remove_template(data_dir=None):
    """Remove the installation's template and its record; True if there was
    one."""
    path = stored_template(data_dir)
    if path is None:
        return False
    path.unlink()
    (path.parent / TEMPLATE_RECORD).unlink(missing_ok=True)
    return True


def example_template():
    """The bytes of a template to start from (see layout.example_template)."""
    return layout.example_template()


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
    counts = {language: len(headings & set(names + qa.HEADINGS[language]))
              for language, names in writer.SECTIONS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] else writer.detect_language(text)


def clock(hours, minutes, seconds):
    hours = int(hours)
    return f"{hours}:{minutes}:{seconds}" if hours else f"{int(minutes)}:{seconds}"


def cited_frames(text, frames_dir):
    """The frames the summary names, in order of first mention, as {name:
    path}. A missing frame, text that mentions a frame in any other way, or
    two frames named as a range (whose two ends nobody chose, INGOL D-181),
    is a ReportError naming every case."""
    frames, problems = {}, []
    for number, line in enumerate(text.splitlines(), start=1):
        found = writer.FRAME_RANGE.search(line)
        if found:
            problems.append(f"line {number}: a range of frames; name each frame on its own: {found.group(0)[:80]}")
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
    """Add a heading; return its paragraph element."""
    if _has_style(document, f"Heading {level}"):
        return document.add_heading(text, level=level)._p
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt({1: 16, 2: 13}.get(level, 12))
    return paragraph._p


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


def check_report(path, headings, cover_images, frames, *, start=0, contents=()):
    """ReportError unless the document at path has every summary heading, in
    order, after its first `start` body elements (the cover, whose table of
    contents repeats the headings); exactly the cover's images plus one of
    each cited frame; each table of contents of the cover listing exactly
    what `contents` says, in order; and no known field left unfilled."""
    document = docx.Document(str(path))
    children = layout.body_children(document)
    texts = iter(layout.paragraph_text(child).strip() for child in children[start:] if child.tag == qn("w:p"))
    missing = [heading for heading in headings if not any(text == heading for text in texts)]
    if missing:
        raise ReportError(f"the Word document is missing the section(s) {missing}; it was not delivered")
    cover_ids = {id(child) for child in children[:start]}
    body = document.element.body
    found_contents = [layout.toc_entries(document, toc) for toc in layout._tocs(document)
                      if id(layout._top(toc[0], body)) in cover_ids]
    if found_contents != [list(entries) for entries in contents]:
        raise ReportError("the Word document's table of contents does not list exactly its sections; "
                          "it was not delivered")
    left = layout.leftover_fields(document, children[:start])
    if left:
        raise ReportError(f"the Word document still has {', '.join(left)} unfilled; it was not delivered")
    expected = collections.Counter(cover_images)
    expected.update(hashlib.sha256(Path(frame).read_bytes()).hexdigest() for frame in frames)
    found = collections.Counter(_body_images(document))
    if found != expected:
        lacking = sum((expected - found).values())
        extra = sum((found - expected).values())
        raise ReportError(f"the Word document has {lacking} image(s) missing and {extra} unexpected; "
                          "it was not delivered")


def build_report(frames_dir, *, title=None, date=None, project_name=None, data_dir=None, neutral=False,
                 template=None, client=None, meeting_type=None):
    """Write OUTPUT_NAME next to the summary in frames_dir and return what was
    built. `template` overrides the installation's; `neutral` uses none. The
    title, date, project, client and type fill the template's fields."""
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
    # utf-8-sig: an editor may add a byte-order mark when the summary is
    # edited by hand, and it would hide the first heading.
    text = summary.read_text(encoding="utf-8-sig")
    headings = summary_headings(text)
    if not headings:
        raise ReportError(f"{summary.resolve()} has no section heading; it does not look like a summary")
    unread = [number for number, line in enumerate(text.splitlines(), start=1)
              if line.lstrip().startswith("#") and not HEADING.match(line)]
    if unread:
        raise ReportError(f"line(s) {unread} of {summary.resolve()} start with # but are not headings the report "
                          "can read (a heading starts the line with 1 to 6 # and has text); the report was not built")
    frames = cited_frames(text, frames_dir)
    language = summary_language(text)
    labels = LABELS[language]

    template = None if neutral else (Path(template) if template else stored_template(data_dir))
    found = None
    if template is not None:
        document = docx.Document(io.BytesIO(template_bytes(template)))
        found = layout.read_layout(document)
        layout.drop_model(document, found)
        layout.fill_fields(document, layout.field_values(
            language, client=client, project=project_name, meeting=title.strip() if title else None, date=date,
            meeting_type=meeting_type))
        layout.no_update_on_open(document)
        cover = bool(found.tocs) or not _body_is_empty(document)
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
    if cover and not layout.ends_on_a_new_page(document):
        # A cover ending with its own section break already starts the report on a new page.
        document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    section = document.sections[-1]
    try:
        width = section.page_width - section.left_margin - section.right_margin
    except TypeError:
        width = Cm(16)

    heading_title = title.strip() if title and title.strip() else labels["title"]
    if _has_style(document, "Title"):
        first = document.add_paragraph(heading_title, style="Title")
    else:
        first = document.add_paragraph()
        run = first.add_run(heading_title)
        run.bold = True
        run.font.size = Pt(20)
    facts = [f"{labels['date']}: {date}" if date else "", f"{labels['project']}: {project_name}" if project_name else ""]
    if any(facts):
        document.add_paragraph(" · ".join(fact for fact in facts if fact))

    embedded, placed = set(), []

    def mention(line):
        found = [match.group(1) for match in FRAME_REF.finditer(line)]
        pending.extend(name for name in found if name not in embedded and name not in pending)
        return FRAME_REF.sub(lambda m: labels["mention"].format(clock=clock(*m.groups()[1:])), line)

    for kind, payload in _blocks(text):
        pending = []
        if kind == "heading":
            shown = mention(payload[1])
            placed.append((payload[0], shown, _heading(document, shown, payload[0])))
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
            try:
                _picture(document, frames[name], labels["caption"].format(clock=clock(*match.groups()[1:])), width)
            except (UnrecognizedImageError, OSError) as error:
                raise ReportError(f"the frame {name} cannot be embedded ({type(error).__name__}: {error}); "
                                  "the report was not built") from None
            embedded.add(name)

    expected = [FRAME_REF.sub(lambda m: labels["mention"].format(clock=clock(*m.groups()[1:])), heading)
                for heading in headings]
    contents = []
    if found is not None and found.tocs:
        bookmarks = layout.bookmark_headings(document, placed)
        try:
            for toc in found.tocs:
                layout.fill_toc(document, toc, placed, bookmarks)
        except layout.LayoutError as error:
            raise ReportError(f"the template {Path(template).name} cannot be used: {error}") from None
        # What each table of contents must list, from the summary's headings
        # and the field's levels, not from what was written in it.
        depth = [max(1, min(len(HEADING.match(line).group(1)) - 1, 3)) for line in text.splitlines()
                 if HEADING.match(line)]
        for _, _, instruction in found.tocs:
            low, high = layout.levels(instruction)
            contents.append([heading for level, heading in zip(depth, expected) if low <= level <= high])
    # Where the report starts, counted after the tables of contents were
    # rewritten: they may have changed how many paragraphs the cover has.
    start = layout.body_children(document).index(first._p)

    output = frames_dir / OUTPUT_NAME
    partial = frames_dir / (OUTPUT_NAME + ".partial")
    try:
        document.save(str(partial))
        check_report(partial, expected, cover_images, frames.values(), start=start, contents=contents)
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise ReportError(f"the report could not be written in {frames_dir.resolve()}: {error}") from None
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    try:
        os.replace(partial, output)
    except OSError as error:
        partial.unlink(missing_ok=True)
        hint = "; if it is open in Word, close it and try again" if isinstance(error, PermissionError) else ""
        raise ReportError(f"{output.resolve()} could not be replaced ({error.strerror}){hint}") from None
    return ReportResult(output, language, len(frames), len(headings), output.stat().st_size,
                        time.monotonic() - started, template, cover, found.fields if found else [],
                        sum(len(entries) for entries in contents), found.dropped if found else 0)
