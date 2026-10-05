"""R05 de la revisión externa del 2026-10-02: con transcripción, la extracción
de imágenes termina TRANSCRIPT_TAIL segundos después del *comienzo* de la
última intervención. Una explicación final larga sigue después de ese punto,
y lo que se muestra en pantalla mientras tanto se pierde antes de cualquier
llamada a Gemini.

En rojo mientras el corte exista. Contradice a propósito
test_frames.MeetingRealityTest.test_with_a_transcript_reading_stops_soon_after_its_last_line,
que fija el corte: si es un defecto o una decisión de producto lo decide el
owner (regla del kit: la prueba se escribe en rojo y decide el owner).

En verde si: el final de la reunión no se infiere de una marca de inicio (se
lee hasta el final del video, o hasta un final que la transcripción dice).
"""

from unittest import mock

from meetingtool.frames import extract_frames
from meetingtool.frames import extract as extract_module
from tests.test_frames import SLIDE_A, SLIDE_B, Workspace, which_slide, write_video


class FinalDeLaReunion(Workspace):

    def test_d1_r05_una_explicacion_final_larga_no_pierde_la_diapositiva_que_sigue(self):
        # La última (y única) intervención empieza en 1 s y dura toda la explicación;
        # la diapositiva B aparece a los 14 s, mientras la persona sigue hablando.
        video = self.tmp / "explicacion-larga.mp4"
        write_video(video, [(SLIDE_A, 14, False), (SLIDE_B, 6, False)])
        transcripcion = self.tmp / "explicacion-larga.txt"
        transcripcion.write_text("[00:00:01] Ana:\nTe explico el tablero entero, columna por columna, "
                                 "y después pasamos al detalle del costo de proceso.\n", encoding="utf-8")
        with mock.patch.object(extract_module, "TRANSCRIPT_TAIL", 5.0):
            con = extract_frames(video, self.out, transcript=transcripcion)
        sin = extract_frames(video, self.tmp / "sin-transcripcion")
        self.assertEqual([which_slide(self.tmp / "sin-transcripcion" / n) for n in sin.kept], ["A", "B"],
                         "control: sin transcripción se ven las dos diapositivas")
        self.assertEqual(
            [which_slide(self.out / n) for n in con.kept], ["A", "B"],
            f"con transcripción la lectura se cortó en {con.read_until} s y la diapositiva que siguió "
            "a la explicación se perdió")
