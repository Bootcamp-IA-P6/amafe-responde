#!/usr/bin/env bash
# comparar_temperaturas_20260713.sh
# AMAFE Responde - Experimento decisión 4: temperature 0.0 vs 0.2
# Ejecuta 4 preguntas con cada temperatura y guarda todo en un JSONL
# trazable en logs/. Requiere: sella/run/banner exportadas en .bashrc.
#
# Uso (desde la raíz del proyecto, D:/Proyectos/amafe-responde):
#   bash scripts/comparar_temperaturas_20260713.sh
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
  banner "--- Tanda temperature=${T} ---"
  for P in "${PREGUNTAS[@]}"; do
    run uv run python src/generacion.py "${P}" --temperature "${T}" --json >> "${OUT}"
  done
done

banner "Hecho. Resultados en ${OUT}"
echo "Comparación rápida (T | pregunta | respuesta abreviada):"
uv run python - "${OUT}" <<'PYEOF'
import json, sys
for linea in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(linea)
    resp = " ".join(r["respuesta"].split())[:100]
    print(f"T={r['temperature']} | {r['pregunta'][:40]:40} | {resp}...")
PYEOF
