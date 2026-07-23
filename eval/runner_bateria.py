# -*- coding: utf-8 -*-
"""runner_bateria.py — M4: ejecuta la batería de evaluación sobre el RAG.

Lee eval/preguntas.jsonl (dataset congelado, decisión Q1c), llama a
generar_respuesta() por cada pregunta con una pausa entre llamadas (free
tier de Groq), y escribe cada dict de trazabilidad —enriquecido con los
campos del dataset (id, categoria, esperado, nota)— como una línea JSONL.

Ejecución, desde la raíz del repo:
    uv run python eval/runner_bateria.py                       # tanda completa
    uv run python eval/runner_bateria.py --limite 2 --pausa 1  # smoke test
    uv run python eval/runner_bateria.py --salida eval/bateria.$(sella).jsonl

Convenciones (R1): stdout = ruta del fichero de datos generado;
stderr = progreso y diagnóstico. Salida JSONL con LF puro.
Un fallo en una pregunta se registra (campo "error") y NO detiene la tanda.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from generacion import generar_respuesta  # noqa: E402


def cargar_preguntas(ruta: Path) -> list[dict]:
    preguntas = []
    with open(ruta, encoding="utf-8") as f:
        for n, linea in enumerate(f, start=1):
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)  # dataset congelado: si está corrupto, mejor parar
            for clave in ("id", "pregunta", "categoria", "esperado"):
                if clave not in d:
                    raise ValueError(f"Línea {n}: falta la clave '{clave}'")
            preguntas.append(d)
    return preguntas


def main() -> int:
    parser = argparse.ArgumentParser(description="M4 - runner de la batería de evaluación")
    parser.add_argument("--preguntas", default=str(RAIZ / "eval" / "preguntas.jsonl"),
                        help="Dataset de preguntas (JSONL)")
    parser.add_argument("--salida", default=None,
                        help="Fichero JSONL de salida (por defecto: eval/bateria_<ts>.jsonl)")
    parser.add_argument("--pausa", type=float, default=3.0,
                        help="Segundos entre llamadas (free tier Groq; 0 para tests)")
    parser.add_argument("--limite", type=int, default=None,
                        help="Ejecutar solo las N primeras (smoke test)")
    args = parser.parse_args()

    preguntas = cargar_preguntas(Path(args.preguntas))
    if args.limite:
        preguntas = preguntas[: args.limite]

    if args.salida:
        salida = Path(args.salida)
    else:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        salida = RAIZ / "eval" / f"bateria_{ts}.jsonl"
    salida.parent.mkdir(parents=True, exist_ok=True)

    print(f"== Batería M4: {len(preguntas)} preguntas -> {salida} ==", file=sys.stderr)
    errores = 0
    t0 = time.monotonic()
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        for n, p in enumerate(preguntas, start=1):
            print(f"[{n:02d}/{len(preguntas)}] {p['id']} · {p['pregunta'][:60]}",
                  file=sys.stderr)
            registro = {"id": p["id"], "categoria": p["categoria"],
                        "esperado": p["esperado"], "nota": p.get("nota")}
            try:
                registro.update(generar_respuesta(p["pregunta"]))
            except Exception as exc:  # se registra y se sigue con la tanda
                errores += 1
                registro.update({"pregunta": p["pregunta"], "error": str(exc)})
                print(f"    ERROR: {exc}", file=sys.stderr)
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            if args.pausa and n < len(preguntas):
                time.sleep(args.pausa)

    duracion = time.monotonic() - t0
    print(f"== Fin: {len(preguntas) - errores} OK, {errores} errores, "
          f"{duracion:.1f} s ==", file=sys.stderr)
    print(salida)  # stdout = datos: la ruta del JSONL generado
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
