"""WI20-AC01: each class of INGOL's pilot tests that WI20 copied into tests/
is INGOL's class, the client's name apart.

    python docs/evidence/01M46KHBYCXMGM0K6N2RM651PE/compare_pilot_tests.py <INGOL's pruebas folder> <client name in INGOL's tests>

The folder is docs/work-items/dev-capabilities/evidence/d1/ac05-base-revisada/
pruebas/ of INGOL's repository. The client's name is not written here because
this repository is public: whoever runs the script types it. Exit 0 when every
class matches.
"""

import ast
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
# The only change: the project of the tests is not named after a client.
def names(client):
    return {f'"{client} Sprint 3", "{client}"': '"Planta Demo Sprint 3", "Cliente Demo"'}



COPIED = {
    "test_d1_hallazgos_arquitecto.py": ["Carpeta", "AR01TrabajoColgado", "AR02EscrituraNoAtomica",
                                        "AR03LoPagadoSeTira", "AR05AltasSimultaneas", "AR10AjustesSimultaneos"],
    "test_d1_barrido.py": ["ConocimientoAMedioEscribir", "ProyectosConElMismoNombre", "LecturaEnTandas"],
}


def classes(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    return {node.name: "".join(lines[node.lineno - 1:node.end_lineno])
            for node in ast.parse(text).body if isinstance(node, ast.ClassDef)}


def main(ingol, client):
    ingol = Path(ingol)
    NAMES = names(client)
    differ = 0
    for name, wanted in COPIED.items():
        theirs, ours = classes(ingol / name), classes(REPOSITORY / "tests" / name)
        for cls in wanted:
            expected = theirs[cls]
            for old, new in NAMES.items():
                expected = expected.replace(old, new)
            same = ours.get(cls) == expected
            differ += not same
            print(f"{name} {cls}: {'same as INGOL' if same else 'DIFFERS'}")
        extra = sorted(set(ours) - set(wanted))
        if extra:
            differ += len(extra)
            print(f"{name}: classes that are not INGOL's: {extra}")
    print("every copied class is INGOL's" if not differ else f"{differ} class(es) differ")
    return 0 if not differ else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
