# -*- coding: utf-8 -*-
"""
inventario_pdf.py - v1.1 (20260713)
AMAFE Responde - Diagnóstico de SOLO LECTURA de los PDFs del corpus.

No modifica nada: recorre CORPUS_PATH recursivamente, analiza cada PDF y
genera un CSV + resumen en consola para decidir el alcance de ingesta_pdf.py.

Por cada PDF reporta:
- ruta relativa, slug (carpeta), tamaño, nº de páginas
- caracteres extraíbles y media por página
- clasificación DIGITAL / ESCANEADO / MIXTO (heurística chars/página)
- categoría por nombre: memoria / auditoria / boletin / REVISAR_SENSIBLE / otro
- SHA-256 para detectar duplicados entre slugs (misma descarga en 2 carpetas)

Uso (desde la raíz del proyecto):
    uv run python src/inventario_pdf.py --csv "logs/inventario_pdf_$(sella).csv"
    uv run python src/inventario_pdf.py --raiz "D:/otra/ruta" --csv salida.csv
"""

import argparse
import csv
import hashlib
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf  # import moderno (el alias clásico 'fitz' está deprecado)
from dotenv import load_dotenv

load_dotenv()

# Umbral de la heurística digital/escaneado (caracteres extraíbles por página)
CHARS_PAG_ESCANEADO = 30    # por debajo: página sin capa de texto
CHARS_PAG_DIGITAL = 200     # por encima de media: claramente digital

# Patrones de categoría sobre el nombre normalizado (minúsculas, sin tildes)
CATEGORIAS = [
    ("REVISAR_SENSIBLE", ("acta", "delegacion", "voto", "candidat", "asamblea")),
    ("memoria", ("memoria",)),
    ("auditoria", ("auditor", "cuentas")),  # v1.1: 'cuentas' captura la serie Informe_y_cuentas_2015-2021 y Cuentas_auditadas_2022 (medido en tree 20260713)
    ("boletin", ("despertando", "boletin")),
]


def normalizar(texto: str) -> str:
    """minúsculas y sin tildes, para clasificar nombres de archivo."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def categoria_por_nombre(nombre: str) -> str:
    nombre_n = normalizar(nombre)
    for cat, patrones in CATEGORIAS:
        if any(p in nombre_n for p in patrones):
            return cat
    return "otro"


def analizar_pdf(ruta: Path) -> dict:
    """Analiza un PDF. Solo lectura. Devuelve dict con métricas o error."""
    info = {
        "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest(),
        "bytes": ruta.stat().st_size,
        "paginas": None,
        "chars_total": None,
        "chars_por_pagina": None,
        "paginas_sin_texto": None,
        "tipo": "ERROR",
        "error": "",
    }
    try:
        with pymupdf.open(ruta) as doc:
            info["paginas"] = doc.page_count
            chars_por_pag = [len(p.get_text().strip()) for p in doc]
        total = sum(chars_por_pag)
        n = max(len(chars_por_pag), 1)
        sin_texto = sum(1 for c in chars_por_pag if c < CHARS_PAG_ESCANEADO)
        media = total / n
        info.update({
            "chars_total": total,
            "chars_por_pagina": round(media),
            "paginas_sin_texto": sin_texto,
        })
        if sin_texto == n:
            info["tipo"] = "ESCANEADO"
        elif media >= CHARS_PAG_DIGITAL and sin_texto == 0:
            info["tipo"] = "DIGITAL"
        elif sin_texto == 0:
            info["tipo"] = "DIGITAL_POCO_TEXTO"
        else:
            info["tipo"] = "MIXTO"
    except Exception as e:  # PDF corrupto, cifrado, etc.: reportar y seguir
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def main() -> int:
    raiz_defecto = os.getenv("CORPUS_PATH")
    parser = argparse.ArgumentParser(
        description="Inventario de solo lectura de los PDFs del corpus AMAFE")
    parser.add_argument("--raiz", default=raiz_defecto,
                        help="Directorio a escanear (defecto: CORPUS_PATH del .env)")
    parser.add_argument("--csv", required=True,
                        help="Ruta del CSV de salida (usar $(sella) para el sello)")
    args = parser.parse_args()

    if not args.raiz:
        print("ERROR: sin --raiz y sin CORPUS_PATH en .env", file=sys.stderr)
        return 1
    raiz = Path(args.raiz)
    if not raiz.is_dir():
        print(f"ERROR: no existe el directorio {raiz}", file=sys.stderr)
        return 1

    pdfs = sorted(raiz.rglob("*.pdf"))
    print(f"Raíz: {raiz}")
    print(f"PDFs encontrados: {len(pdfs)}\n")

    filas = []
    por_hash: dict[str, list[str]] = defaultdict(list)
    for ruta in pdfs:
        rel = ruta.relative_to(raiz)
        info = analizar_pdf(ruta)
        fila = {
            "ruta": str(rel),
            "slug": rel.parts[0] if len(rel.parts) > 1 else "",
            "nombre": ruta.name,
            "categoria": categoria_por_nombre(ruta.name),
            **info,
        }
        filas.append(fila)
        por_hash[info["sha256"]].append(str(rel))
        print(f"  [{fila['tipo']:>18}] {fila['categoria']:>16}  "
              f"{fila['paginas'] if fila['paginas'] is not None else '?':>4} pág  "
              f"{rel}")

    # Marcar duplicados (mismo contenido en varias rutas)
    for fila in filas:
        rutas = por_hash[fila["sha256"]]
        fila["n_copias"] = len(rutas)
        fila["duplicado_de"] = rutas[0] if len(rutas) > 1 and str(fila["ruta"]) != rutas[0] else ""

    # CSV
    salida = Path(args.csv)
    salida.parent.mkdir(parents=True, exist_ok=True)
    campos = ["ruta", "slug", "nombre", "categoria", "tipo", "paginas",
              "chars_total", "chars_por_pagina", "paginas_sin_texto",
              "bytes", "n_copias", "duplicado_de", "sha256", "error"]
    with salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)

    # Resumen
    unicos = {f["sha256"]: f for f in filas}.values()
    print("\n--- Resumen (sobre contenidos ÚNICOS tras dedup) ---")
    print(f"PDFs: {len(filas)} en disco, {len(unicos)} únicos, "
          f"{len(filas) - len(unicos)} copias duplicadas")
    for etiqueta, clave in (("Por tipo", "tipo"), ("Por categoría", "categoria")):
        cuenta = Counter(f[clave] for f in unicos)
        print(f"{etiqueta}: " + ", ".join(f"{k}={v}" for k, v in cuenta.most_common()))
    pag_ocr = sum(f["paginas_sin_texto"] or 0 for f in unicos)
    print(f"Páginas que requerirían OCR (sin capa de texto): {pag_ocr}")
    sensibles = [f["ruta"] for f in unicos if f["categoria"] == "REVISAR_SENSIBLE"]
    if sensibles:
        print(f"⚠ REVISAR_SENSIBLE ({len(sensibles)}): NO ingerir sin revisión manual:")
        for r in sensibles:
            print(f"    {r}")
    errores = [f for f in filas if f["error"]]
    if errores:
        print(f"⚠ Errores de lectura ({len(errores)}):")
        for f in errores:
            print(f"    {f['ruta']}: {f['error']}")
    print(f"\nCSV: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
