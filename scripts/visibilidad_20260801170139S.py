#!/usr/bin/env python3
"""Repliegue / restauracion de visibilidad de los activos publicos de AMAFE Responde.

Decisiones: A4 (repliegue completo), B3 (HF privado + pausado),
D1 (dry-run por defecto), D2 (--revertir), D3 (script sellado),
D4 (verificacion previa de permisos, aborta si falta alguno),
E1 (HF_TOKEN desde <raiz>/.env con python-dotenv), F1 (el entorno tiene
precedencia sobre .env), G1 (solo este script), H1 (se informa la procedencia
del token, nunca su valor), K5 (HF_HUB_OFFLINE se neutraliza solo en este
proceso: este script requiere red hacia HF por definicion; se informa si se
detecto activa).

Convencion R1: stdout = datos (JSON), stderr = diagnosticos.

Activos gestionados
  1. Streamlit Community Cloud ......... MANUAL (no existe API publica)
  2. HF Space JJRSE/amafe-responde ..... API huggingface_hub
  3. Repo Bootcamp-IA-P6/amafe-responde  gh CLI
  4. Project #77 (org) ................. gh CLI

Uso (SIEMPRE con 'uv run': 'python' resuelve al Python global de Windows, que no
tiene huggingface_hub; el .venv del proyecto si lo tiene)
  uv run python scripts/visibilidad_20260801170139S.py              # dry-run
  uv run python scripts/visibilidad_20260801170139S.py --ejecutar    # repliegue
  uv run python scripts/visibilidad_20260801170139S.py --revertir    # dry-run
  uv run python scripts/visibilidad_20260801170139S.py --revertir --ejecutar

Requiere: gh autenticado (scopes repo, project) y HF_TOKEN, bien exportado en
el entorno, bien definido en <raiz>/.env (que esta en .gitignore).
API verificada contra huggingface_hub 1.23.0.
Codigos de salida: 0 ok / 1 error en alguna accion / 2 verificacion previa fallida.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO = "Bootcamp-IA-P6/amafe-responde"
ORG = "Bootcamp-IA-P6"
PROYECTO = "77"
SPACE = "JJRSE/amafe-responde"
SCOPES_NECESARIOS = ("repo", "project")

# La ruta del .env se resuelve desde este fichero, no desde el CWD: el script
# debe funcionar igual lanzado desde la raiz o desde scripts/.
RAIZ = Path(__file__).resolve().parents[1]
RUTA_ENV = RAIZ / ".env"


def _cargar_entorno() -> str:
    """Carga <raiz>/.env sin sobrescribir el entorno (F1).

    Devuelve la procedencia de HF_TOKEN: 'entorno', '.env' o 'ausente'.
    Nunca devuelve ni registra el valor del token (H1).
    """
    ya_exportado = bool(os.environ.get("HF_TOKEN"))
    load_dotenv(RUTA_ENV)  # override=False por defecto: el entorno gana
    if ya_exportado:
        return "entorno"
    return ".env" if os.environ.get("HF_TOKEN") else "ausente"


PROCEDENCIA_HF = _cargar_entorno()


def _neutralizar_offline() -> bool:
    """K1: elimina HF_HUB_OFFLINE de este proceso y devuelve si estaba activa.

    Debe ejecutarse ANTES de cualquier import de huggingface_hub: la libreria
    fija la constante en el momento del import, no en cada llamada. El resto
    del sistema (Dockerfile:28, shell del usuario) no se toca.
    """
    valor = os.environ.pop("HF_HUB_OFFLINE", None)
    return valor is not None and valor.strip().upper() in ("1", "TRUE", "YES", "ON")


OFFLINE_NEUTRALIZADA = _neutralizar_offline()


def log(msg: str = "") -> None:
    print(msg, file=sys.stderr)


def gh(*args: str) -> str:
    """Ejecuta gh y devuelve stdout. Lanza RuntimeError con el stderr si falla."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout.strip()


def hf_api():
    try:
        from huggingface_hub import HfApi
    except ImportError as e:
        raise RuntimeError(
            f"{e}. Interprete en uso: {sys.executable}. "
            "huggingface_hub vive en el .venv del proyecto: relanza con "
            f"'uv run python scripts/{Path(__file__).name}'"
        ) from e

    token = os.environ.get("HF_TOKEN")
    if not token:
        pista = "" if RUTA_ENV.exists() else f" (no existe {RUTA_ENV})"
        raise RuntimeError(
            f"HF_TOKEN no definido ni en el entorno ni en {RUTA_ENV.name}{pista}"
        )
    return HfApi(token=token)


# --- verificacion previa (D4) ----------------------------------------------


def _scopes_gh() -> set[str]:
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    for linea in (r.stdout + r.stderr).splitlines():
        if "Token scopes:" in linea:
            crudo = linea.split("Token scopes:", 1)[1]
            return {t.strip().strip("'\"") for t in crudo.split(",") if t.strip()}
    raise RuntimeError("no se pudo leer 'Token scopes' de gh auth status")


def verificar() -> list[dict]:
    """Devuelve una lista de comprobaciones {nombre, ok, detalle}."""
    checks: list[dict] = []

    def check(nombre, fn):
        try:
            checks.append({"nombre": nombre, "ok": True, "detalle": fn()})
        except Exception as e:  # noqa: BLE001
            checks.append({"nombre": nombre, "ok": False, "detalle": str(e)})

    def _gh_instalado():
        ruta = shutil.which("gh")
        if not ruta:
            raise RuntimeError("gh no encontrado en PATH")
        return ruta

    def _gh_scopes():
        scopes = _scopes_gh()
        faltan = [s for s in SCOPES_NECESARIOS if s not in scopes]
        if faltan:
            raise RuntimeError(
                f"faltan scopes {faltan}; ejecuta: gh auth refresh -s {','.join(faltan)}"
            )
        return f"scopes ok ({', '.join(sorted(scopes))})"

    def _repo_admin():
        if gh("api", f"repos/{REPO}", "--jq", ".permissions.admin") != "true":
            raise RuntimeError(f"sin permiso admin sobre {REPO}")
        return f"admin sobre {REPO}"

    def _proyecto_legible():
        datos = json.loads(
            gh("project", "view", PROYECTO, "--owner", ORG, "--format", "json")
        )
        return f"project #{PROYECTO} '{datos['title']}' public={datos['public']}"

    def _hf_escritura():
        api = hf_api()
        quien = api.whoami()
        rol = (quien.get("auth", {}).get("accessToken") or {}).get("role")
        if rol is not None and rol != "write":
            raise RuntimeError(f"el token HF tiene rol '{rol}', se necesita 'write'")
        propietario = SPACE.split("/", 1)[0]
        nombres = {quien.get("name")} | {
            o.get("name") for o in quien.get("orgs", []) or []
        }
        if propietario not in nombres:
            raise RuntimeError(
                f"el token HF pertenece a {quien.get('name')!r}, "
                f"no da acceso al namespace {propietario!r}"
            )
        api.space_info(SPACE)
        sufijo = "" if rol else " (rol no expuesto por el token)"
        extra = "; HF_HUB_OFFLINE detectada y neutralizada" if OFFLINE_NEUTRALIZADA else ""
        return (
            f"HF {quien.get('name')} con acceso a {SPACE}{sufijo}; "
            f"HF_TOKEN leido de: {PROCEDENCIA_HF}{extra}"
        )

    check("gh_instalado", _gh_instalado)
    check("gh_scopes", _gh_scopes)
    check("repo_admin", _repo_admin)
    check("proyecto_legible", _proyecto_legible)
    check("hf_escritura", _hf_escritura)
    return checks


# --- lectura de estado ------------------------------------------------------


def estado_repo() -> dict:
    return {"privado": gh("api", f"repos/{REPO}", "--jq", ".private") == "true"}


def estado_proyecto() -> dict:
    datos = json.loads(
        gh("project", "view", PROYECTO, "--owner", ORG, "--format", "json")
    )
    return {"privado": not datos["public"]}


def estado_space() -> dict:
    info = hf_api().space_info(SPACE)
    return {
        "privado": bool(info.private),
        "etapa": getattr(getattr(info, "runtime", None), "stage", None),
    }


# --- acciones ---------------------------------------------------------------


def repo_a(privado: bool) -> str:
    destino = "private" if privado else "public"
    gh(
        "repo",
        "edit",
        REPO,
        "--visibility",
        destino,
        "--accept-visibility-change-consequences",
    )
    return f"repo -> {destino}"


def proyecto_a(privado: bool) -> str:
    destino = "PRIVATE" if privado else "PUBLIC"
    gh("project", "edit", PROYECTO, "--owner", ORG, "--visibility", destino)
    return f"project #{PROYECTO} -> {destino}"


def space_a(privado: bool) -> str:
    api = hf_api()
    api.update_repo_settings(repo_id=SPACE, repo_type="space", private=privado)
    if privado:
        api.pause_space(SPACE)
        return "space -> private + paused"
    api.restart_space(SPACE)
    return "space -> public + restarted"


# --- orquestacion -----------------------------------------------------------

PASOS = [
    ("space", estado_space, space_a),
    ("repo", estado_repo, repo_a),
    ("proyecto", estado_proyecto, proyecto_a),
]

AVISO_STREAMLIT = """PASO MANUAL (no automatizable, no hay API):
  1. Abre https://share.streamlit.io
  2. Menu (...) junto a amafe-responde -> Settings -> Sharing
  3. Cambia el acceso a privado (o publico, si estas revirtiendo)
Hazlo ANTES de privatizar el repo: si Streamlit pierde acceso al codigo,
el siguiente redeploy puede quedar en error."""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ejecutar",
        action="store_true",
        help="aplica los cambios (sin este flag solo simula)",
    )
    p.add_argument(
        "--revertir",
        action="store_true",
        help="restaura visibilidad publica en lugar de replegar",
    )
    args = p.parse_args()

    privado = not args.revertir
    modo = "EJECUCION" if args.ejecutar else "DRY-RUN"
    accion = "REPLIEGUE A PRIVADO" if privado else "RESTAURACION A PUBLICO"
    utc = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    log(f"=== {accion} :: {modo} ===")
    log("--- verificacion previa ---")
    checks = verificar()
    for c in checks:
        log(f"[{'OK ' if c['ok'] else 'FAIL'}] {c['nombre']}: {c['detalle']}")

    if not all(c["ok"] for c in checks):
        print(
            json.dumps(
                {
                    "utc": utc,
                    "modo": modo,
                    "accion": accion,
                    "hf_token_origen": PROCEDENCIA_HF,
                    "hf_hub_offline_neutralizada": OFFLINE_NEUTRALIZADA,
                    "resultado": "verificacion_fallida",
                    "verificacion": checks,
                    "activos": [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        log()
        log("Abortado: corrige lo anterior. Nada modificado.")
        return 2

    log()
    log(AVISO_STREAMLIT)
    log()

    orden = PASOS if privado else list(reversed(PASOS))
    resultados = []
    for nombre, leer, aplicar in orden:
        entrada = {"activo": nombre, "objetivo_privado": privado}
        try:
            antes = leer()
        except Exception as e:  # noqa: BLE001
            entrada.update(estado="error_lectura", detalle=str(e))
            log(f"[{nombre}] ERROR leyendo estado: {e}")
            resultados.append(entrada)
            continue

        entrada["antes"] = antes
        if antes["privado"] == privado:
            entrada["estado"] = "sin_cambios"
            log(f"[{nombre}] ya esta en el estado deseado ({antes})")
        elif not args.ejecutar:
            entrada["estado"] = "pendiente"
            log(f"[{nombre}] SIMULADO: cambiaria {antes} -> privado={privado}")
        else:
            try:
                detalle = aplicar(privado)
                entrada.update(estado="aplicado", detalle=detalle, despues=leer())
                log(f"[{nombre}] OK: {detalle}")
            except Exception as e:  # noqa: BLE001
                entrada.update(estado="error", detalle=str(e))
                log(f"[{nombre}] ERROR: {e}")
        resultados.append(entrada)

    print(
        json.dumps(
            {
                "utc": utc,
                "modo": modo,
                "accion": accion,
                "hf_token_origen": PROCEDENCIA_HF,
                "hf_hub_offline_neutralizada": OFFLINE_NEUTRALIZADA,
                "resultado": "ok",
                "verificacion": checks,
                "streamlit": "manual_pendiente",
                "activos": resultados,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    log()
    if not args.ejecutar:
        log("Nada modificado. Repite con --ejecutar para aplicar.")
    return 1 if any(r["estado"].startswith("error") for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
