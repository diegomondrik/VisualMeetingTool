"""Reproductions of the external review's R01 and R03 (2026-10-02), written
by INGOL's pilot package for D1 (docs/work-items/dev-capabilities/evidence/
d1/ac05-base-revisada/pruebas/test_d1_hallazgos_arquitecto.py of INGOL),
failing on 03b8573. WI20 copies the classes of its family; each class is
INGOL's, the client's name apart (docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/
compare_pilot_tests.py checks it). The other families' classes come with
their own work items.

    PYTHONPATH=<home>/.claude/ingol-kits/python python -m unittest discover -s tests -p "test_d1_*"
"""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

try:
    from ingol_kits import fallas, intercalar
except ImportError:  # INGOL's kits are not in this public repository nor in its CI
    raise unittest.SkipTest("ingol_kits is not on the import path: these tests run with "
                            "PYTHONPATH=<home>/.claude/ingol-kits/python (WI20)") from None

from meetingtool import texts
from meetingtool.app import jobs, library
from meetingtool.projects import store
from meetingtool.report import document
from meetingtool.summary import writer
from tests import test_qa
from tests.test_frames import write_teams_docx
from tests.test_reading import KEY, FakeGemini


class Carpeta(unittest.TestCase):
    """Una carpeta de datos nueva, con un proyecto."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = self.tmp / "data"
        self.project = store.create_project(self.data, "Planta Demo Sprint 3", "Cliente Demo")["id"]

    def tearDown(self):
        self._tmp.cleanup()

    def pedido_qa(self, **campos):
        """Un pedido de registro de preguntas, armado como lo arma el servidor."""
        uploads = jobs.Uploads(self.data)
        transcript = uploads.new_path(".docx")
        write_teams_docx(transcript, test_qa.SPANISH)
        data = {"project": self.project, "title": "Sesión de dudas", "date": "2026-09-25", "format": "qa",
                "language": "es", "max_cost": 0.5, "transcript": transcript.name}
        data.update(campos)
        return jobs.check_request(data, self.data, uploads, writer.MEETING_TYPES, texts.LANGUAGES)

    def correr(self, fake, pedido):
        """Corre el pedido con el Runner de la aplicación hasta que su hilo termina.
        Devuelve (runner, job, excepciones que mataron el hilo)."""
        escapadas = []
        runner = jobs.Runner(self.data, lambda: KEY, endpoint=fake.endpoint, sleep=lambda s: None,
                             retry_delays=(0, 0))
        with mock.patch.object(threading, "excepthook", lambda args: escapadas.append(args.exc_value)):
            job = runner.start(pedido, wait=True)
        return runner, job, escapadas


class AR01TrabajoColgado(Carpeta):
    """AR-01 (P1, fallas): un registro ilegible en el proyecto hace que guardar
    la reunión falle, y la limpieza del finally lanza: el trabajo queda
    'running' para siempre y la carpeta de resultados queda huérfana.

    En verde si: el finally de Runner._run no puede lanzar (forget_meeting
    atrapa cualquier error de rebuild_knowledge) y el trabajo termina 'failed'."""

    def test_d1_ar01_un_guardado_que_falla_termina_el_trabajo_y_no_deja_carpeta(self):
        vieja = store.add_meeting(self.data, self.project, "Relevamiento", "2026-09-10", summary="Antes.")
        registro = self.data / self.project / "meetings" / vieja["id"] / "meeting.json"
        contenido = registro.read_bytes()
        registro.write_bytes(contenido[:len(contenido) // 2])  # lo que deja un corte en _write_json (AR-02)

        with FakeGemini([test_qa.json_answer(test_qa.verbal())]) as fake:
            runner, job, escapadas = self.correr(fake, self.pedido_qa())
            pagados = len(fake.requests)

        resultados = self.data / self.project / library.RESULTS_DIR
        huerfanas = sorted(p.name for p in resultados.iterdir()) if resultados.is_dir() else []
        self.assertEqual(pagados, 1, "el registro de preguntas se pagó")
        self.assertEqual(
            (job.state, runner.running() is not None, huerfanas, [type(e).__name__ for e in escapadas]),
            ("failed", False, [], []),
            "el trabajo tiene que terminar 'failed', no quedar como el que se está procesando, y no dejar una "
            "carpeta de resultados que ninguna reunión nombra; ninguna excepción tiene que matar el hilo")


class AR02EscrituraNoAtomica(unittest.TestCase):
    """AR-02 (P1, fallas): store._write_json y rebuild_knowledge escriben en el
    lugar. Un corte al cerrar meeting.json deja el registro a medias y el
    proyecto entero deja de poder listarse.

    En verde si: _write_json y knowledge.md se escriben a un parcial y se
    reemplazan con os.replace (y/o list_meetings saltea y avisa un registro
    ilegible en vez de lanzar)."""

    def test_d1_ar02_cortar_add_meeting_en_cada_frontera_deja_el_proyecto_legible(self):
        def preparar(carpeta):
            pid = store.create_project(carpeta, "Proyecto", "Cliente")["id"]
            store.add_meeting(carpeta, pid, "Existente", "2026-09-10", summary="La de antes.")

        def operacion(carpeta):
            store.add_meeting(carpeta, "proyecto", "Nueva", "2026-09-25", summary="La nueva.",
                              key_points=["Un punto"])

        def verificar(carpeta):
            titulos = [m["title"] for m in store.list_meetings(carpeta, "proyecto")]  # no puede lanzar
            assert "Existente" in titulos, f"se perdió la reunión de antes: {titulos}"
            conocimiento = store.knowledge_context(carpeta, "proyecto")
            proyecto = store._read_json(carpeta / "proyecto" / "project.json")
            completos = {store.render_knowledge(proyecto, store.list_meetings(carpeta, "proyecto"))}
            assert conocimiento in completos or conocimiento.endswith("- Un punto\n") or \
                conocimiento.rstrip().endswith("La de antes."), \
                f"knowledge.md quedó cortado: termina en {conocimiento[-40:]!r}"

        fallas.afirmar_sin_problemas(fallas.cortar_en_cada_frontera(preparar, operacion, verificar))


class AR03LoPagadoSeTira(Carpeta):
    """AR-03 (P1, arquitectura/fallas): una falla del informe, después de pagar
    el registro de preguntas, borra la carpeta de trabajo con las partes
    pagadas (qa-parts); reintentar el mismo pedido lo vuelve a pagar. La línea
    de comandos, sobre la misma carpeta, no paga dos veces (qa._keep).

    En verde si: la aplicación conserva lo pagado de una corrida fallida (la
    carpeta de trabajo o sus qa-parts en un lugar estable) y el reintento lo
    reutiliza."""

    def test_d1_ar03_reintentar_despues_de_un_informe_fallido_no_vuelve_a_pagar(self):
        with FakeGemini([test_qa.json_answer(test_qa.verbal()), test_qa.json_answer(test_qa.verbal())]) as fake:
            with mock.patch("meetingtool.report.document.build_report",
                            side_effect=document.ReportError("report.no_summary", summary="x", folder="y")):
                _, primero, _ = self.correr(fake, self.pedido_qa())
            pagados_primero = len(fake.requests)
            guardado = [p.relative_to(self.data).as_posix() for p in self.data.rglob("*")
                        if p.is_file() and "horas por kilo en la planilla" in p.read_text(encoding="utf-8",
                                                                                         errors="ignore")]
            _, segundo, _ = self.correr(fake, self.pedido_qa())
            pagados_total = len(fake.requests)

        self.assertEqual((primero.state, primero.failed_stage, pagados_primero), ("failed", "report", 1))
        self.assertEqual(segundo.state, "done", segundo.error)
        self.assertEqual(
            (pagados_total, guardado != []), (1, True),
            f"lo pagado en la corrida fallida tiene que quedar (archivos con la respuesta: {guardado}) y el "
            f"reintento no tiene que volver a pagarlo (pedidos pagados en total: {pagados_total})")


class AR05AltasSimultaneas(unittest.TestCase):
    """AR-05 (P2, concurrencia): dos add_meeting a la vez (la aplicación y la
    terminal, dos instancias sin nada en memoria) con el mismo título y la
    misma fecha calculan el mismo id y uno pisa al otro.

    En verde si: el id se reserva con una creación exclusiva (mkdir sin
    exist_ok) y knowledge.md se reconstruye bajo un candado de archivo."""

    def test_d1_ar05_dos_altas_a_la_vez_dejan_las_dos_reuniones(self):
        def preparar(carpeta):
            store.create_project(carpeta, "Proyecto", "Cliente")

        def alta(resumen):
            return lambda carpeta: store.add_meeting(carpeta, "proyecto", "Sesión", "2026-09-25", summary=resumen)

        def verificar(carpeta, a, b):
            assert a.error is None and b.error is None, f"falló un alta: {a.error!r} {b.error!r}"
            ids = [m["id"] for m in store.list_meetings(carpeta, "proyecto")]
            assert len(ids) == 2, f"quedaron {ids}: se perdió una reunión (ids devueltos {a.valor['id']}, " \
                                  f"{b.valor['id']})"
            conocimiento = store.knowledge_context(carpeta, "proyecto")
            assert "Desde la app." in conocimiento and "Desde la terminal." in conocimiento, \
                "knowledge.md no tiene las dos reuniones"

        intercalar.afirmar_sin_problemas(intercalar.explorar(
            preparar, alta("Desde la app."), alta("Desde la terminal."), verificar))


class AR10AjustesSimultaneos(unittest.TestCase):
    """AR-10 (P3, concurrencia): set_language y set_company_name leen,
    modifican y escriben app-settings.json sin exclusión (y con el mismo
    nombre de parcial): uno de los dos cambios se pierde.

    En verde si: leer-modificar-escribir corre bajo un candado (de archivo) y
    cada escritor usa un parcial de nombre único."""

    def test_d1_ar10_dos_cambios_de_ajustes_a_la_vez_quedan_los_dos(self):
        from meetingtool.app import company

        def verificar(carpeta, a, b):
            assert a.error is None and b.error is None, f"falló un cambio: {a.error!r} {b.error!r}"
            quedo = company._read(carpeta)
            assert quedo.get("language") == "en" and quedo.get("company_name") == "Acme Consultores", \
                f"se perdió un cambio: {quedo}"

        intercalar.afirmar_sin_problemas(intercalar.explorar(
            lambda carpeta: None, lambda carpeta: company.set_language(carpeta, "en"),
            lambda carpeta: company.set_company_name(carpeta, "Acme Consultores"), verificar))
