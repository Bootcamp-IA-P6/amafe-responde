"""Parche v1->v2 de src/busqueda.py: filtro por idioma de la pregunta."""
from pathlib import Path

src = Path("src/busqueda.py")
code = src.read_text(encoding="utf-8")

old_buscar = '''def buscar(pregunta: str, top_k: int = TOP_K) -> list[dict]:
    """Devuelve los top_k chunks más relevantes con sus metadatos y puntuación."""
    emb = get_model().encode([pregunta], normalize_embeddings=True)
    col = chromadb.PersistentClient(path=DB_PATH).get_collection(COLLECTION)
    res = col.query(query_embeddings=emb.tolist(), n_results=top_k)'''
new_buscar = '''ES_MARKERS = re.compile(r"[¿¡áéíóúñü]|\\\\b(qué|cómo|dónde|cuándo|quién|es|de|la|el|los|una?)\\\\b", re.I)


def detectar_idioma(pregunta: str) -> str:
    """Heurística mínima: marcadores de español; en su ausencia, inglés."""
    return "es" if ES_MARKERS.search(pregunta) else "en"


def buscar(pregunta: str, top_k: int = TOP_K, idioma: str | None = None) -> list[dict]:
    """Top_k chunks más relevantes. idioma: 'es', 'en', 'all' o None (autodetectar)."""
    if idioma is None:
        idioma = detectar_idioma(pregunta)
    emb = get_model().encode([pregunta], normalize_embeddings=True)
    col = chromadb.PersistentClient(path=DB_PATH).get_collection(COLLECTION)
    where = None if idioma == "all" else {"idioma": idioma}
    res = col.query(query_embeddings=emb.tolist(), n_results=top_k, where=where)'''
assert old_buscar in code, "ancla buscar() no encontrada"
code = code.replace(old_buscar, new_buscar)

old_import = "import argparse"
code = code.replace(old_import, "import argparse\nimport re", 1)

old_main = '''    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    print(f"Pregunta: {args.pregunta}\\n")
    for i, r in enumerate(buscar(args.pregunta, args.top_k), 1):'''
new_main = '''    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--idioma", choices=["es", "en", "all"], default=None,
                        help="Forzar idioma (por defecto: autodetectar)")
    args = parser.parse_args()

    idioma = args.idioma or detectar_idioma(args.pregunta)
    print(f"Pregunta: {args.pregunta}  [idioma detectado: {idioma}]\\n")
    for i, r in enumerate(buscar(args.pregunta, args.top_k, idioma), 1):'''
assert old_main in code, "ancla main() no encontrada"
code = code.replace(old_main, new_main)

src.write_text(code, encoding="utf-8")
print("Parche v2 aplicado sobre src/busqueda.py")
