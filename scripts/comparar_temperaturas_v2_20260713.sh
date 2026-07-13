#!/usr/bin/env bash
# comparar_temperaturas_v2_20260713.sh
# AMAFE Responde - Experimento decisión 4: temperature 0.0 vs 0.2
#
# v2 (20260713): corrige bug de v1 — `run cmd >> fichero` redirigía también
# el banner de run() al JSONL, corrompiéndolo. Ahora banner y redirección
# van separados, y el resumen ignora cualquier línea que no empiece por '{'.
#
# Uso (desde la raíz del proyecto):
#   bash scripts/comparar_temperaturas_v2_20260713.sh
set -euo pipefail

mkdir -p logs
OUT="logs/comparativa_temp_$(sella).jsonl"
banner "Experimento temperaturas 0.0 vs 0.2 -> ${OUT}"

PREGUNTAS=(
  "¿Cómo puedo pedir cita?"
  "¿Qué es el Espacio Joven?"
  "¿Qué información pública existe sobre auditorías?"
  "¿Cuánto cuesta un piso en Móstoles?"
)

for T in 0.0 0.2; do
  for P in "${PREGUNTAS[@]}"; do
    banner "T=${T} :: ${P}"
    uv run python src/generacion.py "${P}" --temperature "${T}" --json >> "${OUT}"
  done
done

banner "Hecho. Resultados en ${OUT}"
echo "Comparación rápida (T | LLM | pregunta | respuesta abreviada):"
uv run python - "${OUT}" <<'PYEOF'
import json, sys
for linea in open(sys.argv[1], encoding="utf-8"):
    if not linea.lstrip().startswith("{"):
        continue  # tolerante a banners u otro ruido
    r = json.loads(linea)
    resp = " ".join(r["respuesta"].split())[:100]
    llm = "LLM" if r["llm_llamado"] else "---"
    print(f"T={r['temperature']} | {llm} | {r['pregunta'][:40]:40} | {resp}...")
PYEOF
