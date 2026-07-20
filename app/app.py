"""app.py — Interfaz web mínima de AMAFE Responde (M2, issue #2).

Consume generar_respuesta() de src/generacion.py (decisión 2a: el dict de
retorno es el contrato de datos) y registra cada consulta en
logs/consultas_app.jsonl (decisión D3a).

Ejecución, desde la raíz del repo:
    uv run streamlit run app/app.py
"""

import json
import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from generacion import generar_respuesta  # noqa: E402

LOG_PATH = RAIZ / "logs" / "consultas_app.jsonl"

PREGUNTAS_SUGERIDAS = [
    "¿Cómo puedo pedir cita?",
    "¿Qué es el Espacio Joven?",
    "¿Cómo puedo asociarme?",
    "¿Qué servicios ofrece AMAFE?",
]


def registrar(resultado: dict) -> None:
    """Añade el dict de trazabilidad como una línea JSONL (LF, UTF-8)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")


def ejecutar(pregunta: str) -> None:
    pregunta = pregunta.strip()
    if not pregunta:
        st.session_state.error = "Escribe una pregunta antes de enviar."
        return
    st.session_state.error = None
    with st.spinner(
        "Generando respuesta con el modelo local (CPU): puede tardar varios minutos…"
    ):
        try:
            resultado = generar_respuesta(pregunta)
        except Exception as exc:  # p. ej. Ollama no arrancado
            st.session_state.error = (
                f"No se pudo generar la respuesta: {exc}. "
                "¿Está Ollama en marcha? (ollama serve)"
            )
            return
    st.session_state.resultado = resultado
    registrar(resultado)


def pintar_chunks(chunks: list[dict]) -> None:
    for c in chunks:
        st.markdown(
            f"**`{c['chunk_id']}`** · similitud {c['similitud']:.4f} · "
            f"distancia {c['distancia']:.4f} · [{c['titulo']}]({c['url']})"
        )
        st.text(c["texto"])
        st.markdown("---")


# ----------------------------------------------------------------- interfaz
st.set_page_config(page_title="AMAFE Responde", page_icon="💬", layout="centered")

st.title("💬 AMAFE Responde")
st.caption(
    "Asistente RAG sobre la documentación pública de [AMAFE](https://www.amafe.org). "
    "Proyecto formativo (Bootcamp IA · Factoría F5): **no es una herramienta oficial "
    "de AMAFE**. Las respuestas se generan solo a partir del corpus público y "
    "citan sus fuentes; contrasta siempre con los enlaces."
)

st.session_state.setdefault("resultado", None)
st.session_state.setdefault("error", None)

st.markdown("**Preguntas sugeridas:**")
cols = st.columns(2)
for i, p in enumerate(PREGUNTAS_SUGERIDAS):
    if cols[i % 2].button(p, use_container_width=True):
        st.session_state.pregunta = p
        ejecutar(p)

pregunta_texto = st.text_input(
    "Escribe tu pregunta sobre AMAFE", key="pregunta",
    placeholder="Por ejemplo: ¿Dónde puedo encontrar las memorias anuales?",
)
if st.button("Preguntar", type="primary"):
    ejecutar(pregunta_texto)

if st.session_state.error:
    st.error(st.session_state.error)

r = st.session_state.resultado
if r:
    st.divider()
    st.markdown(f"**Pregunta:** {r['pregunta']}")

    if r.get("llm_llamado"):
        st.markdown("### Respuesta")
        st.markdown(r["respuesta"])
        st.markdown("### Fuentes consultadas")
        for f in r["fuentes"]:
            st.markdown(
                f"**[{f['n']}]** [{f['titulo']}]({f['url']}) — "
                f"similitud {f['similitud']:.4f}"
            )
        with st.expander("Ver fragmentos y puntuaciones"):
            pintar_chunks(r["chunks"])
    else:
        st.warning(r["respuesta"])
        st.caption(
            f"Ningún fragmento superó el umbral de confianza "
            f"(mejor distancia {r['mejor_distancia']:.4f} > umbral "
            f"{r['umbral_distancia']}). No se ha llamado al modelo y por tanto "
            f"no se citan fuentes."
        )
        with st.expander("Ver los fragmentos más cercanos (descartados por el umbral)"):
            pintar_chunks(r["chunks"])

    st.caption(
        f"Trazabilidad: modelo `{r['modelo']}` · temperature {r['temperature']} · "
        f"umbral {r['umbral_distancia']} · {r['timestamp']} · "
        f"consulta registrada en `logs/consultas_app.jsonl`"
    )
