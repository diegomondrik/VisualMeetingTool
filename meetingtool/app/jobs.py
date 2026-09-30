"""Processing a meeting from start to end, as the commands do it in order.

The stages are the commands' functions: the frames of the recording
(meetingtool.frames, only with a recording), their reading (meetingtool.reading,
only for the summary, which needs it), the summary or the register with what
the project knows (meetingtool.summary), and the Word report
(meetingtool.report). One spending meter is shared by the stages that pay, so
one ceiling covers the whole run.

Nothing is added to the project until the report is built: the run works in
<project>/processing/<run>, moves it to <project>/results/<run> and only then
adds the meeting, naming that folder. If anything fails, the working folder
is removed and the meeting is not added; the job says which stage failed, why,
and what was spent. One run at a time.
"""

import datetime
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path

from meetingtool.app import library
from meetingtool.projects import store
from meetingtool.reading import gemini

FORMATS = ("summary", "qa")
TRANSCRIPT_SUFFIXES = (".docx", ".txt")
RECORDING_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".m4v")
LABELS = {"frames": "Imágenes del video", "reading": "Lectura de las imágenes", "summary": "Resumen",
          "qa": "Preguntas y respuestas", "report": "Informe en Word", "preparing": "Preparación",
          "saving": "Guardar la reunión en el proyecto"}


class JobError(Exception):
    """A request to process that cannot be started; nothing was done."""


class Stage:
    def __init__(self, name):
        self.name = name
        self.state = "pending"  # pending, running, done, skipped, failed
        self.seconds = 0.0
        self.cost_usd = 0.0

    def as_dict(self):
        return {"name": self.name, "label": LABELS[self.name], "state": self.state,
                "seconds": round(self.seconds, 1), "cost_usd": round(self.cost_usd, 4)}


class Job:
    def __init__(self, request):
        self.id = secrets.token_hex(8)
        self.request = request
        self.state = "running"  # running, done, failed
        self.stages = [Stage(name) for name in ("frames", "reading", request["format"], "report")]
        self.counters = gemini.new_counters()
        self.error = ""
        self.failed_stage = ""
        self.meeting_id = ""
        self.started = time.monotonic()
        self.seconds = 0.0

    def as_dict(self):
        seconds = self.seconds if self.state != "running" else time.monotonic() - self.started
        return {"id": self.id, "state": self.state, "project": self.request["project"],
                "title": self.request["title"], "stages": [stage.as_dict() for stage in self.stages],
                "spent_usd": round(self.counters["spent"], 4), "max_cost_usd": self.request["max_cost"],
                "seconds": round(seconds, 1), "error": self.error,
                "failed_stage": LABELS.get(self.failed_stage, ""), "meeting": self.meeting_id}


def _date(value):
    try:
        if len(value) == 10 and datetime.date.fromisoformat(value).isoformat() == value:
            return value
    except ValueError:
        pass
    raise JobError(f"la fecha {value!r} no es una fecha AAAA-MM-DD válida")


def check_request(data, data_dir, uploads, meeting_types, languages):
    """The processing request, checked before anything is done."""
    def text(name):
        value = data.get(name, "")
        if not isinstance(value, str):
            raise JobError(f"el campo {name} no es texto")
        return value.strip()

    project_id = text("project")
    try:
        project = library.project(data_dir, project_id)
    except library.NotFound:
        raise JobError(f"no hay un proyecto {project_id!r}") from None
    title = text("title")
    if not title:
        raise JobError("la reunión necesita un título")
    date = _date(text("date"))
    meeting_type = text("meeting_type")
    if meeting_type and meeting_type not in meeting_types:
        raise JobError(f"no hay un tipo de reunión {meeting_type!r}")
    language = text("language")
    if language and language not in languages:
        raise JobError(f"no hay un idioma {language!r}")
    kind = text("format") or "summary"
    if kind not in FORMATS:
        raise JobError(f"no hay un formato {kind!r}")
    transcript = uploads.get(text("transcript"), TRANSCRIPT_SUFFIXES)
    if transcript is None:
        raise JobError("falta la transcripción (un .docx de Teams o un .txt con líneas [HH:MM:SS])")
    recording = None
    if text("recording"):
        recording = uploads.get(text("recording"), RECORDING_SUFFIXES)
        if recording is None:
            raise JobError("el video subido ya no está: subilo de nuevo")
    if kind == "summary" and recording is None:
        raise JobError("el resumen necesita el video, para leer lo que se mostró; sin video, elegí el formato "
                       "preguntas y respuestas")
    max_cost = data.get("max_cost", 0.50)
    if isinstance(max_cost, bool) or not isinstance(max_cost, (int, float)) or not 0 < max_cost <= 5:
        raise JobError("el techo de gasto tiene que ser un número de dólares mayor que 0 y hasta 5")
    return {"project": project_id, "project_name": project["name"], "title": title, "date": date,
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

    def start(self, request, wait=False):
        key = self.read_key()
        if not key:
            raise JobError("no hay una clave de Gemini guardada: guardala en Ajustes")
        with self.lock:
            if any(job.state == "running" for job in self.jobs.values()):
                raise JobError("ya hay una reunión procesándose: esperá a que termine")
            job = Job(request)
            self.jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job, key), daemon=True)
        thread.start()
        if wait:
            thread.join()
        return job

    def _stage(self, job, name, call):
        stage = next(s for s in job.stages if s.name == name)
        stage.state = "running"
        spent, started = job.counters["spent"], time.monotonic()
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
        from meetingtool.summary import qa, writer

        request = job.request
        project_dir = self.data_dir / request["project"]
        run_id = f"{request['date']}-{store.slugify(request['title'], fallback='meeting')[:40].strip('-')}-" \
                 f"{secrets.token_hex(3)}"
        work = project_dir / library.PROCESSING_DIR / run_id
        final = project_dir / library.RESULTS_DIR / run_id
        added, phase = False, "preparing"
        try:
            store.check_data_dir(project_dir)
            work.mkdir(parents=True)
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
                data_dir=self.data_dir))
            phase = "saving"
            run = {"format": request["format"], "language": written.language,
                   "meeting_type": request["meeting_type"] or "", "max_cost_usd": request["max_cost"],
                   "cost_usd": round(job.counters["spent"], 4), "seconds": round(time.monotonic() - job.started, 1),
                   "stages": [stage.as_dict() for stage in job.stages],
                   "models": sorted(job.counters["models"]), "requests": job.counters["attempts"],
                   "frames_kept": len(extracted.kept) if extracted else 0,
                   "frames_read": written.frames_read if request["format"] == "qa" else
                   (len(extracted.kept) if extracted else 0),
                   "report_images": report.images, "finished_utc": store._now_utc()}
            (work / library.RUN_NAME).write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(work, final)
            later["kwargs"]["transcript"] = str(final / transcript.name)
            record = store.add_meeting(*later["args"], **later["kwargs"],
                                       meeting_folder=f"{library.RESULTS_DIR}/{run_id}")
            added = True
            job.meeting_id = record["id"]
        except Exception as error:  # every failure ends the job with its reason
            job.error = str(error) or error.__class__.__name__
            job.failed_stage = job.failed_stage or phase
        finally:
            if not added:
                shutil.rmtree(work, ignore_errors=True)
                shutil.rmtree(final, ignore_errors=True)
                for leftover in (request["transcript"], request["recording"]):
                    if leftover is not None and leftover.exists():
                        leftover.unlink()
            try:
                (project_dir / library.PROCESSING_DIR).rmdir()
            except OSError:
                pass
            # Said last: a page told the run failed finds nothing left of it.
            job.seconds = time.monotonic() - job.started
            job.state = "done" if added else "failed"
