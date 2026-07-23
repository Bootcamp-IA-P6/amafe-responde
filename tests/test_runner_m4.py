# -*- coding: utf-8 -*-
"""Pruebas de eval/runner_bateria.py (M4) — sin red, sin Groq.

El runner se ejecuta en subproceso a través de un wrapper que inyecta un
mock de `generacion` en sys.modules ANTES de lanzar el script (así el mock
gana siempre, aunque el runner anteponga src/ al path). El dataset usado es
el congelado eval/preguntas.jsonl; la salida va a un directorio temporal.

Ejecución, desde la raíz del repo:
    uv run python tests/test_runner_m4.py

Casos (3):
 1. tanda completa: 20 líneas LF, dataset fusionado con el contrato,
    no-sé simulado para fuera_corpus, orden preservado, stdout=ruta.
 2. --limite 2: exactamente 2 líneas (q01, q02).
 3. error a mitad de tanda: registro con "error", la tanda sigue, exit 1.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MOCK_GENERACION = '''
def generar_respuesta(pregunta, temperature=None, max_tokens=None, idioma=None):
    modo = "__MODO__"
    if modo == "error" and "socio" in pregunta.lower():
        raise ConnectionError("backend caido (simulado)")
    fuera = any(t in pregunta for t in ("Prado", "medicaci", "Liga"))
    chunks = [{"chunk_id": f"mock__{n:03d}", "similitud": 0.6 - n*0.01,
               "distancia": 0.4 + n*0.01, "texto": f"Texto {n}.",
               "url": "https://www.amafe.org/mock", "titulo": f"Mock {n}",
               "slug": "mock", "idioma": "es", "tipo_fuente": "web"}
              for n in range(1, 6)]
    return {"timestamp": "2026-07-22T12:00:00+02:00", "pregunta": pregunta,
            "modelo": "llama-3.1-8b-instant", "temperature": 0.2,
            "max_tokens": 800, "seed": None, "umbral_distancia": 0.75,
            "chunks": chunks,
            "fuentes": [{"n": n, "chunk_id": c["chunk_id"], "titulo": c["titulo"],
                         "url": c["url"], "tipo_fuente": c["tipo_fuente"],
                         "similitud": c["similitud"], "distancia": c["distancia"]}
                        for n, c in enumerate(chunks, 1)],
            "mejor_distancia": 0.82 if fuera else 0.39,
            "respuesta": ("No he encontrado informacion suficiente..." if fuera
                          else "Respuesta simulada [1]."),
            "llm_llamado": not fuera}
'''

WRAPPER = '''
import runpy, sys, types
mock = types.ModuleType("generacion")
exec(open(r"{mock_path}", encoding="utf-8").read(), mock.__dict__)
sys.modules["generacion"] = mock
sys.argv = ["runner_bateria.py"] + {argv!r}
runpy.run_path(r"{runner_path}", run_name="__main__")
'''


def ejecutar_runner(modo: str, extra_args: list[str]):
    tmp = Path(tempfile.mkdtemp(prefix="m4_runner_"))
    mock_path = tmp / "mock_generacion.py"
    mock_path.write_text(MOCK_GENERACION.replace("__MODO__", modo),
                         encoding="utf-8")
    salida = tmp / "bateria_test.jsonl"
    argv = ["--preguntas", str(REPO / "eval" / "preguntas.jsonl"),
            "--salida", str(salida), "--pausa", "0", *extra_args]
    wrapper = tmp / "wrapper.py"
    wrapper.write_text(WRAPPER.format(mock_path=mock_path, argv=argv,
                                      runner_path=REPO / "eval" / "runner_bateria.py"),
                       encoding="utf-8")
    proc = subprocess.run([sys.executable, str(wrapper)],
                          capture_output=True, text=True,
                          env=os.environ.copy(), cwd=str(REPO))
    return proc, salida


def caso_1_tanda_completa():
    proc, salida = ejecutar_runner("ok", [])
    assert proc.returncode == 0, f"exit != 0: {proc.stderr[-300:]}"
    raw = salida.read_bytes()
    assert raw.count(b"\n") == 20 and b"\r\n" not in raw, \
        "deben ser 20 líneas LF puras"
    lineas = [json.loads(l) for l in raw.decode("utf-8").splitlines()]
    assert [l["id"] for l in lineas] == [f"q{n:02d}" for n in range(1, 21)], \
        "orden alterado"
    for l in lineas:
        for clave in ("id", "categoria", "esperado", "pregunta", "respuesta",
                      "chunks", "fuentes", "llm_llamado", "mejor_distancia"):
            assert clave in l, f"{l['id']}: falta '{clave}'"
    fuera = [l for l in lineas if l["categoria"] == "fuera_corpus"]
    assert len(fuera) == 3 and all(not l["llm_llamado"] for l in fuera), \
        "las 3 fuera_corpus deben simular no-sé (llm_llamado=false)"
    assert proc.stdout.strip().endswith("bateria_test.jsonl"), \
        "stdout debe ser la ruta del fichero de datos"
    return "OK"


def caso_2_limite():
    proc, salida = ejecutar_runner("ok", ["--limite", "2"])
    assert proc.returncode == 0, f"exit != 0: {proc.stderr[-300:]}"
    lineas = salida.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2 and json.loads(lineas[1])["id"] == "q02", \
        "--limite 2 debe dar exactamente q01+q02"
    return "OK"


def caso_3_error_no_detiene():
    proc, salida = ejecutar_runner("error", [])
    assert proc.returncode == 1, "con errores el exit code debe ser 1"
    lineas = [json.loads(l) for l in salida.read_text(encoding="utf-8").splitlines()]
    assert len(lineas) == 20, "un error no debe detener la tanda"
    con_error = [l for l in lineas if "error" in l]
    assert con_error and all("id" in l and "pregunta" in l for l in con_error), \
        "los registros de error conservan id y pregunta"
    return "OK"


def main() -> int:
    casos = [caso_1_tanda_completa, caso_2_limite, caso_3_error_no_detiene]
    fallos = 0
    for c in casos:
        try:
            print(f"{c.__name__}: {c()}")
        except AssertionError as e:
            fallos += 1
            print(f"{c.__name__}: FALLO — {e}", file=sys.stderr)
        except Exception as e:
            fallos += 1
            print(f"{c.__name__}: ERROR — {type(e).__name__}: {e}", file=sys.stderr)
    print(f"\nResultado: {len(casos) - fallos}/{len(casos)} verdes")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
