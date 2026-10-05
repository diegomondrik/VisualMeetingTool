"""WI20-AC02 with INGOL's fault cutter: every write boundary of creating a
project, of each setting (language, company name, logo, template) and of
the save of a run of the application, cut by a disk error and by a process
that dies. After each cut, everything lists and opens, what was there before
is intact, and the operation happened entirely or not at all. (Adding a
meeting is AR02EscrituraNoAtomica, in test_d1_hallazgos_arquitecto.py.)

Needs INGOL's kits, as the other test_d1_* files:

    PYTHONPATH=<home>/.claude/ingol-kits/python python -m unittest discover -s tests -p "test_d1_*"
"""

import io
import json
import threading
import unittest
from unittest import mock

from PIL import Image

try:
    from ingol_kits import fallas
except ImportError:  # INGOL's kits are not in this public repository nor in its CI
    raise unittest.SkipTest("ingol_kits is not on the import path: these tests run with "
                            "PYTHONPATH=<home>/.claude/ingol-kits/python (WI20)") from None

from meetingtool import texts
from meetingtool.app import company, jobs, library
from meetingtool.projects import store
from meetingtool.report import document
from meetingtool.summary import writer
from tests import test_qa, test_report
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini


def image(kind, colour):
    out = io.BytesIO()
    Image.new("RGB", (40, 20), colour).save(out, kind)
    return out.getvalue()


class SettingsCutTest(unittest.TestCase):
    def test_a_project_created_or_not(self):
        def preparar(data):
            store.create_project(data, "Existente", "Cliente Demo")

        def operacion(data):
            store.create_project(data, "Proyecto Nuevo", "Cliente Demo")

        def verificar(data):
            ids = [p["id"] for p in store.list_projects(data)]
            assert "existente" in ids, ids
            for project in ids:
                store.knowledge_context(data, project)
            try:  # created again after the cut: it was made, or it is made now
                store.create_project(data, "Proyecto Nuevo", "Cliente Demo")
            except store.ProjectError as error:
                assert error.message.key == "projects.exists", error
            assert "proyecto-nuevo" in [p["id"] for p in store.list_projects(data)]

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(preparar, operacion, verificar))

    def test_the_language_and_the_name(self):
        def preparar(data):
            company.set_company_name(data, "Consultora Demo")

        def verificar(data):
            settings = company._read(data)  # it reads {} for a file it cannot parse: look at the file too
            assert settings.get("company_name") == "Consultora Demo", settings
            assert settings.get("language") in (None, "en"), settings
            if (data / company.SETTINGS_NAME).exists():
                assert company._read(data) == json.loads(
                    (data / company.SETTINGS_NAME).read_text(encoding="utf-8")), "the settings file is broken"

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(
            preparar, lambda data: company.set_language(data, "en"), verificar))

    def test_the_logo(self):
        old, new = image("PNG", (200, 30, 30)), image("JPEG", (30, 200, 30))

        def preparar(data):
            company.set_logo(data, old, "logo.png")

        def verificar(data):
            path = company.logo_path(data)
            assert path is not None, "no logo left"
            with Image.open(path) as logo:
                logo.load()  # a whole image, the old one or the new one
                colour = logo.convert("RGB").getpixel((5, 5))
            assert colour[0] > 150 or colour[1] > 150, colour

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(
            preparar, lambda data: company.set_logo(data, new, "logo.jpg"), verificar))

    def test_the_template(self):
        def preparar(data):
            document.set_template(test_report.company_template(data.parent / f"{data.name}-a.docx"), data,
                                  name="la-de-antes.docx")

        def operacion(data):
            document.set_template(test_report.company_template(data.parent / f"{data.name}-b.docx"), data,
                                  name="la-nueva.docx")

        def verificar(data):
            info = document.template_info(data)  # a template that can still be used
            assert info is not None and info.name in ("la-de-antes.docx", "la-nueva.docx"), info

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(preparar, operacion, verificar))


class RunSaveCutTest(unittest.TestCase):
    """A run of the application, cut at each of its writes: after a restart
    (clear_leftovers), the meeting is in the project with its results, or it
    is not and no results folder is left without a meeting; what was paid is
    kept or the meeting was saved."""

    def test_a_run_cut_anywhere_leaves_the_project_whole(self):
        def preparar(data):
            store.create_project(data, "Planta Demo", "Cliente Demo")
            store.add_meeting(data, "planta-demo", "Relevamiento", "2026-09-10", summary="La de antes.")

        def operacion(data):
            uploads = jobs.Uploads(data)
            transcript = uploads.new_path(".docx")
            write_teams_docx(transcript, test_qa.SPANISH)
            request = jobs.check_request(
                {"project": "planta-demo", "title": "Sesión de dudas", "date": "2026-09-25", "format": "qa",
                 "language": "es", "max_cost": 0.5, "transcript": transcript.name},
                data, uploads, writer.MEETING_TYPES, texts.LANGUAGES)
            with FakeGemini([test_qa.json_answer(test_qa.verbal())]) as fake, \
                    mock.patch.object(threading, "excepthook", lambda args: None):
                runner = jobs.Runner(data, lambda: KEY, endpoint=fake.endpoint, sleep=lambda s: None,
                                     retry_delays=(0, 0))
                runner.start(request, wait=True)

        def verificar(data):
            jobs.clear_leftovers(data)  # the application started again
            meetings = store.list_meetings(data, "planta-demo")
            titles = [m["title"] for m in meetings]
            assert "Relevamiento" in titles, titles
            knowledge = store.knowledge_context(data, "planta-demo")
            assert "La de antes." in knowledge
            project = data / "planta-demo"
            named = {m.get("folder") for m in meetings}
            results = project / library.RESULTS_DIR
            for folder in results.iterdir() if results.is_dir() else ():
                assert f"{library.RESULTS_DIR}/{folder.name}" in named, f"a results folder no meeting names: {folder}"
                assert not (folder / jobs.KEPT_RECORD).exists(), "a result still marked as kept"
            if "Sesión de dudas" in titles:
                assert (project / next(m["folder"] for m in meetings if m["title"] == "Sesión de dudas")
                        / library.REPORT_NAME).is_file()
            for kept in jobs.kept_runs(data, "planta-demo"):
                assert jobs.holds_paid(project / library.PROCESSING_DIR / kept["run"])

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(preparar, operacion, verificar))


if __name__ == "__main__":
    unittest.main()
