# -*- coding: utf-8 -*-
"""Pruebas AppTest de app/app.py — M2b: historial y persistencia.

Ejecución, desde la raíz del repo:
    uv run python tests/test_app_m2b.py

No requiere Ollama/Groq ni ChromaDB: src/generacion.py se sustituye por un
mock inyectado en sys.modules que replica el contrato real (verificado sobre
logs/consultas_app.jsonl). La app se copia a un árbol temporal para que
LOG_PATH apunte a un logs/ aislado: el JSONL real del repo NUNCA se toca.

Casos (6):
 1. respuesta_ok        — turno completo, fuentes, expander D1a, 1 línea LF.
 2. no_se               — aviso, descartados, sin fuentes.
 3. sugeridas_solo_vacio — HA2b: visibles solo con historial vacío.
 4. cargar_historial    — HB1b: repobla, ignora corruptas, no reescribe,
                          botón deshabilitado tras cargar.
 5. limpiar             — HB2a: vacía lo visual, JSONL intacto, rehabilita.
 6. error_backend       — excepción → st.error, nada registrado.
"""

import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parents[1]
TESTROOT = Path(tempfile.mkdtemp(prefix="amafe_m2b_"))

# ---------- mock de generacion (contrato real de generar_respuesta) ----------
def _chunk(n):
    return {
        "chunk_id": f"mock__{n:03d}", "similitud": 0.62 - n * 0.01,
        "distancia": 0.38 + n * 0.01, "texto": f"Texto del fragmento {n}.",
        "url": "https://www.amafe.org/mock", "titulo": f"Página mock {n}",
        "slug": "mock", "idioma": "es", "tipo_fuente": "web",
    }

def _resultado(pregunta, llm=True, modelo="llama-3.1-8b-instant",
               ts="2026-07-21T15:00:00+02:00"):
    chunks = [_chunk(n) for n in range(1, 6)]
    return {
        "timestamp": ts, "pregunta": pregunta, "modelo": modelo,
        "temperature": 0.2, "max_tokens": 800, "seed": None,
        "umbral_distancia": 0.75, "chunks": chunks,
        "fuentes": [{"n": n, "chunk_id": c["chunk_id"], "titulo": c["titulo"],
                     "url": c["url"], "tipo_fuente": c["tipo_fuente"],
                     "similitud": c["similitud"], "distancia": c["distancia"]}
                    for n, c in enumerate(chunks, 1)],
        "mejor_distancia": 0.39 if llm else 0.82,
        "respuesta": ("Respuesta simulada con cita [1]." if llm else
                      "No he encontrado información suficiente en la "
                      "documentación disponible para responder con seguridad."),
        "llm_llamado": llm,
    }

ESTADO = {"modo": "ok"}  # ok | nose | error

def _generar(pregunta, temperature=None, max_tokens=None, idioma=None):
    if ESTADO["modo"] == "error":
        raise ConnectionError("backend caído (simulado)")
    return _resultado(pregunta, llm=(ESTADO["modo"] == "ok"))

mock = types.ModuleType("generacion")
mock.generar_respuesta = _generar
mock.LLM_BASE_URL = "https://api.groq.com/openai/v1"
mock.LLM_MODEL = "llama-3.1-8b-instant"
sys.modules["generacion"] = mock

# ---------- entorno aislado por caso ----------
def preparar(jsonl_lineas=None):
    if TESTROOT.exists():
        shutil.rmtree(TESTROOT)
    (TESTROOT / "app").mkdir(parents=True)
    (TESTROOT / "logs").mkdir()
    shutil.copy(REPO / "app" / "app.py", TESTROOT / "app" / "app.py")
    if jsonl_lineas is not None:
        with open(TESTROOT / "logs" / "consultas_app.jsonl", "w",
                  encoding="utf-8", newline="\n") as f:
            for linea in jsonl_lineas:
                f.write(linea + "\n")
    return AppTest.from_file(str(TESTROOT / "app" / "app.py"),
                             default_timeout=30)

def log_bytes():
    p = TESTROOT / "logs" / "consultas_app.jsonl"
    return p.read_bytes() if p.exists() else b""

def boton(at, texto):
    return next(b for b in at.button if texto in b.label)

def texto_markdown(at):
    return " | ".join(m.value for m in at.markdown)

# ---------- casos ----------
def caso_1_respuesta_ok():
    ESTADO["modo"] = "ok"
    at = preparar().run()
    at.chat_input[0].set_value("¿Qué es el Espacio Joven?").run()
    md = texto_markdown(at)
    assert "¿Qué es el Espacio Joven?" in md, "falta el turno del usuario"
    assert "Respuesta simulada con cita [1]." in md, "falta la respuesta"
    assert "Fuentes consultadas" in md, "faltan las fuentes"
    assert any("Ver fragmentos" in e.label for e in at.expander), \
        "falta el expander D1a"
    raw = log_bytes()
    assert raw.count(b"\n") == 1 and b"\r\n" not in raw, \
        "el JSONL debe tener exactamente 1 línea LF pura"
    assert json.loads(raw)["pregunta"] == "¿Qué es el Espacio Joven?"
    return "OK"

def caso_2_no_se():
    ESTADO["modo"] = "nose"
    at = preparar().run()
    at.chat_input[0].set_value("¿Cuál es el precio del oro?").run()
    assert any("No he encontrado información suficiente" in w.value
               for w in at.warning), "falta el aviso no-sé"
    assert any("descartados por el umbral" in e.label for e in at.expander), \
        "falta el expander de descartados"
    assert "Fuentes consultadas" not in texto_markdown(at), \
        "el caso no-sé no debe listar fuentes"
    return "OK"

def caso_3_sugeridas_solo_vacio():
    ESTADO["modo"] = "ok"
    at = preparar().run()
    labels = [b.label for b in at.button]
    assert any("¿Cómo puedo pedir cita?" in l for l in labels), \
        "sugeridas ausentes con historial vacío"
    boton(at, "¿Cómo puedo pedir cita?").click().run()
    labels2 = [b.label for b in at.button]
    assert not any("¿Qué es el Espacio Joven?" in l for l in labels2), \
        "las sugeridas deben ocultarse tras el primer turno (HA2b)"
    assert "Respuesta simulada" in texto_markdown(at), \
        "la sugerida no ejecutó la consulta"
    assert log_bytes().count(b"\n") == 1, \
        "la sugerida debe registrar exactamente 1 línea"
    return "OK"

def caso_4_cargar_historial():
    ESTADO["modo"] = "ok"
    previas = [
        json.dumps(_resultado("¿Cómo puedo pedir cita?", modelo="qwen3:8b",
                              ts="2026-07-20T10:33:17+02:00"),
                   ensure_ascii=False),
        json.dumps(_resultado("¿Cómo puedo asociarme?",
                              ts="2026-07-20T13:38:43+02:00"),
                   ensure_ascii=False),
        "{esto no es json",  # línea corrupta: se descarta sin romper
    ]
    at = preparar(previas).run()
    bytes_antes = log_bytes()
    boton(at, "Cargar historial anterior").click().run()
    md = texto_markdown(at)
    assert "¿Cómo puedo pedir cita?" in md and "¿Cómo puedo asociarme?" in md, \
        "no repobló los turnos del JSONL"
    assert any("descartado" in (e.value or "") for e in at.error), \
        "debe avisar de la línea corrupta"
    assert log_bytes() == bytes_antes, "cargar NO debe reescribir el JSONL"
    assert boton(at, "Cargar historial anterior").disabled, \
        "el botón debe quedar deshabilitado tras cargar"
    return "OK"

def caso_5_limpiar():
    ESTADO["modo"] = "ok"
    previas = [json.dumps(_resultado("¿Qué servicios ofrece AMAFE?"),
                          ensure_ascii=False)]
    at = preparar(previas).run()
    boton(at, "Cargar historial anterior").click().run()
    assert "¿Qué servicios ofrece AMAFE?" in texto_markdown(at)
    bytes_antes = log_bytes()
    boton(at, "Limpiar conversación").click().run()
    assert "¿Qué servicios ofrece AMAFE?" not in texto_markdown(at), \
        "limpiar no vació el historial visual"
    assert log_bytes() == bytes_antes, "limpiar NO debe tocar el JSONL"
    assert not boton(at, "Cargar historial anterior").disabled, \
        "tras limpiar debe poder recargarse"
    assert any("¿Cómo puedo pedir cita?" in b.label for b in at.button), \
        "tras limpiar deben reaparecer las sugeridas"
    return "OK"

def caso_6_error_backend():
    ESTADO["modo"] = "error"
    at = preparar().run()
    at.chat_input[0].set_value("¿Qué es AMAFE?").run()
    assert any("No se pudo generar la respuesta" in (e.value or "")
               for e in at.error), "falta el mensaje de error"
    assert log_bytes() == b"", "un error no debe registrar nada en el JSONL"
    return "OK"

def main() -> int:
    casos = [caso_1_respuesta_ok, caso_2_no_se, caso_3_sugeridas_solo_vacio,
             caso_4_cargar_historial, caso_5_limpiar, caso_6_error_backend]
    fallos = 0
    for c in casos:
        try:
            print(f"{c.__name__}: {c()}")
        except AssertionError as e:
            fallos += 1
            print(f"{c.__name__}: FALLO — {e}", file=sys.stderr)
        except Exception as e:
            fallos += 1
            print(f"{c.__name__}: ERROR — {type(e).__name__}: {e}",
                  file=sys.stderr)
    shutil.rmtree(TESTROOT, ignore_errors=True)
    print(f"\nResultado: {len(casos) - fallos}/{len(casos)} verdes")
    return 1 if fallos else 0

if __name__ == "__main__":
    sys.exit(main())
