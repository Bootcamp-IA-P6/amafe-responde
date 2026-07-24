# Dockerfile — AMAFE Responde (M5)
# Imagen autocontenida: dependencias CPU + modelo de embeddings horneado
# (BLD1a) + índice ChromaDB del repo (IDX1a). Sin secretos: LLM_BASE_URL,
# LLM_MODEL y LLM_API_KEY se inyectan en runtime (--env-file o panel de la
# plataforma).
#
# Construir:  docker build -t amafe-responde .
# Ejecutar:   docker run --rm -p 8501:8501 --env-file .env amafe-responde

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HF_HOME=/app/.cache/huggingface

# 1. Dependencias primero (capa cacheable): el requirements CPU de M6a
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Hornear el modelo de embeddings en la imagen (BLD1a):
#    arranques rápidos y sin dependencia de red en runtime
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# Con el modelo ya en la imagen, el runtime no necesita tocar Hugging Face
ENV HF_HUB_OFFLINE=1

# 3. La aplicación: solo lo necesario para servir (COPY selectivo)
COPY src/ src/
COPY app/ app/
COPY chroma_db/ chroma_db/

# 4. Usuario sin privilegios con UID 1000 (requisito recomendado de
#    Hugging Face Spaces) y logs/ escribible para consultas_app.jsonl
RUN useradd -m -u 1000 usuario \
    && mkdir -p /app/logs \
    && chown -R usuario:usuario /app
USER usuario
ENV HOME=/home/usuario

EXPOSE 8501

CMD ["streamlit", "run", "app/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--server.fileWatcherType=none"]
