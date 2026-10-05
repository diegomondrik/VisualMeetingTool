"""Projects, their meetings, and the knowledge each project builds up.

Layout of the data folder (outside any git repository, see check_data_dir):

    <data>/<project id>/project.json
    <data>/<project id>/meetings/<meeting id>/meeting.json
    <data>/<project id>/knowledge.md

Only paths to recordings and transcripts are stored; their content is never
read or copied here.

Every write is whole or not at all, and every change happens holding the data
folder's lock, which holds between the application and the terminal commands
(meetingtool.disk; WI20, the external review's R01): two meetings added at
once get two identifiers, and a process that dies while saving leaves every
record readable. A record that still cannot be read (edited by hand, or left
by a version before WI20) is named in an error, never skipped: skipping would
hide the damage.
"""

import contextlib
import datetime
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

from meetingtool import disk, texts

SCHEMA_VERSION = 1
DATA_DIR_ENV = "MEETINGTOOL_DATA_DIR"
DEFAULT_DATA_DIR_NAME = "VisualMeetingTool-data"


class ProjectError(texts.Failure):
    """A project or meeting operation that cannot be carried out."""


def default_data_dir():
    """The data folder used when none is given: the environment variable, or a
    folder in the user's home directory."""
    configured = os.environ.get(DATA_DIR_ENV)
    if configured:
        return Path(configured)
    return Path.home() / DEFAULT_DATA_DIR_NAME


def enclosing_git_work_tree(path):
    """Return the folder holding .git that contains path, or None."""
    current = Path(path).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def check_data_dir(data_dir):
    """Refuse a data folder inside a git work tree: meeting data is client
    data and must never sit where a repository could track it."""
    work_tree = enclosing_git_work_tree(data_dir)
    if work_tree is not None:
        raise ProjectError("projects.inside_repository", folder=str(Path(data_dir).resolve()),
                           work_tree=str(work_tree))
    return Path(data_dir)


def slugify(text, fallback="item"):
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = "-".join(re.findall(r"[a-z0-9]+", normalized.lower()))
    return slug or fallback


def _write_json(path, data):
    disk.write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", newline="\n")


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _read_record(path, needed):
    """A record holding the text fields `needed`, or ProjectError naming the file."""
    try:
        record = _read_json(path)
    except ValueError as error:  # not JSON, or not UTF-8
        raise ProjectError("projects.unreadable", file=str(path), detail=texts.External(str(error))) from None
    if not isinstance(record, dict) or any(not isinstance(record.get(name), str) for name in needed):
        raise ProjectError("projects.unreadable", file=str(path),
                           detail=texts.External("missing " + ", ".join(needed)))
    return record


@contextlib.contextmanager
def data_lock(data_dir):
    """Hold the data folder's lock (meetingtool.disk.locked); ProjectError if
    another writer keeps it too long."""
    try:
        with disk.locked(data_dir):
            yield
    except disk.LockTimeout as error:
        raise ProjectError(error.message) from None


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_dir(data_dir, project_id):
    # A project id is a slug, never a path: "../repo/x" or an absolute path
    # would write outside the data folder. The final folder is checked too,
    # in case a link inside the data folder points into a repository.
    if project_id != slugify(project_id, fallback=""):
        raise ProjectError("projects.bad_identifier", project=project_id)
    folder = Path(data_dir) / project_id
    check_data_dir(folder)
    if not (folder / "project.json").is_file():
        raise ProjectError("projects.missing", project=project_id, folder=str(Path(data_dir).resolve()))
    return folder


def create_project(data_dir, name, client, context=""):
    """Create a project and return its record."""
    data_dir = check_data_dir(data_dir)
    if not name.strip():
        raise ProjectError("projects.needs_name")
    project_id = slugify(name, fallback="project")
    folder = data_dir / project_id
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": project_id,
        "name": name.strip(),
        "client": client.strip(),
        "context": context.strip(),
        "created_utc": _now_utc(),
    }
    with data_lock(data_dir):
        # The folder reserves the identifier: made exclusively, under the lock.
        # One without project.json is what a creation cut short left.
        try:
            folder.mkdir(parents=True)
        except FileExistsError:
            if (folder / "project.json").exists() or not folder.is_dir():
                raise ProjectError("projects.exists", project=project_id, folder=str(data_dir.resolve())) from None
        _write_json(folder / "project.json", record)
        rebuild_knowledge(data_dir, project_id)
    return record


def list_projects(data_dir):
    """Return every project record, sorted by identifier."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    return [
        _read_record(entry / "project.json", ("id", "name"))
        for entry in sorted(data_dir.iterdir())
        if (entry / "project.json").is_file()
    ]


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value).isoformat() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def add_meeting(data_dir, project_id, title, date, meeting_type="", recording="", transcript="",
                summary="", key_points=(), meeting_folder=""):
    """Add a meeting to a project, rebuild its knowledge file, and return the
    meeting record. _project_dir checks the project's own folder, which also
    covers a data folder inside a git work tree. `meeting_folder`, the meeting's
    own folder relative to the project's (the application's results), is
    recorded only when given: a meeting added from the terminal has none."""
    folder = _project_dir(data_dir, project_id)
    iso_date = _parse_date(date)
    if iso_date is None:
        raise ProjectError("meeting.bad_date", date=date)
    if not title.strip():
        raise ProjectError("projects.needs_title")
    meetings = folder / "meetings"
    base_id = f"{iso_date}-{slugify(title, fallback='meeting')}"
    record = {
        "schema_version": SCHEMA_VERSION,
        "title": title.strip(),
        "date": iso_date,
        "meeting_type": meeting_type.strip(),
        "recording": str(Path(recording).resolve()) if recording else "",
        "transcript": str(Path(transcript).resolve()) if transcript else "",
        "summary": summary.strip(),
        "key_points": [point.strip() for point in key_points if point.strip()],
        "added_utc": _now_utc(),
    }
    if meeting_folder:
        record["folder"] = meeting_folder
    with data_lock(data_dir):
        # The meeting's folder reserves its identifier, made exclusively under
        # the lock; one without meeting.json is what a save cut short left.
        meeting_id, counter = base_id, 2
        while True:
            try:
                (meetings / meeting_id).mkdir(parents=True)
                break
            except FileExistsError:
                if (meetings / meeting_id).is_dir() and not (meetings / meeting_id / "meeting.json").exists():
                    break
            meeting_id, counter = f"{base_id}-{counter}", counter + 1
        record = {"id": meeting_id, **record}
        _write_json(meetings / meeting_id / "meeting.json", record)
        try:
            rebuild_knowledge(data_dir, project_id)
        except BaseException:
            # Whole or not at all: a meeting the knowledge cannot take is not kept.
            shutil.rmtree(meetings / meeting_id, ignore_errors=True)
            raise
    return record


def list_meetings(data_dir, project_id):
    """Return a project's meetings in date order, then by time added and
    identifier. The sort is explicit: folder listing order differs between
    file systems."""
    folder = _project_dir(data_dir, project_id)
    meetings = folder / "meetings"
    if not meetings.is_dir():
        return []
    records = [
        _read_record(entry / "meeting.json", ("id", "title", "date", "added_utc"))
        for entry in meetings.iterdir()
        if (entry / "meeting.json").is_file()
    ]
    return sorted(records, key=lambda m: (m["date"], m["added_utc"], m["id"]))


def render_knowledge(project, meetings):
    """The knowledge text for a project and its meetings, in date order."""
    lines = [f"# Knowledge: {project['name']}", "", f"Client: {project.get('client') or '(not set)'}", "",
             "## Context", "", project.get("context") or "(none)", "", "## Meetings", ""]
    if not meetings:
        lines += ["(no meetings yet)", ""]
    for meeting in meetings:
        heading = f"### {meeting['date']}: {meeting['title']}"
        if meeting.get("meeting_type"):
            heading += f" ({meeting['meeting_type']})"
        lines += [heading, "", meeting.get("summary") or "(no summary yet)", ""]
        if meeting.get("key_points"):
            lines += ["Key points:", ""] + [f"- {point}" for point in meeting["key_points"]] + [""]
    return "\n".join(lines)


def rebuild_knowledge(data_dir, project_id):
    """Rewrite a project's knowledge file from all of its meetings."""
    folder = _project_dir(data_dir, project_id)
    with data_lock(data_dir):
        text = render_knowledge(_read_record(folder / "project.json", ("name",)), list_meetings(data_dir, project_id))
        disk.write_text(folder / "knowledge.md", text, newline="\n")
    return text


def knowledge_context(data_dir, project_id):
    """The accumulated knowledge the next meeting summary reads: knowledge.md,
    or, if a creation cut short left none, the same text made from the
    records (WI20)."""
    folder = _project_dir(data_dir, project_id)
    try:
        with open(folder / "knowledge.md", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return render_knowledge(_read_record(folder / "project.json", ("name",)), list_meetings(data_dir, project_id))
