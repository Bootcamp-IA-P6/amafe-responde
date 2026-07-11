"""
ingesta.py v3 - Extrae, limpia y trocea las páginas web del corpus AMAFE.

Novedades v2 (decisión JJ 20260711):
- Filtrado estadístico de boilerplate: líneas presentes en >40% de las
  páginas del mismo idioma se consideran menú/pie y se eliminan.
- Eliminación de la cabecera de extracción (línea "- Extraido: ...").
- Chunking por párrafos: los cortes caen en límites de párrafo, con
  solapamiento de un párrafo entre chunks consecutivos.
"""

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CORPUS_PATH = Path(os.environ["CORPUS_PATH"])
MAPA_WEB_PATH = CORPUS_PATH.parent / "_B_.Estructuracion_MapaWeb_AMAFE_bilingue_20260708.20260708141606.md"
OUTPUT_PATH = Path("data/processed/chunks.jsonl")

CHUNK_SIZE = 1000        # tamaño objetivo por chunk (caracteres)
CHUNK_OVERLAP_PARAS = 1  # párrafos de solapamiento entre chunks
BOILERPLATE_THRESHOLD = 0.40  # línea en >40% de páginas del mismo idioma = menú/pie

EXCLUDED_SLUGS = {"newpagede8c1075"}  # borradores (mapa web, sección 17.4)

# Línea de metadatos inyectada por descarga_amafe.py (no es contenido de la web)
EXTRAIDO_RE = re.compile(r"^\s*-\s*Extraido:\s*\d{4}-\d{2}-\d{2}")

# v3: enlaces markdown -> solo el texto visible (las URLs CDN firmadas
# contaminaban los embeddings; la URL de la página vive en los metadatos)
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def strip_markdown_links(text: str) -> str:
    text = MD_IMAGE_RE.sub(r"\1", text)
    for _ in range(3):  # enlaces anidados en varias pasadas
        new = MD_LINK_RE.sub(r"\1", text)
        if new == text:
            break
        text = new
    return text

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
    return strip_markdown_links(md_path.read_text(encoding="utf-8", errors="replace"))


def detect_boilerplate(texts_by_lang: dict[str, list[str]]) -> dict[str, set[str]]:
    """Líneas (normalizadas) presentes en >threshold de páginas del mismo idioma."""
    boilerplate: dict[str, set[str]] = {}
    for lang, texts in texts_by_lang.items():
        counter: Counter[str] = Counter()
        for text in texts:
            unique_lines = {ln.strip() for ln in text.splitlines() if ln.strip()}
            counter.update(unique_lines)
        threshold = len(texts) * BOILERPLATE_THRESHOLD
        boilerplate[lang] = {ln for ln, n in counter.items() if n > threshold}
    return boilerplate


def clean_text(text: str, boilerplate: set[str]) -> str:
    """Elimina líneas de boilerplate y metadatos de extracción."""
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if stripped in boilerplate:
            continue
        if EXTRAIDO_RE.match(stripped):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)  # colapsar huecos
    return cleaned.strip()


def chunk_by_paragraphs(text: str, size: int = CHUNK_SIZE,
                        overlap_paras: int = CHUNK_OVERLAP_PARAS) -> list[str]:
    """Agrupa párrafos hasta ~size caracteres; solapa overlap_paras entre chunks."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paras:
        para_len = len(para) + 2
        if current and current_len + para_len > size:
            chunks.append("\n\n".join(current))
            current = current[-overlap_paras:] if overlap_paras else []
            current_len = sum(len(p) + 2 for p in current)
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
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

    # --- Pasada 1: cargar textos y detectar boilerplate por idioma ---
    pages: list[tuple[str, dict, str]] = []
    texts_by_lang: dict[str, list[str]] = {}
    stats = Counter()

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
        pages.append((slug, meta, text))
        texts_by_lang.setdefault(meta["lang"], []).append(text)

    boilerplate = detect_boilerplate(texts_by_lang)
    for lang, lines in sorted(boilerplate.items()):
        print(f"Boilerplate [{lang}]: {len(lines)} líneas repetidas "
              f"en >{BOILERPLATE_THRESHOLD:.0%} de {len(texts_by_lang[lang])} páginas")

    # --- Pasada 2: limpiar, deduplicar y trocear ---
    seen_hashes: dict[str, str] = {}
    chunks_out = []
    empty_after_clean = []

    for slug, meta, text in pages:
        cleaned = clean_text(text, boilerplate[meta["lang"]])
        if not cleaned:
            stats["vacias_tras_limpieza"] += 1
            empty_after_clean.append(slug)
            continue
        content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            stats["duplicadas_por_contenido"] += 1
            print(f"  [dedup] {slug}: contenido idéntico a '{seen_hashes[content_hash]}', se omite")
            continue
        seen_hashes[content_hash] = slug

        for i, chunk in enumerate(chunk_by_paragraphs(cleaned)):
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

    if empty_after_clean:
        print(f"  [aviso] páginas vacías tras limpieza: {', '.join(empty_after_clean)}")

    sizes = [len(c["texto"]) for c in chunks_out]
    print("\n--- Resumen ---")
    for k, v in sorted(stats.items()):
        print(f"{k}: {v}")
    print(f"Chunks totales: {len(chunks_out)}")
    if sizes:
        print(f"Tamaño de chunk (caracteres): min={min(sizes)} "
              f"medio={sum(sizes)//len(sizes)} max={max(sizes)}")
    print(f"Salida: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
