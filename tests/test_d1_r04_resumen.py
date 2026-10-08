"""The external review's R04 (2026-10-02), written by INGOL's pilot package for D1
(docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/pruebas/
test_d1_hallazgos_arquitecto.py of INGOL), failing on 03b8573: check_summary looked
at the headings and not at what is under them, so a STOP answer with the nine
headings and eight of them empty was accepted and turned into a Word report. WI25
copies AR06ResumenVacio with the class's code as INGOL wrote it (docs/evidence/
01M4B3HE2AVWM7CEPPNRWS9SFY/compare_pilot_tests.py checks it). It imports nothing of
INGOL's kits, so the CI runs it. The other half of R04, the register's years and
figures, is TrazabilidadDelRegistro in test_d1_barrido.py, which needs the kits.

    python -m unittest tests.test_d1_r04_resumen
"""

import unittest

from meetingtool.summary import writer
from tests import test_summary


class AR06ResumenVacio(unittest.TestCase):
    """AR-06 (P2, resultado): check_summary mira títulos, no contenido.

    En verde si: cada sección exige contenido (o la línea explícita de que no
    hubo nada)."""

    def test_d1_ar06_un_resumen_con_las_secciones_vacias_se_rechaza(self):
        titulos = writer.required_headings("es")
        texto = "\n\n".join(f"## {t}" for t in titulos[:-1]) + f"\n\n## {titulos[-1]}\n- Se habló de la planta.\n"
        with self.assertRaises(writer.SummaryError, msg="un resumen con 8 secciones vacías se entrega"):
            writer.check_summary(test_summary.answer(texto), titulos, "es", frame_names=set())
