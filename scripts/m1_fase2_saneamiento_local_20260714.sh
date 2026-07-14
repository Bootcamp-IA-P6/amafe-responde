#!/usr/bin/env bash
# m1_fase2_saneamiento_local_20260714.sh — M1/fase 2: aplica E1a + L1c EN LOCAL
# Proyecto: AMAFE Responde · Decisiones: E1a, L1c (20260714)
# Uso: desde la raíz del repo, con el fichero LICENSE ya copiado a la raíz:
#     bash scripts/m1_fase2_saneamiento_local_20260714.sh
# HACE: amplía .gitignore, des-trackea ficheros E1a (SIN borrarlos del disco),
#       añade LICENSE y docs/decisiones.md, y commitea.
# NO HACE: push, ni tocar el historial, ni borrar nada del disco.

set -eu

if [ ! -d .git ] || [ ! -f pyproject.toml ]; then
    echo "[ABORTADO] Ejecutar desde la raíz de amafe-responde." >&2
    exit 1
fi
if [ ! -f LICENSE ]; then
    echo "[ABORTADO] Falta LICENSE en la raíz (copiarlo antes de ejecutar)." >&2
    exit 1
fi
if grep -q "E1a (20260714)" .gitignore; then
    echo "[ABORTADO] .gitignore ya contiene la sección E1a (¿doble ejecución?)." >&2
    exit 1
fi

echo "== 1. Ampliar .gitignore (sección E1a) =="
cat >> .gitignore <<'EOF'

# M1 — Exclusiones del repo público, decisión E1a (20260714)
logs/*
!logs/.gitkeep
eval/lista_blanca*.csv
*inventario_pdf*.csv
EOF
echo "(añadida)"

echo "== 2. Des-trackear ficheros E1a (quedan en disco) =="
git ls-files -z | grep -zE '^logs/.+|inventario_pdf.*\.csv$|^eval/lista_blanca' \
    | grep -zv '^logs/\.gitkeep$' \
    | xargs -0 -r git rm -q --cached --
git ls-files | grep -E '^logs/|inventario_pdf|lista_blanca' || echo "(solo debería quedar logs/.gitkeep arriba, si aparece)"

echo "== 3. Añadir LICENSE, .gitignore y decisiones.md =="
git add LICENSE .gitignore docs/decisiones.md

echo "== 4. Commit =="
git commit -m "chore(repo): exclusiones E1a, licencia MIT y decisiones 20260714

- .gitignore: excluye logs/ (salvo .gitkeep), lista_blanca*.csv e inventario_pdf*.csv
- des-trackea logs e inventario PDF del indice (permanecen en disco)
- LICENSE MIT, titular 'AMAFE Responde contributors' (decision L1c)
- docs/decisiones.md: entradas R1 y H1 del 20260714"

echo
echo "== Estado final =="
git status --short | head -20
echo
echo "# Fin. Commit local creado. El push queda pendiente de la decisión R2."
