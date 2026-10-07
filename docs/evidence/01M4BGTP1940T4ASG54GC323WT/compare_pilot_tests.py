"""WI26-AC01: the class of INGOL's pilot tests that WI26 copied into tests/ is INGOL's, its code unchanged, and so
is what it uses.

    python docs/evidence/01M4BGTP1940T4ASG54GC323WT/compare_pilot_tests.py <INGOL's pruebas folder>

The folder is docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/
pruebas/ of INGOL's repository. Exit 0 when TranscripcionDeTexto, the constant
TEXTO and the function turnos in tests/test_d1_barrido.py are the same as in
INGOL's test_d1_barrido.py. What the script does not compare is the file's
header and imports (this repository's file also imports `variantes` from the
kits inside the guard that skips the file without them, and
`meetingtool.frames.transcript` as `transcripcion`, as INGOL's file does). A
piece that is not there or differs makes it exit 1; the classes of the other
work items are checked by docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/ (WI20) and
docs/evidence/01M4B3HE2AVWM7CEPPNRWS9SFY/ (WI25).
"""

import ast
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
FILE = "test_d1_barrido.py"
CLASSES = ["TranscripcionDeTexto"]
CONSTANTS = ["TEXTO"]
FUNCTIONS = ["turnos"]


def pieces(path):
    """{kind and name: source} of the classes, the functions and the constants of the module's top level."""
    text = path.read_text(encoding="utf-8")
    found = {}
    for node in ast.parse(text).body:
        source = ast.get_source_segment(text, node)
        if isinstance(node, ast.ClassDef):
            found[f"class {node.name}"] = source
        elif isinstance(node, ast.FunctionDef):
            found[f"def {node.name}"] = source
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[f"constant {target.id}"] = source
    return found


def main(ingol):
    theirs, ours = pieces(Path(ingol) / FILE), pieces(REPOSITORY / "tests" / FILE)
    wanted = [f"class {name}" for name in CLASSES] + [f"def {name}" for name in FUNCTIONS] \
        + [f"constant {name}" for name in CONSTANTS]
    differ = 0
    for piece in wanted:
        same = piece in theirs and ours.get(piece) == theirs[piece]
        differ += not same
        print(f"{FILE} {piece}: {'same as INGOL' if same else 'DIFFERS'}")
    print("the copied class and what it uses are INGOL's" if not differ else f"{differ} piece(s) differ")
    return 0 if not differ else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
