"""Parche v3.1: bug en_gb + chunks mínimos (ingesta) + embeber titulo (indexado)."""
from pathlib import Path

# --- 1 y 2: src/ingesta.py ---
src = Path("src/ingesta.py")
code = src.read_text(encoding="utf-8")

# 1. Bug: la portada inglesa tiene slug exactamente "en_gb" (sin guion bajo final)
old = '"lang": "en" if slug.startswith("en_gb_") else "es",'
new = '"lang": "en" if (slug == "en_gb" or slug.startswith("en_gb_")) else "es",'
assert old in code, "ancla lang no encontrada"
code = code.replace(old, new)

# 2. Descartar chunks minúsculos (restos de limpieza sin valor semántico)
old = 'BOILERPLATE_THRESHOLD = 0.40  # línea en >40% de páginas del mismo idioma = menú/pie'
new = old + '\nMIN_CHUNK_CHARS = 50     # v3.1: chunks más cortos se descartan (ruido)'
assert old in code, "ancla threshold no encontrada"
code = code.replace(old, new)

old = '        for i, chunk in enumerate(chunk_by_paragraphs(cleaned)):'
new = '''        trozos = [t for t in chunk_by_paragraphs(cleaned) if len(t) >= MIN_CHUNK_CHARS]
        for i, chunk in enumerate(trozos):'''
assert old in code, "ancla bucle chunks no encontrada"
code = code.replace(old, new)

code = code.replace("ingesta.py v3 -", "ingesta.py v3.1 -")
src.write_text(code, encoding="utf-8")
print("ingesta.py -> v3.1")

# --- 3: src/indexado.py ---
src = Path("src/indexado.py")
code = src.read_text(encoding="utf-8")

old = '''        texts = [c["texto"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)'''
new = '''        texts = [c["texto"] for c in batch]
        # v2: se embebe "titulo + texto" para que cada chunk herede la
        # semántica de su página; en documents se guarda solo el texto
        embed_texts = [f"{c['titulo']}\\n\\n{c['texto']}" for c in batch]
        embeddings = model.encode(embed_texts, show_progress_bar=False, normalize_embeddings=True)'''
assert old in code, "ancla encode no encontrada"
code = code.replace(old, new)

src.write_text(code, encoding="utf-8")
print("indexado.py -> v2 (embedding titulo+texto)")
