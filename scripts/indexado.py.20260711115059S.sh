cat > src/indexado.py << 'PYEOF'
"""
indexado.py - Genera embeddings de los chunks y los persiste en ChromaDB.

Entrada: data/processed/chunks.jsonl
Salida:  chroma_db/ (colección 'amafe', persistente en disco)

Modelo: paraphrase-multilingual-MiniLM-L12-v2 (multilingüe ES/EN, CPU-friendly).
La primera ejecución descarga el modelo (~470 MB) a la caché de Hugging Face.
"""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path("data/processed/chunks.jsonl")
DB_PATH = "chroma_db"
COLLECTION = "amafe"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH = 64


def load_chunks(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    chunks = load_chunks(CHUNKS_PATH)
    print(f"Chunks cargados: {len(chunks)}")

    print(f"Cargando modelo de embeddings: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    client = chromadb.PersistentClient(path=DB_PATH)
    # Índice reproducible: se borra y regenera entero desde chunks.jsonl
    try:
        client.delete_collection(COLLECTION)
        print(f"Colección '{COLLECTION}' previa eliminada (regeneración limpia).")
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [c["texto"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        collection.add(
            ids=[c["chunk_id"] for c in batch],
            embeddings=embeddings.tolist(),
            documents=texts,
            # Chroma no admite None en metadatos: se omiten claves vacías
            metadatas=[
                {k: v for k, v in {
                    "titulo": c["titulo"],
                    "url": c["url"],
                    "tipo_fuente": c["tipo_fuente"],
                    "idioma": c["idioma"],
                    "fecha": c["fecha"],
                    "slug": c["slug"],
                }.items() if v is not None}
                for c in batch
            ],
        )
        print(f"  Indexados {min(i + BATCH, len(chunks))}/{len(chunks)}")

    print("\n--- Verificación ---")
    print(f"Vectores en la colección: {collection.count()} (esperados: {len(chunks)})")
    print(f"Base persistida en: {DB_PATH}/")


if __name__ == "__main__":
    main()
PYEOF