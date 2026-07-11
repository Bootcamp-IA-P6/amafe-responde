cat > src/ingesta.py << 'PYEOF'
"""
ingesta.py - Extrae y trocea las páginas web del corpus AMAFE en chunks con metadatos.

Fuente de metadatos: mapa web bilingüe (_B_.Estructuracion_MapaWeb_AMAFE_bilingue_*.md)
Fuente de contenido: <CORPUS_PATH>/<slug>/<slug>.md

Salida: data/processed/chunks.jsonl
"""

import hashlib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CORPUS_PATH = Path(os.environ["CORPUS_PATH"])
MAPA_WEB_PATH = CORPUS_PATH.parent / "_B_.Estructuracion_MapaWeb_AMAFE_bilingue_20260708.20260708141606.md"
OUTPUT_PATH = Path("data/processed/chunks.jsonl")

# Chunking: valores de partida, se ajustan en la Semana 2 con preguntas reales
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Páginas borrador detectadas en la sección 17 del mapa: accesibles pero sin
# contenido real (JJ, decisión confirmada 20260711)
EXCLUDED_SLUGS = {"newpagede8c1075"}

SLUG_TITLE_RE = re.compile(
    r"^\d[\d.]*\.{2,}\s*/(?P<slug>\S+?)\s+—\s+(?P<title>.+?)"
    r"(?:\s*\[\d+\s*documentos?\])?(?:\s*⚠)?\s*$"
)
URL_RE = re.compile(r"^\d[\d.]*\.{2,}\s*URL:\s*(?P<url>\S+)\s*$")


def parse_mapa_web(path: Path) -> dict[str, dict]:
    """Devuelve {slug: {title, url, lang}} a partir del mapa web bilingüe."""
    pages: dict[str, dict] = {}
    current_slug = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = SLUG_TITLE_RE.match(line)
        if m:
            slug = m.group("slug")
            pages[slug] = {
                "title": m.group("title").strip(),
                "url": None,
                "lang": "en" if slug.startswith("en_gb_") else "es",
            }
            current_slug = slug
            continue
        m = URL_RE.match(line)
        if m and current_slug and pages[current_slug]["url"] is None:
            pages[current_slug]["url"] = m.group("url")
    return pages


def load_page_text(slug_dir: Path) -> str | None:
    md_path = slug_dir / f"{slug_dir.name}.md"
    if not md_path.exists():
        return None
    return md_path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def main() -> None:
    print(f"Corpus: {CORPUS_PATH}")
    print(f"Mapa web: {MAPA_WEB_PATH}")
    if not MAPA_WEB_PATH.exists():
        raise SystemExit(f"ERROR: no encuentro el mapa web en {MAPA_WEB_PATH}")
    if not CORPUS_PATH.exists():
        raise SystemExit(f"ERROR: no encuentro el corpus en {CORPUS_PATH}")

    pages_meta = parse_mapa_web(MAPA_WEB_PATH)
    print(f"Páginas en el mapa: {len(pages_meta)}")

    seen_hashes: dict[str, str] = {}
    chunks_out = []
    stats = {
        "procesadas": 0,
        "sin_md": 0,
        "sin_en_mapa": 0,
        "excluidas_borrador": 0,
        "duplicadas_por_contenido": 0,
    }

    for slug_dir in sorted(p for p in CORPUS_PATH.iterdir() if p.is_dir()):
        slug = slug_dir.name

        if slug in EXCLUDED_SLUGS:
            stats["excluidas_borrador"] += 1
            print(f"  [excluida] {slug}: página borrador")
            continue

        meta = pages_meta.get(slug)
        if meta is None:
            stats["sin_en_mapa"] += 1
            print(f"  [aviso] {slug}: no aparece en el mapa web, se omite")
            continue

        text = load_page_text(slug_dir)
        if text is None:
            stats["sin_md"] += 1
            print(f"  [aviso] {slug}: sin fichero .md, se omite")
            continue

        content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            stats["duplicadas_por_contenido"] += 1
            print(f"  [dedup] {slug}: contenido idéntico a '{seen_hashes[content_hash]}', se omite")
            continue
        seen_hashes[content_hash] = slug

        for i, chunk in enumerate(chunk_text(text)):
            chunks_out.append({
                "chunk_id": f"{slug}__{i:03d}",
                "texto": chunk,
                "titulo": meta["title"],
                "url": meta["url"],
                "tipo_fuente": "web",
                "idioma": meta["lang"],
                "fecha": None,
                "slug": slug,
            })
        stats["procesadas"] += 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for c in chunks_out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("\n--- Resumen ---")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(f"Chunks totales: {len(chunks_out)}")
    print(f"Salida: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
PYEOF