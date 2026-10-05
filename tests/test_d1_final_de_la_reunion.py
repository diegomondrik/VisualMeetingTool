"""R05 de la revisión externa del 2026-10-02: con transcripción, la extracción
de imágenes termina TRANSCRIPT_TAIL segundos después del *comienzo* de la
última intervención. Una explicación final larga sigue después de ese punto,
y lo que se muestra en pantalla mientras tanto se pierde antes de cualquier
llamada a Gemini.

Escrita en rojo en el piloto D1 de INGOL, sobre 03b8573, cuando una prueba
de WI10 fijaba el corte. El owner decidió el 2026-10-05 que el corte es un
defecto, y WI21 lo quitó: el video se lee hasta el final, con transcripción o
sin ella.

En verde porque el final de la reunión ya no se infiere de una marca de inicio.
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
        # create=True: the cut is gone and so is its constant; if a cut comes back under this name, a short video shows it
        with mock.patch.object(extract_module, "TRANSCRIPT_TAIL", 5.0, create=True):
            con = extract_frames(video, self.out, transcript=transcripcion)
        sin = extract_frames(video, self.tmp / "sin-transcripcion")
        self.assertEqual([which_slide(self.tmp / "sin-transcripcion" / n) for n in sin.kept], ["A", "B"],
                         "control: sin transcripción se ven las dos diapositivas")
        self.assertEqual(
            [which_slide(self.out / n) for n in con.kept], ["A", "B"],
            f"con transcripción la lectura se cortó en {getattr(con, 'read_until', None)} s y la diapositiva que siguió "
            "a la explicación se perdió")
