#!/usr/bin/env bash
# m2b_gestion_issue_rama — crea la issue M2b, la añade al proyecto 77 y crea la rama.
# Ejecutar desde la raíz del repo (D:\Proyectos\amafe-responde), con gh autenticado.
# stdout=datos, stderr=diagnóstico (R1).
set -euo pipefail

echo "== [1/3] Creando issue M2b ==" >&2
URL_ISSUE=$(gh issue create \
  --repo Bootcamp-IA-P6/amafe-responde \
  --title "M2b — Historial y persistencia en la app Streamlit" \
  --body "Encargo del tutor: historial visual de la conversación y persistencia entre sesiones.

Decisiones (docs/decisiones.md, 20260721): HA1a (dict completo por turno), HA2b (sugeridas solo con historial vacío), HB1b (botón de recarga desde logs/consultas_app.jsonl), HB2a (limpiar solo lo visual), HC0 (sin memoria conversacional del LLM), S1 (spinner dinámico).

Material de estudio: https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps")
echo "$URL_ISSUE"

echo "== [2/3] Añadiendo la issue al proyecto 77 ==" >&2
gh project item-add 77 --owner Bootcamp-IA-P6 --url "$URL_ISSUE" >&2

echo "== [3/3] Creando la rama de trabajo ==" >&2
git checkout -b feature/m2b-historial
git status -sb
