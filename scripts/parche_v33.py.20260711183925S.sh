cat > scripts/parche_v33.$(sella).py << 'PYEOF'
"""Parche v3.3: revertir max_seq_length=256 -> 128 (defecto).
Medido con 3 preguntas de la demo: la config v3 (128, sin titulo) gana
en 2/3. Ver tabla comparativa en docs/decisiones.md."""
from pathlib import Path

src = Path("src/indexado.py")
code = src.read_text(encoding="utf-8")
old = '''    # v3.2: MiniLM trunca a 128 tokens por defecto (~450 chars); se amplía a
    # 256 para que el chunk tipico de ~800 chars sea visible casi entero.
    model.max_seq_length = 256
'''
assert old in code, "ancla indexado no encontrada"
code = code.replace(old, "")
src.write_text(code, encoding="utf-8")
print("indexado.py -> v3.3 (max_seq_length por defecto, 128)")

src = Path("src/busqueda.py")
code = src.read_text(encoding="utf-8")
old = '\n        _model.max_seq_length = 256  # v3.2: simétrico con indexado'
assert old in code, "ancla busqueda no encontrada"
code = code.replace(old, "")
src.write_text(code, encoding="utf-8")
print("busqueda.py -> v3.3 (max_seq_length por defecto, 128)")
PYEOF
uv run python scripts/parche_v33.*.py

run uv run python -u src/indexado.py 2>&1 | tee logs/indexado_v33.$(sella).log
uv run python -u src/busqueda.py "¿Cómo puedo pedir cita?"