# -*- coding: utf-8 -*-
"""
generacion.py - v3.1 (20260713)
AMAFE Responde - Fase de generación del pipeline RAG.

Conecta busqueda.py con un LLM vía API OpenAI-compatible (Ollama fase 1,
Groq fase 2, sin cambiar código: solo .env).

Ubicación: src/generacion.py (junto a busqueda.py).
Ejecutar SIEMPRE desde la raíz del proyecto (chroma_db/ es ruta relativa).

Decisiones aplicadas (docs/decisiones.md):
- 1a: soft switch /no_think + limpieza regex de <think>...</think>
- 2a: módulo reutilizable, generar_respuesta(pregunta) -> dict
- 3c: doble guardarraíl (umbral de distancia + prompt)
- 4:  temperature y max_tokens en .env, con override --temperature en CLI
      para el experimento comparativo 0.0 vs 0.2

Cambios v3.1 (20260713):
- Adaptado a la interfaz real de busqueda.py v2:
  buscar(pregunta, top_k, idioma) -> list[dict] con chunk_id, similitud
  (= 1 - distancia coseno), texto y metadatos aplanados.
- Eliminado el normalizador especulativo de v3 (ya no hay incertidumbre).
- distancia se deriva como 1 - similitud para mantener UMBRAL_DISTANCIA
  coherente con ChromaDB y docs/decisiones.md.

Uso CLI (desde la raíz del proyecto):
    uv run python src/generacion.py "¿Cómo puedo pedir cita?"
    uv run python src/generacion.py "¿Qué es el Espacio Joven?" --temperature 0.0
    uv run python src/generacion.py "..." --json    # dict completo en una línea (JSONL)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from busqueda import buscar

load_dotenv()

# --- Configuración (.env con valores por defecto) ---------------------------
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")  # Ollama ignora el valor
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "800"))
LLM_SEED = os.getenv("LLM_SEED")  # opcional; si existe, refuerza reproducibilidad
UMBRAL_DISTANCIA = float(os.getenv("UMBRAL_DISTANCIA", "0.65"))
TOP_K = int(os.getenv("TOP_K", "5"))

MENSAJE_NO_SE = (
    "No he encontrado información suficiente en la documentación "
    "disponible para responder con seguridad."
)

SYSTEM_PROMPT = """Eres "AMAFE Responde", un asistente que contesta preguntas \
sobre la asociación AMAFE usando EXCLUSIVAMENTE los fragmentos de su \
documentación pública que se te proporcionan.

Reglas obligatorias:
1. Responde SOLO con información presente en los fragmentos. No uses \
conocimiento externo.
2. Cita las fuentes con el formato [n] tras cada afirmación, donde n es el \
número del fragmento usado.
3. Si los fragmentos no contienen la respuesta, di exactamente: \
"{mensaje_no_se}"
4. Nunca inventes teléfonos, emails, direcciones, servicios ni datos \
económicos.
5. La documentación puede no estar actualizada: si das fechas, plazos o \
datos económicos, añade al final "(según la documentación disponible, \
podría estar desactualizada)".
6. Responde en el idioma de la pregunta, de forma clara y concisa.
/no_think"""


# --- Utilidades --------------------------------------------------------------
def _limpiar_thinking(texto: str) -> str:
    """Red de seguridad 1a: elimina bloques <think>...</think> si aparecen."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    return texto.strip()


def _con_distancia(chunks: list[dict]) -> list[dict]:
    """Añade 'distancia' (= 1 - similitud) a cada chunk de busqueda.buscar()."""
    for ch in chunks:
        ch["distancia"] = round(1 - ch["similitud"], 4)
    return chunks


def _formatear_contexto(chunks: list[dict]) -> str:
    """Construye el bloque de fragmentos numerados para el prompt."""
    partes = []
    for n, ch in enumerate(chunks, start=1):
        fuente = ch.get("titulo") or ch.get("slug") or ch["chunk_id"]
        partes.append(f"[{n}] (fuente: {fuente})\n{ch['texto']}")
    return "\n\n".join(partes)


def _extraer_fuentes(chunks: list[dict]) -> list[dict]:
    """Lista de fuentes para mostrar bajo la respuesta (trazabilidad)."""
    return [{
        "n": n,
        "chunk_id": ch["chunk_id"],
        "titulo": ch.get("titulo"),
        "url": ch.get("url"),
        "tipo_fuente": ch.get("tipo_fuente"),
        "similitud": ch["similitud"],
        "distancia": ch["distancia"],
    } for n, ch in enumerate(chunks, start=1)]


# --- Función principal (decisión 2a) -----------------------------------------
def generar_respuesta(
    pregunta: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    idioma: str | None = None,
) -> dict:
    """Ejecuta el ciclo RAG completo para una pregunta.

    Devuelve un dict con todos los campos de trazabilidad:
    pregunta, respuesta, fuentes, chunks, parámetros, umbral, timestamp.
    idioma: 'es', 'en', 'all' o None (autodetección de busqueda.py).
    """
    temperature = LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = LLM_MAX_TOKENS if max_tokens is None else max_tokens
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    # 1. Recuperación (busqueda.py v2: autodetecta idioma si es None)
    chunks = _con_distancia(buscar(pregunta, top_k=TOP_K, idioma=idioma))

    resultado = {
        "timestamp": timestamp,
        "pregunta": pregunta,
        "modelo": LLM_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": int(LLM_SEED) if LLM_SEED else None,
        "umbral_distancia": UMBRAL_DISTANCIA,
        "chunks": chunks,
        "fuentes": _extraer_fuentes(chunks),
    }

    # 2. Guardarraíl 1 (decisión 3c): umbral de distancia previo al LLM
    mejor = min((c["distancia"] for c in chunks), default=None)
    resultado["mejor_distancia"] = mejor
    if mejor is None or mejor > UMBRAL_DISTANCIA:
        resultado["respuesta"] = MENSAJE_NO_SE
        resultado["llm_llamado"] = False
        return resultado

    # 3. Generación (guardarraíl 2: prompt)
    cliente = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    extra = {}
    if LLM_SEED:
        extra["seed"] = int(LLM_SEED)
    respuesta_llm = cliente.chat.completions.create(
        model=LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system",
             "content": SYSTEM_PROMPT.format(mensaje_no_se=MENSAJE_NO_SE)},
            {"role": "user",
             "content": (f"Fragmentos de la documentación de AMAFE:\n\n"
                         f"{_formatear_contexto(chunks)}\n\n"
                         f"Pregunta: {pregunta}")},
        ],
        **extra,
    )

    resultado["respuesta"] = _limpiar_thinking(
        respuesta_llm.choices[0].message.content or ""
    )
    resultado["llm_llamado"] = True
    return resultado


# --- CLI ----------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="AMAFE Responde - generación RAG")
    parser.add_argument("pregunta", help="Pregunta en lenguaje natural")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Override de LLM_TEMPERATURE (para experimentos)")
    parser.add_argument("--idioma", choices=["es", "en", "all"], default=None,
                        help="Forzar idioma (por defecto: autodetectar)")
    parser.add_argument("--json", action="store_true",
                        help="Volcar el dict completo como JSON en una línea (JSONL)")
    args = parser.parse_args()

    r = generar_respuesta(args.pregunta,
                          temperature=args.temperature,
                          idioma=args.idioma)

    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0

    print("\n=== AMAFE Responde ===")
    print(f"Pregunta   : {r['pregunta']}")
    print(f"Modelo     : {r['modelo']}  T={r['temperature']}  "
          f"max_tokens={r['max_tokens']}  seed={r['seed']}")
    print(f"Mejor dist.: {r['mejor_distancia']}  (umbral {r['umbral_distancia']})")
    print(f"LLM llamado: {r['llm_llamado']}")
    print(f"\n--- Respuesta ---\n{r['respuesta']}")
    print("\n--- Fuentes ---")
    for f in r["fuentes"]:
        print(f"  [{f['n']}] {f['chunk_id']}  sim={f['similitud']:.4f}  "
              f"d={f['distancia']:.4f}  {f['titulo'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
