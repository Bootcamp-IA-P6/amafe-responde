cat > scripts/parche_v32.$(sella).py << 'PYEOF'
"""Parche v3.2: revertir embedding titulo+texto; max_seq_length 128->256."""
from pathlib import Path

# --- src/indexado.py: revertir titulo+texto ---
src = Path("src/indexado.py")
code = src.read_text(encoding="utf-8")

old = '''        texts = [c["texto"] for c in batch]
        # v2: se embebe "titulo + texto" para que cada chunk herede la
        # semántica de su página; en documents se guarda solo el texto
        embed_texts = [f"{c['titulo']}\\n\\n{c['texto']}" for c in batch]
        embeddings = model.encode(embed_texts, show_progress_bar=False, normalize_embeddings=True)'''
new = '''        texts = [c["texto"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)'''
assert old in code, "ancla embed_texts no encontrada"
code = code.replace(old, new)

old = '    model = SentenceTransformer(MODEL_NAME, device="cpu")'
new = old + '''
    # v3.2: MiniLM trunca a 128 tokens por defecto (~450 chars); se amplía a
    # 256 para que el chunk tipico de ~800 chars sea visible casi entero.
    model.max_seq_length = 256'''
assert old in code, "ancla model indexado no encontrada"
code = code.replace(old, new)
src.write_text(code, encoding="utf-8")
print("indexado.py -> v3 (revertido titulo, max_seq_length=256)")

# --- src/busqueda.py: misma ventana, por simetría ---
src = Path("src/busqueda.py")
code = src.read_text(encoding="utf-8")

old = '        _model = SentenceTransformer(MODEL_NAME, device="cpu")'
new = old + '\n        _model.max_seq_length = 256  # v3.2: simétrico con indexado'
assert old in code, "ancla model busqueda no encontrada"
code = code.replace(old, new)
src.write_text(code, encoding="utf-8")
print("busqueda.py -> v3 (max_seq_length=256)")
PYEOF
uv run python scripts/parche_v32.*.py