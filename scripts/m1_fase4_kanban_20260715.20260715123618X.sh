#!/usr/bin/env bash
# m1_fase4_kanban_20260715.sh — M1/fase 4: GitHub Project + issues K1-01..07
# Proyecto: AMAFE Responde · Decisión: K1 (20260715)
# Uso: desde la raíz del repo:  bash scripts/m1_fase4_kanban_20260715.sh
# HACE: crea el proyecto "AMAFE Responde" en la org, crea 7 issues en el repo
#       y las añade al tablero. Aborta si el proyecto ya existe (anti-duplicados).
# NOTA: las issues entran en el tablero sin estado; arrastrarlas a "Todo"
#       en la web es un minuto (asignar Status por CLI requiere IDs internos).

set -eu

OWNER="Bootcamp-IA-P6"
REPO="${OWNER}/amafe-responde"
TITULO_PROYECTO="AMAFE Responde"

command -v gh >&1 2>&1 || { echo "[ABORTADO] gh no está en el PATH." >&2; exit 1; }

# Anti-duplicados: ¿existe ya un proyecto con este título en la org?
if gh project list --owner "$OWNER" --format json --jq '.projects[].title' 2>&1 \
   | grep -Fxq "$TITULO_PROYECTO"; then
    echo "[ABORTADO] Ya existe un proyecto '$TITULO_PROYECTO' en $OWNER." >&2
    exit 1
fi

echo "== 1. Crear el proyecto =="
PROJ_NUM=$(gh project create --owner "$OWNER" --title "$TITULO_PROYECTO" --format json --jq '.number')
echo "Proyecto #${PROJ_NUM} creado en ${OWNER}"

crear_issue() {  # $1 = título · $2 = cuerpo
    local URL
    URL=$(gh issue create -R "$REPO" --title "$1" --body "$2")
    echo "  ${URL}  ·  $1"
    gh project item-add "$PROJ_NUM" --owner "$OWNER" --url "$URL" >&1
}

echo "== 2. Crear issues y añadirlas al tablero =="
crear_issue "M1 · README técnico" \
"Instalación (uv), ejecución de los 4 módulos, arquitectura RAG y enlace a docs/decisiones.md. Entregable del briefing."

crear_issue "M2 · app.py con Streamlit" \
"Interfaz mínima: pregunta, respuesta con citas, fuentes con URL, mensaje de no-sé, preguntas sugeridas y log JSONL de consultas. Consume generar_respuesta() de src/generacion.py (decisión 2a)."

crear_issue "M3 · Groq como LLM" \
"Cambiar LLM_BASE_URL, LLM_MODEL y LLM_API_KEY en .env (cosecha de la decisión 1a). Primera clave secreta real del proyecto: verificar .gitignore y no pegarla nunca en logs ni commits."

crear_issue "M4 · Batería de 20 preguntas + informe de evaluación" \
"Dataset de ≥20 preguntas reales sobre AMAFE y runner que genere el informe (pregunta, chunks, puntuaciones, respuesta, fuentes). Ejecución comparada Ollama vs Groq."

crear_issue "M4 · Recalibrar UMBRAL_DISTANCIA (U1)" \
"Recalibrar el umbral 0.75 con los datos de la batería de 20 (previsto en la decisión U1 de docs/decisiones.md)."

crear_issue "M5 · Dockerizar la aplicación" \
"Imagen ligera de la app Streamlit; el LLM queda fuera vía API. Variables de entorno para configurar el modelo (nivel medio del briefing)."

crear_issue "M6 · Despliegue en entorno accesible" \
"Decidir Streamlit Community Cloud vs HF Spaces y desplegar la demo. Gestionar la clave Groq como secreto de la plataforma."

echo
echo "== 3. Hecho =="
echo "Tablero: https://github.com/orgs/${OWNER}/projects/${PROJ_NUM}"
echo "Siguiente paso manual: en la web, vista Board y arrastrar las 7 issues a 'ToDo'."
