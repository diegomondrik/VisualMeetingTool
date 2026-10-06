"""Processing a meeting from start to end, as the commands do it in order.

The stages are the commands' functions: the frames of the recording
(meetingtool.frames, only with a recording), their reading (meetingtool.reading,
only for the summary, which needs it), the summary or the register with what
the project knows (meetingtool.summary), and the Word report
(meetingtool.report). One spending meter is shared by the stages that pay, so
one ceiling covers the whole run.

Nothing is added to the project until the report is built: the run works in
<project>/processing/<run>, moves it to <project>/results/<run> and only then
adds the meeting, naming that folder. If anything fails, the meeting is not
added and the job says which stage failed, why, and what was spent.

What was paid is not thrown away (WI20, the external review's R03, a rule the
owner approved on 2026-10-05 in place of "if anything fails, nothing is left
of the run"): every accepted answer of a paid request is kept in the working
folder (gemini.KEPT_DIR, and the register's qa.PARTS_DIR), and a run that
fails holding one keeps its folder, with KEPT_RECORD saying what it was
asked. Processing the same meeting again (the same transcript and format, in
the same project) continues in that folder and pays only what is missing; the
folder goes when that run succeeds or when the person discards it. A run that
paid nothing leaves nothing. One run at a time.
"""

import datetime
import hashlib
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path

from meetingtool import disk, texts
from meetingtool.app import library
from meetingtool.frames import transcript as transcript_module
from meetingtool.projects import store
from meetingtool.reading import gemini
from meetingtool.summary import qa

FORMATS = ("summary", "qa")
# The ceiling of one meeting, every stage together (INGOL D-186): it must cover each paid request and
# its retry at their worst, or a long meeting stops before a retry of its reading (the first real run:
# 70 frames reserve about US$0.26, twice is over US$0.50). What is usually paid is far less.
DEFAULT_MAX_COST_USD = 1.00
TRANSCRIPT_SUFFIXES = (".docx", ".txt")
RECORDING_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".m4v")
# In a run's working folder: what it was asked, so that the same meeting processed again continues in it.
KEPT_RECORD = "kept.json"
STAGE_KEYS = {"frames": "app.stage.frames", "reading": "app.stage.reading", "summary": "app.stage.summary",
              "qa": "app.stage.qa", "report": "app.stage.report", "preparing": "app.stage.preparing",
              "saving": "app.stage.saving"}


class JobError(texts.Failure):
    """A request to process that cannot be started; nothing was done."""


def label(name, language):
    return texts.Message(STAGE_KEYS[name]).text(language) if name in STAGE_KEYS else ""


class Stage:
    def __init__(self, name):
        self.name = name
        self.state = "pending"  # pending, running, done, skipped, failed
        self.seconds = 0.0  # set when the stage ends
        self.started = None  # time.monotonic() when it began, for the seconds of a stage still running
        self.cost_usd = 0.0

    def as_dict(self, language=texts.DEFAULT_LANGUAGE):
        # While it runs, the time since it began (the page showed 0 s until the stage ended, WI24);
        # when it ends, its final seconds.
        running = self.state == "running" and self.started is not None
        seconds = time.monotonic() - self.started if running else self.seconds
        return {"name": self.name, "label": label(self.name, language), "state": self.state,
                "seconds": round(seconds, 1), "cost_usd": round(self.cost_usd, 4)}


class Job:
    def __init__(self, request):
        self.id = secrets.token_hex(8)
        self.request = request
        self.state = "running"  # running, done, failed
        self.stages = [Stage(name) for name in ("frames", "reading", request["format"], "report")]
        self.counters = gemini.new_counters()
        self.error = ""  # the message of what failed: a texts.Message, or text
        self.failed_stage = ""
        self.meeting_id = ""
        self.run_id = ""
        self.kept = None  # after a failure that kept what was paid: {"run", "paid_usd"}
        self.started = time.monotonic()
        self.seconds = 0.0

    def as_dict(self, language=texts.DEFAULT_LANGUAGE):
        """The job as the page reads it, in the application's language: what
        failed is said in it, and what came from outside comes as `detail`."""
        seconds = self.seconds if self.state != "running" else time.monotonic() - self.started
        error, detail = texts.said(self.error, language)
        return {"id": self.id, "state": self.state, "project": self.request["project"],
                "title": self.request["title"], "stages": [stage.as_dict(language) for stage in self.stages],
                "spent_usd": round(self.counters["spent"], 4), "max_cost_usd": self.request["max_cost"],
                "seconds": round(seconds, 1), "error": error, "detail": detail,
                "failed_stage": label(self.failed_stage, language), "failed_stage_name": self.failed_stage,
                "meeting": self.meeting_id, "kept": self.kept}


def _date(value):
    try:
        if len(value) == 10 and datetime.date.fromisoformat(value).isoformat() == value:
            return value
    except ValueError:
        pass
    raise JobError("app.request.bad_date", value=value)


def check_request(data, data_dir, uploads, meeting_types, languages):
    """The processing request, checked before anything is done."""
    def text(name):
        value = data.get(name, "")
        if not isinstance(value, str):
            raise JobError("app.request.not_text", name=name)
        return value.strip()

    project_id = text("project")
    try:
        project = library.project(data_dir, project_id)
    except library.NotFound:
        raise JobError("app.request.no_project", project=project_id) from None
    title = text("title")
    if not title:
        raise JobError("app.request.needs_title")
    date = _date(text("date"))
    meeting_type = text("meeting_type")
    if meeting_type and meeting_type not in meeting_types:
        raise JobError("app.request.no_type", value=meeting_type)
    language = text("language")
    if language and language not in languages:
        raise JobError("app.request.no_language", value=language)
    kind = text("format") or "summary"
    if kind not in FORMATS:
        raise JobError("app.request.no_format", value=kind)
    transcript = uploads.get(text("transcript"), TRANSCRIPT_SUFFIXES)
    if transcript is None:
        raise JobError("app.request.no_transcript")
    recording = None
    if text("recording"):
        recording = uploads.get(text("recording"), RECORDING_SUFFIXES)
        if recording is None:
            raise JobError("app.request.video_gone")
    if kind == "summary" and recording is None:
        raise JobError("app.request.summary_needs_video")
    if kind == "qa":
        try:
            nobody = transcript_module.names_no_one(transcript)
        except transcript_module.TranscriptError:
            nobody = False  # an unreadable transcript fails where it always did, in the run
        if nobody:
            raise JobError("app.request.qa_needs_speakers")
    max_cost = data.get("max_cost", DEFAULT_MAX_COST_USD)
    if isinstance(max_cost, bool) or not isinstance(max_cost, (int, float)) or not 0 < max_cost <= 5:
        raise JobError("app.request.bad_ceiling")
    return {"project": project_id, "project_name": project["name"], "client": project.get("client") or "",
            "title": title, "date": date,
            "meeting_type": meeting_type or None, "language": language or None, "format": kind,
            "transcript": transcript, "recording": recording, "max_cost": float(max_cost)}


class Uploads:
    """Files uploaded by the page, kept in <data>/.meetingtool-uploads until a
    run takes them. Named by the server, never by the page."""

    def __init__(self, data_dir):
        self.folder = Path(data_dir) / ".meetingtool-uploads"
        self.lock = threading.Lock()

    def clear(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def new_path(self, suffix):
        store.check_data_dir(self.folder.parent)
        self.folder.mkdir(parents=True, exist_ok=True)
        return self.folder / f"{secrets.token_hex(12)}{suffix}"

    def get(self, name, suffixes):
        if not name or "/" in name or "\\" in name or not name.endswith(suffixes):
            return None
        stem = name.rsplit(".", 1)[0]
        if len(stem) != 24 or any(c not in "0123456789abcdef" for c in stem):
            return None
        path = self.folder / name
        return path if path.is_file() else None

    def discard(self, names):
        """Remove the uploads of a request that was refused."""
        for name in names:
            path = self.get(name, TRANSCRIPT_SUFFIXES + RECORDING_SUFFIXES) if isinstance(name, str) else None
            if path is not None:
                path.unlink(missing_ok=True)


def forget_meeting(data_dir, project_id, folder_name):
    """Remove a meeting record that names folder_name, if one was left by a
    save that failed, and rebuild the project's knowledge, so a failed save
    leaves no meeting behind. A record that cannot be read is not this run's
    (its own was written whole) and is left as it is. Never raises: it runs
    while a failure is being settled."""
    try:
        meetings = Path(data_dir) / project_id / "meetings"
        removed = False
        with store.data_lock(data_dir):
            for record in meetings.glob("*/meeting.json") if meetings.is_dir() else ():
                try:
                    named = json.loads(record.read_text(encoding="utf-8")).get("folder")
                except (OSError, ValueError, AttributeError):
                    continue
                if named == folder_name:
                    shutil.rmtree(record.parent, ignore_errors=True)
                    removed = True
            if removed:
                store.rebuild_knowledge(data_dir, project_id)
    except Exception:  # noqa: BLE001 - the failure being settled is what the job reports
        pass


def holds_paid(folder):
    """True if a run's folder holds an accepted answer that was paid for."""
    folder = Path(folder)
    return any((folder / gemini.KEPT_DIR).glob("*.json")) or any((folder / qa.PARTS_DIR).glob("part-*.json"))


def kept_cost(folder):
    """What the answers kept in a run's folder cost, as each one recorded it:
    known even when the process that paid for them died before saying so."""
    total = 0.0
    for kept in (Path(folder) / gemini.KEPT_DIR).glob("*.json"):
        try:
            cost = json.loads(kept.read_text(encoding="utf-8")).get("cost_usd")
        except (OSError, ValueError, AttributeError):
            continue
        total += cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else 0.0
    return total


def request_fingerprint(request):
    """What makes two requests the same meeting for continuing a kept run:
    the project, the format and the transcript's bytes. Each kept answer is
    used only for the exact same request to Gemini (gemini.call_checked), so
    anything else that changed (the title, the recording) pays again."""
    digest = hashlib.sha256(f"{request['project']}\n{request['format']}\n".encode("utf-8"))
    with open(request["transcript"], "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _kept_record(folder):
    try:
        record = json.loads((Path(folder) / KEPT_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def kept_runs(data_dir, project_id):
    """The runs of a project that failed (or were cut short) keeping what was
    paid, newest first: {"run", "title", "date", "format", "failed_stage",
    "paid_usd", "failed_utc"}."""
    folder = Path(data_dir) / project_id / library.PROCESSING_DIR
    found = []
    for run in sorted(folder.iterdir()) if folder.is_dir() else ():
        record = _kept_record(run)
        if record is None or not library.is_slug(run.name) or not holds_paid(run):
            continue
        paid = record.get("paid_usd")
        paid = float(paid) if isinstance(paid, (int, float)) and not isinstance(paid, bool) else 0.0
        found.append({"run": run.name, "title": str(record.get("title", "")), "date": str(record.get("date", "")),
                      "format": str(record.get("format", "")), "failed_stage": str(record.get("failed_stage", "")),
                      "paid_usd": round(max(paid, kept_cost(run)), 4),
                      "failed_utc": str(record.get("failed_utc", ""))})
    return sorted(found, key=lambda run: run["failed_utc"], reverse=True)


def _kept_for(project_dir, fingerprint):
    """The folder of the newest kept run of the same meeting, or None."""
    for run in kept_runs(project_dir.parent, project_dir.name):
        folder = project_dir / library.PROCESSING_DIR / run["run"]
        if (_kept_record(folder) or {}).get("fingerprint") == fingerprint:
            return folder
    return None


def discard_kept(data_dir, project_id, run):
    """Remove what a failed run kept, at the person's request; NotFound if
    there is no such kept run."""
    if not all(isinstance(value, str) and library.is_slug(value) for value in (project_id, run)):
        raise library.NotFound(str(run))
    if run not in {kept["run"] for kept in kept_runs(data_dir, project_id)}:
        raise library.NotFound(run)
    processing = Path(data_dir) / project_id / library.PROCESSING_DIR
    shutil.rmtree(processing / run)
    try:
        processing.rmdir()
    except OSError:
        pass


def _named_folders(project_dir):
    """The results folders the project's meeting records name, read as they
    are: an unreadable record names none."""
    named = set()
    for record in (project_dir / "meetings").glob("*/meeting.json"):
        try:
            named.add(json.loads(record.read_text(encoding="utf-8")).get("folder"))
        except (OSError, ValueError, AttributeError):
            continue
    return named


def _settle_cut_saves(data_dir):
    """A process that died while saving a run leaves a results folder still
    holding KEPT_RECORD: if a meeting names it, the save had ended and the
    record goes; if none does, the folder goes back to being a kept run."""
    for results in data_dir.glob(f"*/{library.RESULTS_DIR}"):
        project_dir = results.parent
        if not (project_dir / "project.json").is_file():
            continue
        cut = [run for run in results.iterdir() if (run / KEPT_RECORD).is_file()]
        if not cut:
            continue
        named = _named_folders(project_dir)
        for run in cut:
            if f"{library.RESULTS_DIR}/{run.name}" in named:
                (run / KEPT_RECORD).unlink()
            else:
                (project_dir / library.PROCESSING_DIR).mkdir(exist_ok=True)
                os.replace(run, project_dir / library.PROCESSING_DIR / run.name)


def clear_leftovers(data_dir):
    """What a run cut short by closing the window left: a save cut half way
    (_settle_cut_saves), a knowledge file one meeting behind (a process that
    died between saving a meeting's record and rewriting it), the working
    folders of every project that hold nothing paid (one that does is kept,
    as a failed run's), and the uploads no run took. Called at start, while
    this session holds the data folder's lock."""
    data_dir = Path(data_dir)
    with store.data_lock(data_dir):
        _settle_cut_saves(data_dir)
        for project in data_dir.glob("*/project.json"):
            try:
                store.rebuild_knowledge(data_dir, project.parent.name)
            except store.ProjectError:
                pass  # an unreadable record: listing the project names it
    for folder in data_dir.glob(f"*/{library.PROCESSING_DIR}"):
        if not (folder.parent / "project.json").is_file():
            continue
        for run in folder.iterdir():
            if not run.is_dir():
                run.unlink(missing_ok=True)
            elif not holds_paid(run):
                shutil.rmtree(run, ignore_errors=True)
        try:
            folder.rmdir()
        except OSError:
            pass
    Uploads(data_dir).clear()


class Runner:
    """Starts one run at a time in a thread of its own and keeps every job of
    this session, to be asked how it goes."""

    def __init__(self, data_dir, read_key, endpoint=gemini.ENDPOINT, sleep=time.sleep, retry_delays=None):
        self.data_dir = Path(data_dir)
        self.read_key = read_key
        self.endpoint = endpoint
        self.sleep = sleep
        self.retry_delays = gemini.RETRY_DELAYS if retry_delays is None else retry_delays
        self.jobs = {}
        self.lock = threading.Lock()

    def running(self):
        with self.lock:
            return next((job for job in self.jobs.values() if job.state == "running"), None)

    def discard(self, project_id, run):
        """Discard a kept run, never while a run is going on: it may be
        continuing in that very folder. Under the same lock that starts a run,
        so a run cannot start between the check and the removal (WI20's
        review, P3-2)."""
        with self.lock:
            if any(job.state == "running" for job in self.jobs.values()):
                raise JobError("app.run.busy")
            discard_kept(self.data_dir, project_id, run)

    def start(self, request, wait=False):
        key = self.read_key()
        if not key:
            raise JobError("app.run.no_key")
        with self.lock:
            if any(job.state == "running" for job in self.jobs.values()):
                raise JobError("app.run.busy")
            job = Job(request)
            self.jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job, key), daemon=True)
        thread.start()
        if wait:
            thread.join()
        return job

    def _stage(self, job, name, call):
        stage = next(s for s in job.stages if s.name == name)
        spent, started = job.counters["spent"], time.monotonic()
        stage.started = started
        stage.state = "running"
        try:
            value = call()
        except BaseException:
            stage.state = "failed"
            job.failed_stage = name
            raise
        finally:
            stage.seconds = time.monotonic() - started
            stage.cost_usd = job.counters["spent"] - spent
        stage.state = "done"
        return value

    def _run(self, job, key):
        # Imported here: the frames need av and numpy, the report python-docx.
        from meetingtool.frames.extract import extract_frames
        from meetingtool.report import document
        from meetingtool.summary import writer

        request = job.request
        project_dir = self.data_dir / request["project"]
        work = final = None
        folder_name = ""
        added, moved, phase = False, False, "preparing"
        try:
            store.check_data_dir(project_dir)
            fingerprint = request_fingerprint(request)
            work = _kept_for(project_dir, fingerprint)
            kept = _kept_record(work) if work is not None else None
            if work is not None:
                # Only what was paid goes on: anything else of the attempt before (its frames, its
                # readings, a copy of its recording) is not this run's (WI20's review, P3-4).
                for entry in work.iterdir():
                    if entry.name in (KEPT_RECORD, gemini.KEPT_DIR, qa.PARTS_DIR):
                        continue
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
            else:
                run_id = f"{request['date']}-{store.slugify(request['title'], fallback='meeting')[:40].strip('-')}-" \
                         f"{secrets.token_hex(3)}"
                work = project_dir / library.PROCESSING_DIR / run_id
                work.mkdir(parents=True)
                kept = {"paid_usd": 0.0}
            paid_before = max(kept.get("paid_usd") if isinstance(kept.get("paid_usd"), (int, float)) else 0.0,
                              kept_cost(work))
            job.run_id = work.name
            final = project_dir / library.RESULTS_DIR / work.name
            folder_name = f"{library.RESULTS_DIR}/{work.name}"
            kept.update(fingerprint=fingerprint, title=request["title"], date=request["date"],
                        format=request["format"], started_utc=store._now_utc())
            disk.write_text(work / KEPT_RECORD, json.dumps(kept, ensure_ascii=False, indent=2) + "\n")
            transcript = work / f"transcript{request['transcript'].suffix.lower()}"
            os.replace(request["transcript"], transcript)
            if request["recording"] is not None:
                recording = work / f"recording{request['recording'].suffix.lower()}"
                os.replace(request["recording"], recording)
                extracted = self._stage(job, "frames", lambda: extract_frames(recording, work,
                                                                               transcript=str(transcript)))
                recording.unlink()  # the meeting keeps its frames, not a copy of the recording
            else:
                job.stages[0].state = "skipped"
                extracted = None
            if request["format"] == "summary":
                self._stage(job, "reading", lambda: gemini.read_frames(
                    work, key, endpoint=self.endpoint, retry_delays=self.retry_delays, sleep=self.sleep,
                    max_cost_usd=request["max_cost"], counters=job.counters))
            else:
                job.stages[1].state = "skipped"
            later = {}

            def record_later(*args, **kwargs):
                later["args"], later["kwargs"] = args, kwargs
                return {"id": ""}

            write = qa.write_register if request["format"] == "qa" else writer.write_summary
            written = self._stage(job, request["format"], lambda: write(
                work, transcript, key, data_dir=self.data_dir, project=request["project"], title=request["title"],
                date=request["date"], meeting_type=request["meeting_type"], language=request["language"],
                endpoint=self.endpoint, max_cost_usd=request["max_cost"], retry_delays=self.retry_delays,
                sleep=self.sleep, counters=job.counters, add_meeting=record_later))
            report = self._stage(job, "report", lambda: document.build_report(
                work, title=request["title"], date=request["date"], project_name=request["project_name"],
                client=request["client"], meeting_type=request["meeting_type"], data_dir=self.data_dir))
            phase = "saving"
            run = {"format": request["format"], "language": written.language,
                   "meeting_type": request["meeting_type"] or "", "max_cost_usd": request["max_cost"],
                   "cost_usd": round(job.counters["spent"], 4), "seconds": round(time.monotonic() - job.started, 1),
                   # what earlier attempts that failed paid for this meeting (WI20's review, P3-5)
                   "paid_before_usd": round(paid_before, 4),
                   "stages": [stage.as_dict() for stage in job.stages],
                   "models": sorted(job.counters["models"]), "requests": job.counters["attempts"],
                   "frames_kept": len(extracted.kept) if extracted else 0,
                   "frames_read": written.frames_read if request["format"] == "qa" else
                   (len(extracted.kept) if extracted else 0),
                   "report_images": report.images, "finished_utc": store._now_utc()}
            disk.write_text(work / library.RUN_NAME, json.dumps(run, indent=2, ensure_ascii=False) + "\n")
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                raise JobError("app.run.folder_taken", folder=folder_name)
            os.replace(work, final)
            moved = True
            later["kwargs"]["transcript"] = str(final / transcript.name)
            record = store.add_meeting(*later["args"], **later["kwargs"], meeting_folder=folder_name)
            added = True
            job.meeting_id = record["id"]
            (final / KEPT_RECORD).unlink(missing_ok=True)  # a result now, not a kept run
        except Exception as error:  # every failure ends the job with its reason
            job.error = error.message if isinstance(error, texts.Failure) else texts.Message(
                "app.unexpected", detail=texts.External(str(error) or error.__class__.__name__))
            job.failed_stage = job.failed_stage or phase
        finally:
            try:
                if not added:
                    self._settle_failure(job, project_dir, work, final, folder_name, moved)
                try:
                    (project_dir / library.PROCESSING_DIR).rmdir()
                except OSError:
                    pass
            except Exception as error:  # noqa: BLE001 - the job must end, and say why
                job.error = job.error or texts.Message("app.unexpected", detail=texts.External(str(error)))
            # Said last: a page told the run failed finds it settled.
            job.seconds = time.monotonic() - job.started
            job.state = "done" if added else "failed"

    def _settle_failure(self, job, project_dir, work, final, folder_name, moved):
        """After a failure: no meeting added, no results folder left, and the
        working folder kept if it holds something paid, removed otherwise."""
        request = job.request
        if moved:  # the save failed after the folder became a result: it goes back to being worked on
            forget_meeting(self.data_dir, request["project"], folder_name)
            try:
                os.replace(final, work)
            except OSError:
                shutil.rmtree(final, ignore_errors=True)  # never a folder this run did not make
        if work is not None and work.is_dir():
            if holds_paid(work):
                record = _kept_record(work) or {}
                paid = record.get("paid_usd") if isinstance(record.get("paid_usd"), (int, float)) else 0.0
                record.update(paid_usd=round(max(paid + job.counters["spent"], kept_cost(work)), 4),
                              failed_stage=job.failed_stage, failed_utc=store._now_utc())
                disk.write_text(work / KEPT_RECORD, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                job.kept = {"run": work.name, "paid_usd": record["paid_usd"]}
            else:
                shutil.rmtree(work, ignore_errors=True)
        for leftover in (request["transcript"], request["recording"]):
            if leftover is not None and leftover.exists():
                leftover.unlink()
