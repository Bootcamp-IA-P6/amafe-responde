# AMAFE Responde

Asistente de consulta en lenguaje natural sobre la documentación pública de
[AMAFE](https://amafe.org) (Asociación Española de Apoyo en Psicosis),
construido con una arquitectura **RAG** (Retrieval-Augmented Generation).
Funciona con LLM en la nube (Groq) o íntegramente en local (Ollama) — el
código es idéntico en ambos modos.

🌐 **App en vivo**: https://amafe-responde.streamlit.app

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
dice en lugar de inventar — comportamiento verificado con una batería de
evaluación de 20 preguntas sobre 3 modelos (ver [Evaluación](#evaluación-m4)).

## Interfaz web

Aplicación Streamlit con patrón de chat (`app/app.py`):

- Historial visual de la conversación en la sesión, con las fuentes
  enlazadas y los fragmentos recuperados en expander por cada turno.
- Persistencia: cada consulta se registra en `logs/consultas_app.jsonl`
  (trazabilidad completa) y puede recargarse con *"Cargar historial
  anterior"*; *"Limpiar conversación"* vacía solo la vista, nunca el registro.
- Preguntas sugeridas para facilitar la demo (visibles con el historial vacío).
- Aviso explícito cuando el sistema no encuentra información suficiente.

```bash
uv run streamlit run app/app.py
```

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
`max_seq_length=128`, distancia coseno, `top_k=5`, 605 chunks (408 ES /
197 EN). Los experimentos que llevaron a esta configuración (y los que se
descartaron con datos) están documentados en
[`docs/decisiones.md`](docs/decisiones.md).

**Guardarraíles anti-alucinación (doble capa):**

1. **Umbral de distancia** (`UMBRAL_DISTANCIA=0.75`): si ningún chunk es
   suficientemente cercano a la pregunta, el LLM ni siquiera se invoca.
2. **Instrucciones de "no sé" en el prompt**: para los casos que superan el
   filtro pero cuyo contenido no responde realmente a la pregunta.

Validación con datos (M4, 60 generaciones): **0 alucinaciones**; la capa 2
resolvió correctamente los 6 casos de "no sé" y quedó documentada como
guardarraíl efectivo — la evidencia muestra que no existe umbral capaz de
separar preguntas fuera de corpus semánticamente cercanas (decisión U1a en
`docs/decisiones.md`, detalle en
[`eval/informe_evaluacion.md`](eval/informe_evaluacion.md)).

## Modelos de lenguaje

| Modo | Modelo | Notas |
|---|---|---|
| **Producción (Groq)** | `openai/gpt-oss-120b` | El mejor medido en la evaluación (19/20). Elegido tras comparativa de 3 modelos (decisión G3a). |
| Local (Ollama) | `qwen3:8b` | Funciona en CPU (32 GB RAM recomendados); usado en el desarrollo del MVP. |

> Nota: el modelo anterior (`llama-3.1-8b-instant`) queda deprecado por Groq
> el 16/08/2026; la migración a `openai/gpt-oss-120b` está hecha y medida.

## Evaluación (M4)

Batería de 20 preguntas reales (`eval/preguntas.jsonl`: 10 del briefing,
4 paráfrasis, 3 fuera de corpus, 2 sobre la debilidad conocida, 1 en inglés)
ejecutada con `eval/runner_bateria.py` sobre tres modelos con **recuperación
idéntica verificada** (la comparación aísla la generación):

| Modelo | Correctas | Duración |
|---|---|---|
| `llama-3.1-8b-instant` | 17/20 | 285,6 s |
| `openai/gpt-oss-20b` | 18/20 | 208,4 s |
| `openai/gpt-oss-120b` | **19/20** | 202,9 s |

El único fallo persistente en los tres (q12) es de recuperación, no de
generación, y degrada en seguro: el sistema calla honestamente en lugar de
inventar. Informe completo con análisis de errores:
[`eval/informe_evaluacion.md`](eval/informe_evaluacion.md). Las tres tandas
crudas (JSONL de trazabilidad) están en `eval/`.

## Requisitos

- Windows 11 con Git Bash / MSYS2 (probado), o Linux/macOS
- [Python 3.12](https://www.python.org/) gestionado con [`uv`](https://docs.astral.sh/uv/)
- Una clave API gratuita de [Groq](https://console.groq.com/) (modo
  producción) **o** [Ollama](https://ollama.com/) con `qwen3:8b` (modo local)
- Solo para regenerar el corpus: el corpus web de AMAFE descargado en local
  (fase previa del proyecto; ruta en `.env`)

## Instalación

```bash
git clone https://github.com/Bootcamp-IA-P6/amafe-responde.git
cd amafe-responde
uv sync
cp .env.example .env
# Editar .env: LLM_BASE_URL/LLM_MODEL/LLM_API_KEY (bloque Groq del ejemplo)
```

El índice ChromaDB (605 chunks, ~11 MB) **se incluye en el repositorio**:
no hace falta ejecutar ingesta ni indexado para usar la aplicación. Esos
pasos solo son necesarios si se regenera el corpus.

## Uso

```bash
# Aplicación web (chat con historial)
uv run streamlit run app/app.py

# Pipeline por módulos (solo para regenerar el corpus/índice)
uv run python src/ingesta.py
uv run python src/indexado.py

# Búsqueda semántica (sin LLM), con filtro de idioma opcional
uv run python src/busqueda.py "¿Cómo puedo pedir cita?" --idioma es

# Generación de respuesta completa, con salida JSON de trazabilidad
uv run python src/generacion.py "¿Qué es el Espacio Joven?" --json

# Batería de evaluación (M4)
uv run python eval/runner_bateria.py

# Pruebas (sin red: mocks del contrato real)
uv run python tests/test_app_m2b.py     # app Streamlit, 6 casos (AppTest)
uv run python tests/test_runner_m4.py   # runner de evaluación, 3 casos
```

El dict/JSON devuelto por `generacion.py` incluye: pregunta, chunks
recuperados con puntuaciones, prompt enviado, respuesta, fuentes citadas,
parámetros del modelo y timestamp — la trazabilidad completa de cada
consulta.

## Configuración (`.env`)

Las variables principales (ver `.env.example` anotado):

| Variable | Producción (Groq) | Local (Ollama) |
|---|---|---|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | `http://localhost:11434/v1` |
| `LLM_MODEL` | `openai/gpt-oss-120b` | `qwen3:8b` |
| `LLM_API_KEY` | clave de Groq | `ollama` |
| `LLM_TEMPERATURE` | `0.2` (experimento 0.0 vs 0.2) | ídem |
| `UMBRAL_DISTANCIA` | `0.75` (decisión U1a, con datos) | ídem |
| `TOP_K` | `5` | ídem |
| `CORPUS_PATH` | solo para regenerar el corpus | ídem |

Cambiar de un modo a otro solo requiere esas tres primeras variables — el
código es idéntico por diseño (decisión 1a).

## Estado del proyecto y hoja de ruta

Seguimiento público en el
[tablero Kanban](https://github.com/orgs/Bootcamp-IA-P6/projects/77) y mapa
de navegación en [`docs/URLS.md`](docs/URLS.md).

- [x] M1 — Repo público, licencia, decisiones documentadas, Kanban
- [x] M2 — Interfaz web con Streamlit ([#8](https://github.com/Bootcamp-IA-P6/amafe-responde/pull/8)) + historial y persistencia ([#11](https://github.com/Bootcamp-IA-P6/amafe-responde/pull/11))
- [x] M3 — Groq como LLM ([#9](https://github.com/Bootcamp-IA-P6/amafe-responde/pull/9))
- [x] M4 — Batería de 20 preguntas, comparativa de 3 modelos e informe de evaluación
- [x] M6a — Despliegue en Streamlit Community Cloud ([app en vivo](https://amafe-responde.streamlit.app), [#16](https://github.com/Bootcamp-IA-P6/amafe-responde/pull/16), [#17](https://github.com/Bootcamp-IA-P6/amafe-responde/pull/17))
- [ ] M5 — Docker ([#6](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/6))
- [ ] M6b — Despliegue dockerizado en otra plataforma ([#7](https://github.com/Bootcamp-IA-P6/amafe-responde/issues/7))

**Fase 2 (fuera del MVP):** incorporación de los PDFs institucionales
(memorias, boletines, auditorías) con estrategia de lista blanca, y OCR de
los documentos escaneados.

**Limitaciones conocidas (medidas en M4):** las preguntas sobre auditorías
obtienen resultados flojos porque esos documentos son PDFs escaneados fuera
del corpus web (previsto para fase 2); y la recuperación es sensible a la
formulación — alguna paráfrasis no recupera la página correcta (q12 del
informe). En ambos casos el guardarraíl responde "no sé" en lugar de
inventar.

## Principios de trabajo

- **Decisiones respaldadas por datos medidos** antes de implementar; todo
  registrado con ID y evidencia en [`docs/decisiones.md`](docs/decisiones.md).
- **Reproducibilidad**: scripts sellados con timestamp en `scripts/`, logs
  JSONL/CSV de cada experimento, pruebas con mocks del contrato real.
- **Privacidad por lista blanca**: solo entra en el corpus (y en este repo)
  información pública verificada; nunca datos personales.
- **Simplicidad primero**: sin funcionalidades especulativas.

## Licencia

[MIT](LICENSE) — Copyright (c) 2026 AMAFE Responde contributors.
