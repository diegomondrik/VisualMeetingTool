"""Projects, their meetings, and the knowledge each project builds up.

Layout of the data folder (outside any git repository, see check_data_dir):

    <data>/<project id>/project.json
    <data>/<project id>/meetings/<meeting id>/meeting.json
    <data>/<project id>/knowledge.md

Only paths to recordings and transcripts are stored; their content is never
read or copied here.
"""

import datetime
import json
import os
import re
import unicodedata
from pathlib import Path

SCHEMA_VERSION = 1
DATA_DIR_ENV = "MEETINGTOOL_DATA_DIR"
DEFAULT_DATA_DIR_NAME = "VisualMeetingTool-data"


class ProjectError(Exception):
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
        raise ProjectError(
            f"data folder {Path(data_dir).resolve()} is inside the git work tree {work_tree}; "
            "meeting data must live outside any repository"
        )
    return Path(data_dir)


def slugify(text, fallback="item"):
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = "-".join(re.findall(r"[a-z0-9]+", normalized.lower()))
    return slug or fallback


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_dir(data_dir, project_id):
    folder = Path(data_dir) / project_id
    if not (folder / "project.json").is_file():
        raise ProjectError(f"project {project_id} does not exist in {Path(data_dir).resolve()}")
    return folder


def create_project(data_dir, name, client, context=""):
    """Create a project and return its record."""
    data_dir = check_data_dir(data_dir)
    if not name.strip():
        raise ProjectError("a project needs a name")
    project_id = slugify(name, fallback="project")
    folder = data_dir / project_id
    if folder.exists():
        raise ProjectError(f"project {project_id} already exists in {data_dir.resolve()}")
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": project_id,
        "name": name.strip(),
        "client": client.strip(),
        "context": context.strip(),
        "created_utc": _now_utc(),
    }
    _write_json(folder / "project.json", record)
    rebuild_knowledge(data_dir, project_id)
    return record


def list_projects(data_dir):
    """Return every project record, sorted by identifier."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    return [
        _read_json(entry / "project.json")
        for entry in sorted(data_dir.iterdir())
        if (entry / "project.json").is_file()
    ]


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value).isoformat() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def add_meeting(data_dir, project_id, title, date, meeting_type="", recording="", transcript="",
                summary="", key_points=()):
    """Add a meeting to a project, rebuild its knowledge file, and return the
    meeting record."""
    data_dir = check_data_dir(data_dir)
    folder = _project_dir(data_dir, project_id)
    iso_date = _parse_date(date)
    if iso_date is None:
        raise ProjectError(f"meeting date {date!r} is not a valid YYYY-MM-DD date")
    if not title.strip():
        raise ProjectError("a meeting needs a title")
    meetings = folder / "meetings"
    base_id = f"{iso_date}-{slugify(title, fallback='meeting')}"
    meeting_id, counter = base_id, 2
    while (meetings / meeting_id).exists():
        meeting_id, counter = f"{base_id}-{counter}", counter + 1
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": meeting_id,
        "title": title.strip(),
        "date": iso_date,
        "meeting_type": meeting_type.strip(),
        "recording": str(Path(recording).resolve()) if recording else "",
        "transcript": str(Path(transcript).resolve()) if transcript else "",
        "summary": summary.strip(),
        "key_points": [point.strip() for point in key_points if point.strip()],
        "added_utc": _now_utc(),
    }
    _write_json(meetings / meeting_id / "meeting.json", record)
    rebuild_knowledge(data_dir, project_id)
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
        _read_json(entry / "meeting.json")
        for entry in meetings.iterdir()
        if (entry / "meeting.json").is_file()
    ]
    return sorted(records, key=lambda m: (m["date"], m["added_utc"], m["id"]))


def render_knowledge(project, meetings):
    """The knowledge text for a project and its meetings, in date order."""
    lines = [f"# Knowledge: {project['name']}", "", f"Client: {project['client'] or '(not set)'}", "",
             "## Context", "", project["context"] or "(none)", "", "## Meetings", ""]
    if not meetings:
        lines += ["(no meetings yet)", ""]
    for meeting in meetings:
        heading = f"### {meeting['date']}: {meeting['title']}"
        if meeting["meeting_type"]:
            heading += f" ({meeting['meeting_type']})"
        lines += [heading, "", meeting["summary"] or "(no summary yet)", ""]
        if meeting["key_points"]:
            lines += ["Key points:", ""] + [f"- {point}" for point in meeting["key_points"]] + [""]
    return "\n".join(lines)


def rebuild_knowledge(data_dir, project_id):
    """Rewrite a project's knowledge file from all of its meetings."""
    folder = _project_dir(data_dir, project_id)
    text = render_knowledge(_read_json(folder / "project.json"), list_meetings(data_dir, project_id))
    with open(folder / "knowledge.md", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return text


def knowledge_context(data_dir, project_id):
    """The accumulated knowledge the next meeting summary reads."""
    folder = _project_dir(data_dir, project_id)
    with open(folder / "knowledge.md", encoding="utf-8") as handle:
        return handle.read()
