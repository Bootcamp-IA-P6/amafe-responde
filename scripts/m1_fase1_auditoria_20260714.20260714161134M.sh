#!/usr/bin/env bash
# m1_fase1_auditoria_20260714.sh — M1/fase 1: auditoría pre-push (SOLO LECTURA)
# Proyecto: AMAFE Responde · Decisión: H1a/H1d (docs/decisiones.md 20260714)
# Uso: desde la raíz del repo:  bash scripts/m1_fase1_auditoria_20260714.sh
# No modifica NADA. Informe por stdout (redirigible a logs/ sin contaminación).

set -u

echo "# Auditoría pre-push — $(date +%Y%m%d%H%M%S)"
echo "# Directorio: $(pwd)"
echo

# 0. Sanidad: ¿estamos en la raíz del repo correcto?
if [ ! -d .git ] || [ ! -f pyproject.toml ]; then
    echo "[ABORTADO] Ejecutar desde la raíz de amafe-responde (falta .git o pyproject.toml)." >&2
    exit 1
fi
echo "== 0. Remotos actuales (debería estar vacío: aún sin remoto) =="
git remote -v
echo

echo "== A1. ¿.env en el historial? (esperado: 0 líneas) =="
git log --all --full-history --oneline -- .env
echo "A1 total: $(git log --all --full-history --oneline -- .env | wc -l)"
echo

echo "== A2. Ficheros de riesgo actualmente TRACKED (esperado: revisar lista) =="
git ls-files | grep -E '(^|/)(downloads|chroma_db|logs|\.obsidian|__pycache__)(/|$)|lista_blanca|inventario_pdf|TRASPASO|(^|/)\.env$' \
    || echo "(ninguno)"
echo

echo "== A3. Barrido de posibles secretos en TODO el historial (esperado: 0) =="
N_SECRETOS=$(git log --all -p | grep -cE 'gsk_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{10,}|api[_-]?key[[:space:]]*=[[:space:]]*[^[:space:]$#]' || true)
echo "A3 coincidencias: ${N_SECRETOS}"
echo

echo "== A4. .gitignore actual =="
cat .gitignore
echo

echo "== A5. .env.example (verificar que solo hay placeholders) =="
cat .env.example
echo

echo "== A6. gh CLI disponible y autenticado =="
if command -v gh >/dev/null 2>&1; then
    gh --version | head -1
    gh auth status 2>&1 | head -6
else
    echo "[AVISO] gh no está instalado. Instalar: https://cli.github.com (winget install GitHub.cli)"
fi
echo

echo "== A7. Estado del working tree =="
git status --short | head -40
echo
echo "# Fin de auditoría. Ninguna modificación realizada."
