"""app.py — Interfaz web de AMAFE Responde (M2b: historial y persistencia).

Patrón de chat de Streamlit (st.chat_message + st.chat_input + session_state),
adaptado del tutorial oficial al contrato propio del proyecto:
https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps

Decisiones aplicadas (docs/decisiones.md):
- HA1a: cada turno guarda el dict COMPLETO de generar_respuesta(); el
  bocadillo del asistente conserva fuentes, expander (D1a) y aviso no-sé.
- HA2b: preguntas sugeridas visibles solo con el historial vacío.
- HB1b: botón "Cargar historial anterior" que relee logs/consultas_app.jsonl
  (D3a); sin recarga automática.
- HB2a: botón "Limpiar conversación" que vacía solo el historial visual;
  el JSONL de trazabilidad nunca se toca.
- HC0: sin memoria conversacional del LLM (generar_respuesta() intacta).
- S1: texto del spinner dinámico según el backend (local vs nube).

Ejecución, desde la raíz del repo:
    uv run streamlit run app/app.py
"""

import json
import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from generacion import LLM_BASE_URL, LLM_MODEL, generar_respuesta  # noqa: E402

LOG_PATH = RAIZ / "logs" / "consultas_app.jsonl"

PREGUNTAS_SUGERIDAS = [
    "¿Cómo puedo pedir cita?",
    "¿Qué es el Espacio Joven?",
    "¿Cómo puedo asociarme?",
    "¿Qué servicios ofrece AMAFE?",
]

ES_LOCAL = "localhost" in LLM_BASE_URL or "127.0.0.1" in LLM_BASE_URL
TEXTO_SPINNER = (
    "Generando respuesta con el modelo local (CPU): puede tardar varios minutos…"
    if ES_LOCAL
    else f"Generando respuesta con `{LLM_MODEL}` en la nube…"
)


def registrar(resultado: dict) -> None:
    """Añade el dict de trazabilidad como una línea JSONL (LF, UTF-8). D3a."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")


def cargar_historial() -> tuple[list[dict], int]:
    """Lee el JSONL completo. Devuelve (turnos válidos, líneas descartadas).

    Un turno es válido si tiene al menos 'pregunta' y 'respuesta' (contrato
    de generar_respuesta()); las líneas corruptas se cuentan, no rompen.
    """
    if not LOG_PATH.exists():
        return [], 0
    validos: list[dict] = []
    descartadas = 0
    with open(LOG_PATH, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                descartadas += 1
                continue
            if "pregunta" in d and "respuesta" in d:
                validos.append(d)
            else:
                descartadas += 1
    return validos, descartadas


def ejecutar(pregunta: str) -> None:
    """Ciclo completo de una consulta nueva: RAG + historial + registro."""
    pregunta = pregunta.strip()
    if not pregunta:
        st.session_state.error = "Escribe una pregunta antes de enviar."
        return
    st.session_state.error = None
    with st.spinner(TEXTO_SPINNER):
        try:
            resultado = generar_respuesta(pregunta)
        except Exception as exc:  # p. ej. backend LLM no disponible
            st.session_state.error = (
                f"No se pudo generar la respuesta: {exc}. "
                "¿Está el backend LLM disponible? (Ollama: ollama serve; "
                "Groq: revisa LLM_API_KEY y la conexión)"
            )
            return
    st.session_state.historial.append(resultado)
    registrar(resultado)  # solo las consultas NUEVAS se escriben en el JSONL


def pintar_chunks(chunks: list[dict]) -> None:
    for c in chunks:
        st.markdown(
            f"**`{c['chunk_id']}`** · similitud {c['similitud']:.4f} · "
            f"distancia {c['distancia']:.4f} · [{c['titulo']}]({c['url']})"
        )
        st.text(c["texto"])
        st.markdown("---")


def pintar_asistente(r: dict) -> None:
    """Contenido del bocadillo del asistente para un turno (HA1a):
    misma lógica rica que la app M2, ahora por turno del historial."""
    if r.get("llm_llamado"):
        st.markdown(r["respuesta"])
        st.markdown("**Fuentes consultadas**")
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
        f"umbral {r['umbral_distancia']} · {r['timestamp']}"
    )


# ----------------------------------------------------------------- interfaz
st.set_page_config(page_title="AMAFE Responde", page_icon="💬", layout="centered")

st.title("💬 AMAFE Responde")
st.caption(
    "Asistente RAG sobre la documentación pública de [AMAFE](https://www.amafe.org). "
    "Proyecto formativo (Bootcamp IA · Factoría F5): **no es una herramienta oficial "
    "de AMAFE**. Las respuestas se generan solo a partir del corpus público y "
    "citan sus fuentes; contrasta siempre con los enlaces."
)

st.session_state.setdefault("historial", [])
st.session_state.setdefault("historial_cargado", False)
st.session_state.setdefault("error", None)

# --- Controles de historial (HB1b + HB2a) ---
col_cargar, col_limpiar = st.columns(2)
if col_cargar.button(
    "📂 Cargar historial anterior",
    use_container_width=True,
    disabled=st.session_state.historial_cargado,
):
    turnos, descartadas = cargar_historial()
    if turnos:
        st.session_state.historial = turnos + st.session_state.historial
        st.session_state.historial_cargado = True
        if descartadas:
            st.session_state.error = (
                f"Historial cargado, pero se han descartado {descartadas} "
                "líneas no válidas del registro."
            )
    else:
        st.session_state.error = "No hay historial anterior que cargar."
    st.rerun()  # aplica ya el estado (evita doble clic que duplicaría turnos)

if col_limpiar.button("🧹 Limpiar conversación", use_container_width=True):
    st.session_state.historial = []
    st.session_state.historial_cargado = False  # permite recargar tras limpiar
    st.session_state.error = None
    st.rerun()

# --- Preguntas sugeridas: solo con el historial vacío (HA2b) ---
if not st.session_state.historial:
    st.markdown("**Preguntas sugeridas:**")
    cols = st.columns(2)
    for i, p in enumerate(PREGUNTAS_SUGERIDAS):
        if cols[i % 2].button(p, use_container_width=True):
            ejecutar(p)
            st.rerun()

if st.session_state.error:
    st.error(st.session_state.error)

# --- Historial de la conversación (HA1a) ---
for r in st.session_state.historial:
    with st.chat_message("user"):
        st.markdown(r["pregunta"])
    with st.chat_message("assistant"):
        pintar_asistente(r)

if st.session_state.historial:
    st.caption("Cada consulta nueva queda registrada en `logs/consultas_app.jsonl`.")

# --- Entrada de chat (fija abajo) ---
if pregunta := st.chat_input("Escribe tu pregunta sobre AMAFE"):
    ejecutar(pregunta)
    st.rerun()
