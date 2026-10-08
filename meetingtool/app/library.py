"""What the screens show, read from the data folder and never written.

A project's meetings are those of meetingtool.projects. A meeting processed by
the application has its own folder, named in its record (`folder`, relative to
the project's); one added from the terminal has none, and shows what its
record holds. A folder of the data folder that is not a project but holds a
summary.md (a result made with the commands) is a loose result, shown
read-only. Every path is built from identifiers checked as slugs, never taken
from a request.
"""

import json
import re
from pathlib import Path

from meetingtool.projects import store
from meetingtool.summary import qa, writer

RESULTS_DIR = "results"
PROCESSING_DIR = "processing"
RUN_NAME = "run.json"
REPORT_NAME = "summary.docx"
FOLDER = re.compile(rf"{RESULTS_DIR}/([a-z0-9]+(?:-[a-z0-9]+)*)")
FRAME_NAME = re.compile(r"frame_\d+_t\d{2}-\d{2}-\d{2}\.jpg")


class NotFound(Exception):
    """Nothing to show at that address."""


def is_slug(value):
    return bool(value) and value == store.slugify(value, fallback="")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _inside(folder, root):
    try:
        folder.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def projects(data_dir):
    return store.list_projects(data_dir)


def project(data_dir, project_id):
    if not is_slug(project_id):
        raise NotFound(project_id)
    try:
        folder = store._project_dir(data_dir, project_id)
    except store.ProjectError:
        raise NotFound(project_id) from None
    record = _read_json(folder / "project.json")
    if record is None:
        raise NotFound(project_id)
    return record


def knowledge(data_dir, project_id):
    project(data_dir, project_id)
    try:
        return store.knowledge_context(data_dir, project_id)
    except (store.ProjectError, OSError):
        return ""


def meeting_folder(data_dir, project_id, record):
    """The meeting's own folder, or None: only a folder under the project's
    results, named as the application names them, is followed."""
    match = FOLDER.fullmatch(record.get("folder", "") or "")
    if not match:
        return None
    project_dir = Path(data_dir) / project_id
    folder = project_dir / RESULTS_DIR / match.group(1)
    return folder if folder.is_dir() and _inside(folder, project_dir) else None


def result(folder):
    """What a result folder holds: summary, register, report, run record."""
    if folder is None:
        return None
    summary = folder / writer.OUTPUT_NAME
    text = summary.read_text(encoding="utf-8") if summary.is_file() else ""
    named = []
    for name in writer.FRAME_REF.findall(text):
        if name not in named and (folder / name).is_file():
            named.append(name)
    return {
        "summary": text,
        "format": "qa" if (folder / qa.REGISTER_NAME).is_file() else ("summary" if text else ""),
        "report": (folder / REPORT_NAME).is_file(),
        "frames": named,
        "frames_total": sum(1 for _ in folder.glob("frame_*.jpg")),
        "run": _read_json(folder / RUN_NAME),
    }


def meetings(data_dir, project_id):
    """The project's meetings in date order, each with its result if the
    application made it."""
    project(data_dir, project_id)
    listed = []
    for record in store.list_meetings(data_dir, project_id):
        listed.append({"record": record, "result": result(meeting_folder(data_dir, project_id, record))})
    return listed


def meeting_record(data_dir, project_id, meeting_id):
    """One meeting's record, read from its own folder: no other meeting's record
    or result is read, so a broken one elsewhere does not matter."""
    project(data_dir, project_id)
    try:
        record = store.read_meeting(data_dir, project_id, meeting_id)
    except store.ProjectError:
        raise NotFound(meeting_id) from None
    if record is None:
        raise NotFound(meeting_id)
    return record


def meeting(data_dir, project_id, meeting_id):
    record = meeting_record(data_dir, project_id, meeting_id)
    return {"record": record, "result": result(meeting_folder(data_dir, project_id, record))}


def _is_loose(entry):
    return (entry.is_dir() and is_slug(entry.name) and not (entry / "project.json").exists()
            and (entry / writer.OUTPUT_NAME).is_file())


def loose(data_dir):
    """Result folders of the data folder that are not projects, by name."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    return [{"name": entry.name, "result": result(entry)} for entry in sorted(data_dir.iterdir()) if _is_loose(entry)]


def _loose_folder(data_dir, name):
    """The folder of the loose result called `name`: only that folder is looked at."""
    if not is_slug(name) or not _is_loose(Path(data_dir) / name):
        raise NotFound(name)
    return Path(data_dir) / name


def loose_result(data_dir, name):
    return {"name": name, "result": result(_loose_folder(data_dir, name))}


def file_path(folder, name):
    """A file of a result folder the screens may serve: a frame, or the
    report."""
    if folder is None or not (FRAME_NAME.fullmatch(name) or name == REPORT_NAME):
        raise NotFound(name)
    path = folder / name
    if not path.is_file():
        raise NotFound(name)
    return path


def meeting_file(data_dir, project_id, meeting_id, name):
    record = meeting_record(data_dir, project_id, meeting_id)
    return file_path(meeting_folder(data_dir, project_id, record), name)


def loose_file(data_dir, folder_name, name):
    return file_path(_loose_folder(data_dir, folder_name), name)
