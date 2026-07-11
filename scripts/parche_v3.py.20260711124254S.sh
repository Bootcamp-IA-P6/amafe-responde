cat > scripts/parche_v3.$(sella).py << 'PYEOF'
"""Parche v2->v3 de src/ingesta.py: enlaces markdown a texto plano."""
from pathlib import Path

src = Path("src/ingesta.py")
code = src.read_text(encoding="utf-8")

# 1. Nueva constante y función tras EXTRAIDO_RE
anchor = 'EXTRAIDO_RE = re.compile(r"^\\s*-\\s*Extraido:\\s*\\d{4}-\\d{2}-\\d{2}")'
addition = anchor + '''

# v3: enlaces markdown -> solo el texto visible (las URLs CDN firmadas
# contaminaban los embeddings; la URL de la página vive en los metadatos)
MD_IMAGE_RE = re.compile(r"!\\[([^\\]]*)\\]\\([^)]*\\)")
MD_LINK_RE = re.compile(r"\\[([^\\]]*)\\]\\([^)]*\\)")


def strip_markdown_links(text: str) -> str:
    text = MD_IMAGE_RE.sub(r"\\1", text)
    for _ in range(3):  # enlaces anidados en varias pasadas
        new = MD_LINK_RE.sub(r"\\1", text)
        if new == text:
            break
        text = new
    return text'''
assert anchor in code, "ancla EXTRAIDO_RE no encontrada"
code = code.replace(anchor, addition)

# 2. Aplicar el strip al cargar cada página (antes de detectar boilerplate,
#    para que las líneas de menú queden idénticas entre páginas)
old = 'return md_path.read_text(encoding="utf-8", errors="replace")'
new = 'return strip_markdown_links(md_path.read_text(encoding="utf-8", errors="replace"))'
assert old in code, "ancla load_page_text no encontrada"
code = code.replace(old, new)

# 3. Actualizar el docstring de versión
code = code.replace("ingesta.py v2 -", "ingesta.py v3 -")

src.write_text(code, encoding="utf-8")
print("Parche v3 aplicado sobre src/ingesta.py")
PYEOF
uv run python scripts/parche_v3.*.py
