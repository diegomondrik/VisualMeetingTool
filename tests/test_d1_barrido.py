"""The sweep of INGOL's tester for D1 (fault, concurrency, input and result
tests), at docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/
pruebas/test_d1_barrido.py of INGOL, failing on 03b8573. WI20 copies the
classes of its family (R01 and R03); each class is INGOL's (docs/evidence/
01M46KHBYCXMGM0K6N2RM651PE/compare_pilot_tests.py checks it).

    PYTHONPATH=<home>/.claude/ingol-kits/python python -m unittest discover -s tests -p "test_d1_*"
"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

try:
    from ingol_kits import intercalar
except ImportError:  # INGOL's kits are not in this public repository nor in its CI
    raise unittest.SkipTest("ingol_kits is not on the import path: these tests run with "
                            "PYTHONPATH=<home>/.claude/ingol-kits/python (WI20)") from None

from meetingtool.projects import store
from meetingtool.reading import gemini
from tests.test_reading import KEY, FakeGemini, answer_for


class ConocimientoAMedioEscribir(unittest.TestCase):
    """rebuild_knowledge abre knowledge.md con 'w' (lo trunca) y después
    escribe. Un resumen que lee lo que sabe el proyecto (knowledge_context)
    mientras otro proceso agrega una reunión lee un archivo vacío o cortado, y
    el pedido se paga sin el conocimiento del proyecto, sin que nada falle
    (write_summary sólo lo agrega 'if knowledge.strip()').

    En verde si: knowledge.md se escribe a un parcial y se reemplaza con
    os.replace (la lectura ve el de antes o el de después)."""

    def test_d1_leer_el_conocimiento_mientras_se_agrega_una_reunion_lo_ve_entero(self):
        def preparar(carpeta):
            store.create_project(carpeta, "Proyecto", "Cliente")
            store.add_meeting(carpeta, "proyecto", "Existente", "2026-09-10", summary="La de antes.")

        def agregar(carpeta):
            return store.add_meeting(carpeta, "proyecto", "Nueva", "2026-09-25", summary="La nueva.")

        def leer(carpeta):
            return store.knowledge_context(carpeta, "proyecto")

        def verificar(carpeta, a, b):
            assert b.error is None, f"la lectura falló: {b.error!r}"
            assert "La de antes." in b.valor, f"el resumen leyó un conocimiento sin lo de antes: {b.valor!r:.80}"

        intercalar.afirmar_sin_problemas(intercalar.explorar(preparar, agregar, leer, verificar))


class ProyectosConElMismoNombre(unittest.TestCase):
    """P3: create_project mira si la carpeta existe y después escribe. Dos
    pedidos a la vez (dos pestañas; el servidor atiende cada uno en un hilo)
    con el mismo nombre responden los dos 'creado' y el segundo pisa al
    primero.

    En verde si: la carpeta del proyecto se crea con mkdir(exist_ok=False) y
    el que llega segundo recibe projects.exists."""

    def test_d1_dos_altas_del_mismo_proyecto_no_se_pisan(self):
        def crear(cliente):
            return lambda carpeta: store.create_project(carpeta, "Proyecto Nuevo", cliente)

        def verificar(carpeta, a, b):
            ok = [s for s in (a, b) if s.error is None]
            assert all(s.error is None or isinstance(s.error, store.ProjectError) for s in (a, b)), \
                f"error inesperado: {a.error!r} {b.error!r}"
            clientes = [p["client"] for p in store.list_projects(carpeta)]
            assert len(ok) == len(clientes), (f"{len(ok)} altas respondieron 'creado' y quedaron {len(clientes)} "
                                              f"proyecto(s): {clientes}")

        intercalar.afirmar_sin_problemas(intercalar.explorar(
            lambda carpeta: None, crear("Cliente A"), crear("Cliente B"), verificar))


class LecturaEnTandas(unittest.TestCase):
    """read_frames manda las imágenes en tandas de 70 (hasta 150 imágenes: 3
    pedidos pagos) y escribe frames_read.md sólo si todas salen bien. Si falla
    una tanda posterior, las anteriores (ya pagadas) se tiran, también en la
    línea de comandos; repetir paga todo otra vez. qa._keep ya resuelve esto
    para el registro de preguntas.

    En verde si: cada tanda aceptada se guarda (como qa-parts, con el digest
    del pedido) y se reutiliza al repetir."""

    def test_d1_repetir_una_lectura_que_fallo_en_la_ultima_tanda_no_repaga_las_anteriores(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "frames"
            carpeta.mkdir()
            for n in (1, 2, 3):
                Image.new("RGB", (64, 36), (60 * n, 30, 30)).save(carpeta / f"frame_00{n}_t00-00-0{n}.jpg")
            leer = dict(retry_delays=(), sleep=lambda s: None, chunk_size=1)
            with FakeGemini([answer_for, answer_for, 400]) as fake:
                with self.assertRaises(gemini.ReadingError):
                    gemini.read_frames(carpeta, KEY, endpoint=fake.endpoint, **leer)
                primera = len(fake.requests)
            with FakeGemini() as fake:
                gemini.read_frames(carpeta, KEY, endpoint=fake.endpoint, **leer)
                segunda = len(fake.requests)
        self.assertEqual(primera, 3)
        self.assertEqual(segunda, 1, f"se volvieron a pagar las {segunda - 1} tandas ya aceptadas")
