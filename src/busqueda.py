"""
busqueda.py - Búsqueda semántica sobre la colección ChromaDB del corpus AMAFE.

Uso:
    uv run python src/busqueda.py "¿Cómo puedo pedir cita?"
    uv run python src/busqueda.py "¿Qué es el Espacio Joven?" --top-k 8
"""

import argparse
import re

import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "chroma_db"
COLLECTION = "amafe"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5

_model = None  # caché del modelo para uso como módulo


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


ES_MARKERS = re.compile(r"[¿¡áéíóúñü]|\\b(qué|cómo|dónde|cuándo|quién|es|de|la|el|los|una?)\\b", re.I)


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
    res = col.query(query_embeddings=emb.tolist(), n_results=top_k, where=where)
    resultados = []
    for doc, meta, dist, cid in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0], res["ids"][0]
    ):
        resultados.append({
            "chunk_id": cid,
            "similitud": round(1 - dist, 4),  # distancia coseno -> similitud
            "texto": doc,
            **meta,
        })
    return resultados


def main() -> None:
    parser = argparse.ArgumentParser(description="Búsqueda semántica corpus AMAFE")
    parser.add_argument("pregunta", help="Pregunta en lenguaje natural")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--idioma", choices=["es", "en", "all"], default=None,
                        help="Forzar idioma (por defecto: autodetectar)")
    args = parser.parse_args()

    idioma = args.idioma or detectar_idioma(args.pregunta)
    print(f"Pregunta: {args.pregunta}  [idioma detectado: {idioma}]\n")
    for i, r in enumerate(buscar(args.pregunta, args.top_k, idioma), 1):
        print(f"[{i}] similitud={r['similitud']}  [{r['idioma']}]  {r['titulo']}")
        print(f"    {r['url']}  ({r['chunk_id']})")
        snippet = r["texto"][:220].replace("\n", " ")
        print(f"    {snippet}...\n")


if __name__ == "__main__":
    main()
