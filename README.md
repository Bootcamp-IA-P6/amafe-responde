# AMAFE Responde

Asistente de consulta en lenguaje natural sobre la documentación pública de
[AMAFE](https://amafe.org) (Asociación Española de Apoyo en Psicosis),
construido con una arquitectura **RAG** (Retrieval-Augmented Generation)
que funciona íntegramente en local.

> ⚠️ **Aviso**: este es un proyecto formativo (proyecto final del Bootcamp de
> IA de Factoría F5) y **no es una herramienta oficial de AMAFE**. Utiliza
> únicamente información ya pública de la web de la asociación. Las respuestas
> las genera un modelo de lenguaje y pueden contener errores: contrasta
> siempre con las fuentes citadas.

## Qué hace

Permite hacer preguntas como *"¿Cómo puedo pedir cita?"* o *"¿Qué es el
Espacio Joven?"* y obtener respuestas generadas **exclusivamente a partir del
corpus público de AMAFE**, con las fuentes citadas y trazabilidad completa de
cada consulta. Si la documentación no contiene la respuesta, el sistema lo
dice en lugar de inventar.

## Arquitectura

Pipeline de cuatro módulos en `src/`, cada uno ejecutable y probado por
separado:

| Módulo | Función |
|---|---|
| `ingesta.py` | Web pública de AMAFE → chunks con metadatos (`data/processed/chunks.jsonl`). Chunking por párrafos, filtrado estadístico de boilerplate, deduplicación SHA-256, etiquetado bilingüe ES/EN. |
| `indexado.py` | Chunks → base vectorial ChromaDB persistente (colección `amafe`). |
| `busqueda.py` | Pregunta → top-k chunks más relevantes, con autodetección de idioma y filtro opcional. |
| `generacion.py` | Chunks recuperados → respuesta en lenguaje natural vía LLM, con citas, guardarraíles anti-alucinación y dict de trazabilidad completo. |

**Configuración de recuperación (v3, congelada por experimentos medidos):**
embeddings `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers),
`max_seq_length=128`, distancia coseno, `top_k=5`, 605 chunks. Los
experimentos que llevaron a esta configuración (y los que se descartaron con
datos) están documentados en [`docs/decisiones.md`](docs/decisiones.md).

**Guardarraíles anti-alucinación (doble capa):**

1. **Umbral de distancia** (`UMBRAL_DISTANCIA=0.75`, calibrado con datos
   reales): si ningún chunk es suficientemente cercano a la pregunta, el LLM
   ni siquiera se invoca.
2. **Instrucciones de "no sé" en el prompt**: para los casos grises que
   superan el filtro pero cuyo contenido no responde realmente a la pregunta.

Ambas capas están validadas experimentalmente (ver
`eval/comparativa_temp_20260713110201L.limpio.jsonl` y las entradas U1 y
T-FINAL-a de `docs/decisiones.md`).

## Requisitos

- Windows 11 con Git Bash / MSYS2 (probado), o Linux/macOS
- [Python 3.12](https://www.python.org/) gestionado con [`uv`](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) con el modelo `qwen3:8b` (funciona en CPU;
  32 GB de RAM recomendados)
- Corpus web de AMAFE descargado en local (fase previa del proyecto; la ruta
  se configura en `.env`)

## Instalación

```bash
git clone https://github.com/Bootcamp-IA-P6/amafe-responde.git
cd amafe-responde
uv sync
cp .env.example .env
# Editar .env: al menos CORPUS_PATH con la ruta local del corpus descargado
ollama pull qwen3:8b
```

## Uso

```bash
# 1. Ingesta: web → chunks.jsonl
uv run python src/ingesta.py

# 2. Indexado: chunks → ChromaDB persistente
uv run python src/indexado.py

# 3. Búsqueda semántica (sin LLM), con filtro de idioma opcional
uv run python src/busqueda.py "¿Cómo puedo pedir cita?" --idioma es

# 4. Generación de respuesta completa, con salida JSON de trazabilidad
uv run python src/generacion.py "¿Qué es el Espacio Joven?" --json
```

El dict/JSON devuelto por `generacion.py` incluye: pregunta, chunks
recuperados con puntuaciones, prompt enviado, respuesta, fuentes citadas,
parámetros del modelo y timestamp — la trazabilidad completa de cada
consulta.

## Configuración (`.env`)

Las variables principales (ver `.env.example` anotado):

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `CORPUS_PATH` | — | Ruta local del corpus web descargado |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Endpoint OpenAI-compatible (Ollama en fase 1; Groq en fase 2) |
| `LLM_MODEL` | `qwen3:8b` | Modelo generativo |
| `LLM_TEMPERATURE` | `0.2` | Elegida tras experimento 0.0 vs 0.2 |
| `UMBRAL_DISTANCIA` | `0.75` | Guardarraíl capa 1, calibrado con datos reales |
| `TOP_K` | `5` | Chunks recuperados por consulta |

Cambiar de Ollama a Groq (fase 2) solo requiere modificar `LLM_BASE_URL`,
`LLM_MODEL` y `LLM_API_KEY` — el código es idéntico por diseño (decisión 1a).

## Estado del proyecto y hoja de ruta

MVP en desarrollo sobre el corpus web (605 chunks). Seguimiento público en el
[tablero Kanban](https://github.com/orgs/Bootcamp-IA-P6/projects/77).

- [x] M1 — Repo público, licencia, decisiones documentadas, Kanban
- [ ] M2 — Interfaz web con Streamlit ([#2](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/2))
- [ ] M3 — Groq como LLM ([#3](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/3))
- [ ] M4 — Batería de 20 preguntas + informe de evaluación ([#4](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/4), [#5](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/5))
- [ ] M5 — Docker ([#6](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/6))
- [ ] M6 — Despliegue ([#7](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/7))

**Fase 2 (fuera del MVP):** incorporación de los PDFs institucionales
(memorias, boletines, auditorías) con estrategia de lista blanca, y OCR de
los documentos escaneados.

**Limitación conocida:** las preguntas sobre auditorías obtienen resultados
flojos en el MVP, porque los documentos de auditoría son PDFs escaneados que
quedan fuera del corpus web actual. Está documentado y previsto para fase 2 —
el guardarraíl de "no sé" gestiona el caso correctamente.

## Principios de trabajo

- **Decisiones respaldadas por datos medidos** antes de implementar; todo
  registrado con ID y evidencia en [`docs/decisiones.md`](docs/decisiones.md).
- **Reproducibilidad**: scripts sellados con timestamp en `scripts/`, logs
  JSONL/CSV de cada experimento.
- **Privacidad por lista blanca**: solo entra en el corpus (y en este repo)
  información pública verificada; nunca datos personales.
- **Simplicidad primero**: sin funcionalidades especulativas.

## Licencia

[MIT](LICENSE) — Copyright (c) 2026 AMAFE Responde contributors.
