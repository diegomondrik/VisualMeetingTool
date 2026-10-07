"""WI25-AC01: the two classes of INGOL's pilot tests that WI25 copied into tests/ are INGOL's,
their code unchanged.

    python docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/compare_pilot_tests.py <INGOL's pruebas folder>

The folder is docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/
pruebas/ of INGOL's repository. Exit 0 when both classes match. What the script
does not compare is each file's header and imports (AR06ResumenVacio's file does
not import INGOL's kits, which the class does not use; test_d1_barrido.py keeps
the one import of the kits that skips it without them), and the classes WI20
copied into test_d1_barrido.py, which docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/
compare_pilot_tests.py checks. A class that is not there or differs makes it
exit 1; the script lists classes it does not know.
"""

import ast
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
# (INGOL's file, the copy's file, the classes of this work item).
COPIED = [
    ("test_d1_hallazgos_arquitecto.py", "test_d1_r04_resumen.py", ["AR06ResumenVacio"]),
    ("test_d1_barrido.py", "test_d1_barrido.py", ["TrazabilidadDelRegistro"]),
]


def classes(path):
    text = path.read_text(encoding="utf-8")
    return {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body
            if isinstance(node, ast.ClassDef)}


def main(ingol):
    ingol = Path(ingol)
    differ = 0
    for theirs_name, ours_name, wanted in COPIED:
        theirs, ours = classes(ingol / theirs_name), classes(REPOSITORY / "tests" / ours_name)
        for cls in wanted:
            same = cls in theirs and ours.get(cls) == theirs[cls]
            differ += not same
            print(f"{ours_name} {cls}: {'same as INGOL' if same else 'DIFFERS'}")
        extra = sorted(set(ours) - set(wanted))
        if extra:
            print(f"{ours_name}: other classes (not this work item's): {extra}")
    print("both copied classes are INGOL's" if not differ else f"{differ} class(es) differ")
    return 0 if not differ else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
