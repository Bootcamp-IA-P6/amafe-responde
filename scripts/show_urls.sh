#!/usr/bin/env bash
# show_urls.sh — regenera docs/URLS.md con datos reales de la API de GitHub.
# Adaptado del generador del P10JJ al proyecto amafe-responde (decisión U-M1b).
# Ejecutar desde la raíz del repo, con gh autenticado:
#     bash scripts/show_urls.sh
# R1: stdout=datos (ninguno aquí), stderr=diagnóstico. Salida: docs/URLS.md (LF).
set -euo pipefail

REPO="Bootcamp-IA-P6/amafe-responde"
SALIDA="docs/URLS.md"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "== [1/3] Consultando la API de GitHub (gh api) ==" >&2
gh api "repos/$REPO/issues?state=all&per_page=100" > "$TMP/issues.json"
gh api "repos/$REPO/pulls?state=all&per_page=100"  > "$TMP/pulls.json"

echo "== [2/3] Inventariando ficheros clave (git ls-files) ==" >&2
git ls-files "src/*.py" "app/*.py" "tests/*.py" > "$TMP/ficheros.txt"

echo "== [3/3] Generando $SALIDA ==" >&2
uv run python - "$TMP" "$SALIDA" "$REPO" << 'PYEOF'
import json
import sys
from datetime import date
from pathlib import Path

tmp, salida, repo = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
base = f"https://github.com/{repo}"
raw = f"https://raw.githubusercontent.com/{repo}/main"

todas = json.load(open(tmp / "issues.json", encoding="utf-8"))
pulls = json.load(open(tmp / "pulls.json", encoding="utf-8"))
issues = [i for i in todas if "pull_request" not in i]
mergeados = sorted((p for p in pulls if p.get("merged_at")),
                   key=lambda p: p["number"])

def linea_issue(i):
    estado = "cerrada" if i["state"] == "closed" else "abierta"
    return f"- **#{i['number']}** [{estado}] {i['title']} — {i['html_url']}"

def bloque_ficheros(prefijo, titulo):
    fs = [f for f in ficheros if f.startswith(prefijo)]
    if not fs:
        return []
    out = [f"### {titulo}", ""]
    out += [f"- {f.split('/')[-1]}: {raw}/{f}" for f in fs]
    out.append("")
    return out

ficheros = [l.strip() for l in open(tmp / "ficheros.txt", encoding="utf-8")
            if l.strip()]

L = []
L += [f"# amafe-responde — Mapa de URLs", "",
      "> Centro de navegación del proyecto AMAFE Responde (P12JJ).",
      "> Generado automáticamente por `scripts/show_urls.sh`.",
      f"> Última revisión: {date.today().isoformat()}", "", "---", "",
      "## Repositorio", "",
      f"- Repo: {base}",
      f"- Rama main: {base}/tree/main",
      f"- Ramas: {base}/branches",
      f"- Commits (main): {base}/commits/main", "", "---", "",
      "## Pull Requests", "",
      f"- Todos: {base}/pulls?q=is%3Apr",
      f"- Abiertos: {base}/pulls?q=is%3Apr+is%3Aopen",
      f"- Mergeados: {base}/pulls?q=is%3Apr+is%3Amerged", "",
      "### Histórico de PRs mergeados", ""]
L += [f"- **#{p['number']}** {p['title']} — {p['html_url']}" for p in mergeados]
L += ["", "---", "", "## Issues", "",
      f"- Todas: {base}/issues?q=is%3Aissue",
      f"- Abiertas: {base}/issues?q=is%3Aissue+is%3Aopen",
      f"- Cerradas: {base}/issues?q=is%3Aissue+is%3Aclosed", "",
      f"### Listado (estado a {date.today().isoformat()})", ""]
L += [linea_issue(i) for i in sorted(issues, key=lambda i: i["number"])]
L += ["", "---", "", "## Project Kanban", "",
      "- Project #77 — AMAFE Responde: "
      "https://github.com/orgs/Bootcamp-IA-P6/projects/77", "", "---", "",
      "## Archivos clave (RAW desde `main`)", "",
      "> Las URLs RAW devuelven el fichero plano (sin envoltura GitHub). "
      "Útiles para curl/wget/scripts.", "",
      "### Documentación", "",
      f"- README: {raw}/README.md",
      f"- LICENSE: {raw}/LICENSE",
      f"- Registro de decisiones: {raw}/docs/decisiones.md",
      f"- Este mapa: {raw}/docs/URLS.md", "",
      "### Configuración", "",
      f"- pyproject.toml: {raw}/pyproject.toml",
      f"- .env.example: {raw}/.env.example",
      f"- .gitignore: {raw}/.gitignore", ""]
L += bloque_ficheros("src/", "Pipeline RAG (`src/`)")
L += bloque_ficheros("app/", "Aplicación (`app/`)")
L += bloque_ficheros("tests/", "Pruebas (`tests/`)")
L += ["---", "", "## Recursos externos", "",
      "- Web pública de AMAFE (origen del corpus): https://www.amafe.org",
      "- Tutorial Streamlit de apps conversacionales (base de M2b): "
      "https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps",
      "- Documentación Streamlit AppTest: "
      "https://docs.streamlit.io/develop/api-reference/app-testing",
      "- Groq console (modelos y límites): https://console.groq.com/",
      "- Ollama: https://ollama.com/",
      "- ChromaDB: https://docs.trychroma.com/",
      "- sentence-transformers: https://www.sbert.net/",
      "- Documentación uv: https://docs.astral.sh/uv/",
      "- Conventional Commits: https://www.conventionalcommits.org/",
      "- Roadmap del bootcamp: https://roadmap-mad-ai-p4.coderf5.es/", "",
      "---", "",
      "> Este fichero se regenera con `bash scripts/show_urls.sh`. "
      "No editar a mano.", ""]

salida.parent.mkdir(parents=True, exist_ok=True)
with open(salida, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))
print(f"OK: {salida} regenerado "
      f"({len(issues)} issues, {len(mergeados)} PRs mergeados)", file=sys.stderr)
PYEOF
echo "== Hecho ==" >&2
