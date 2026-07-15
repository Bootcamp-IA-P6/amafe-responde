#!/usr/bin/env bash
# m1_fase3_purga_historial_20260714.sh — M1/fase 3: R2a (backup + filter-repo)
# Proyecto: AMAFE Responde · Decisión: R2a (20260714)
# Uso: desde la raíz del repo:  bash scripts/m1_fase3_purga_historial_20260714.sh
# HACE: (1) exige worktree limpio salvo untracked, (2) backup .tgz en D:\Proyectos,
#       (3) purga logs/*.log y *inventario_pdf*.csv de TODO el historial,
#       (4) verifica. REESCRIBE HASHES y ELIMINA el remote origin (filter-repo).
# NO HACE: nada contra GitHub. Los comandos gh se imprimen al final para
#          ejecutarlos A MANO, con ojos encima.

set -eu

# --- 0. Preconditions ---------------------------------------------------
if [ ! -d .git ] || [ ! -f pyproject.toml ]; then
    echo "[ABORTADO] Ejecutar desde la raíz de amafe-responde." >&2
    exit 1
fi
if git status --porcelain | grep -qvE '^\?\?'; then
    echo "[ABORTADO] Hay cambios sin commitear (M/D/staged)." >&2
    echo "  Commitea antes el housekeeping (parches renombrados, scripts m1)" >&2
    echo "  o guarda los cambios. Los ficheros untracked (??) sí se permiten." >&2
    git status --short | grep -vE '^\?\?' >&2
    exit 1
fi

# Localizar git-filter-repo (instalado o vía uvx)
if git filter-repo --version >/dev/null 2>&1; then
    FR="git filter-repo"
elif command -v git-filter-repo >/dev/null 2>&1; then
    FR="git-filter-repo"
elif command -v uvx >/dev/null 2>&1; then
    FR="uvx git-filter-repo"
    echo "[INFO] Usando uvx git-filter-repo (efímero, sin instalación)."
else
    echo "[ABORTADO] No encuentro git-filter-repo. Instalar con:" >&2
    echo "  uv tool install git-filter-repo" >&2
    exit 1
fi

# --- 1. Métricas ANTES --------------------------------------------------
COMMITS_ANTES=$(git rev-list --count HEAD)
CSV_ANTES=$(git log --all --oneline -- 'logs/inventario_pdf_20260713154857L.csv' | wc -l)
echo "== ANTES: ${COMMITS_ANTES} commits · CSV inventario en ${CSV_ANTES} commit(s) =="

# --- 2. Backup completo (sin .venv, recreable con uv sync) ---------------
SELLO=$(date +%Y%m%d%H%M%S)
DIRNAME=$(basename "$PWD")
BACKUP="../${DIRNAME}.backup_prefiltro.${SELLO}.tgz"
echo "== Backup: ${BACKUP} =="
tar --exclude='.venv' -czf "${BACKUP}" -C .. "${DIRNAME}"
ls -lh "${BACKUP}"

# --- 3. Purga del historial ----------------------------------------------
echo "== Purgando logs/*.log y *inventario_pdf*.csv de todo el historial =="
${FR} --force --invert-paths \
    --path-glob 'logs/*.log' \
    --path-glob '*inventario_pdf*.csv'

# --- 4. Verificación -----------------------------------------------------
COMMITS_DESPUES=$(git rev-list --count HEAD)
CSV_DESPUES=$(git log --all --oneline -- 'logs/inventario_pdf_20260713154857L.csv' | wc -l)
LOGS_HIST=$(git log --all --name-only --pretty=format: | grep -cE '^logs/.+\.log$|inventario_pdf.*\.csv$' || true)
echo
echo "== DESPUÉS =="
echo "Commits: ${COMMITS_ANTES} -> ${COMMITS_DESPUES} (los que solo tocaban logs se podan)"
echo "CSV inventario en historial: ${CSV_DESPUES} (esperado: 0)"
echo "Apariciones de logs/*.log o inventario_pdf*.csv en todo el historial: ${LOGS_HIST} (esperado: 0)"
echo "Tracked en logs/: $(git ls-files logs/ | tr '\n' ' ') (esperado: solo logs/.gitkeep)"
echo "src/inventario_pdf.py sigue tracked: $(git ls-files src/inventario_pdf.py)"
echo "Remote origin (esperado: vacío, filter-repo lo elimina):"
git remote -v || true
echo
if [ "${CSV_DESPUES}" != "0" ] || [ "${LOGS_HIST}" != "0" ]; then
    echo "[AVISO] La verificación NO da 0. NO ejecutar los pasos gh; enviar este log a Claude." >&2
    exit 1
fi

# --- 5. Pasos manuales ----------------------------------------------------
cat <<'EOF'
== VERIFICACIÓN OK. Pasos gh A MANO, en este orden ==

  # 5a. Ampliar el token con permiso de borrado (abre navegador):
  gh auth refresh -h github.com -s delete_repo

  # 5b. Borrar el repo remoto contaminado:
  gh repo delete Bootcamp-IA-P6/amafe-responde --yes

  # 5c. Recrear y subir el historial limpio:
  gh repo create Bootcamp-IA-P6/amafe-responde --public --source=. --remote=origin --push

  # 5d. Comprobación final en remoto:
  gh repo view Bootcamp-IA-P6/amafe-responde --web
EOF
