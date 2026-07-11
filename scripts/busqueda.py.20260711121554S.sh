cat > src/busqueda.py << 'PYEOF'
"""
busqueda.py - Búsqueda semántica sobre la colección ChromaDB del corpus AMAFE.

Uso:
    uv run python src/busqueda.py "¿Cómo puedo pedir cita?"
    uv run python src/busqueda.py "¿Qué es el Espacio Joven?" --top-k 8
"""

import argparse

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


def buscar(pregunta: str, top_k: int = TOP_K) -> list[dict]:
    """Devuelve los top_k chunks más relevantes con sus metadatos y puntuación."""
    emb = get_model().encode([pregunta], normalize_embeddings=True)
    col = chromadb.PersistentClient(path=DB_PATH).get_collection(COLLECTION)
    res = col.query(query_embeddings=emb.tolist(), n_results=top_k)
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
    args = parser.parse_args()

    print(f"Pregunta: {args.pregunta}\n")
    for i, r in enumerate(buscar(args.pregunta, args.top_k), 1):
        print(f"[{i}] similitud={r['similitud']}  [{r['idioma']}]  {r['titulo']}")
        print(f"    {r['url']}  ({r['chunk_id']})")
        snippet = r["texto"][:220].replace("\n", " ")
        print(f"    {snippet}...\n")


if __name__ == "__main__":
    main()
PYEOF