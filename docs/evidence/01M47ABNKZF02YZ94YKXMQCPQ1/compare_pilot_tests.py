"""WI22-AC01: the class of INGOL's pilot tests that WI22 copied into tests/ is
INGOL's class, and so are the two constants above it (W and CAMPO), unchanged.

    python docs/evidence/01M47ABNKZF02YZ94YKXMQCPQ1/compare_pilot_tests.py <INGOL's pruebas folder>

The folder is docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/
pruebas/ of INGOL's repository. Exit 0 when the class and the constants match.
Unlike WI20's script, no name has to be replaced: the class names no client.
What the script does not compare is the file's header and its imports (the
copy does not import INGOL's kits, which the class does not use), and the class
that follows it, which is this project's negative control and says so; the
script lists such classes. A class that is not there, or a constant, makes it
exit 1.
"""

import ast
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
COPIED = {
    "test_d1_hallazgos_arquitecto.py": ("test_d1_r02_plantilla.py", ["AR04FiltroDeCamposEludible"], ["W", "CAMPO"]),
}


def pieces(path):
    """({class name: its source}, {constant name: its source}) of a module's top level."""
    text = path.read_text(encoding="utf-8")
    classes, constants = {}, {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.ClassDef):
            classes[node.name] = ast.get_source_segment(text, node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            constants[node.targets[0].id] = ast.get_source_segment(text, node)
    return classes, constants


def main(ingol):
    ingol = Path(ingol)
    differ = 0
    for name, (copy, wanted_classes, wanted_constants) in COPIED.items():
        their_classes, their_constants = pieces(ingol / name)
        our_classes, our_constants = pieces(REPOSITORY / "tests" / copy)
        for kind, theirs, ours, wanted in (("class", their_classes, our_classes, wanted_classes),
                                           ("constant", their_constants, our_constants, wanted_constants)):
            for item in wanted:
                same = item in theirs and ours.get(item) == theirs[item]
                differ += not same
                print(f"{copy} {kind} {item}: {'same as INGOL' if same else 'DIFFERS'}")
        extra = sorted(set(our_classes) - set(wanted_classes))
        if extra:
            print(f"{copy}: classes that are not INGOL's (this project's): {extra}")
    print("the copied class and constants are INGOL's" if not differ else f"{differ} item(s) differ")
    return 0 if not differ else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
