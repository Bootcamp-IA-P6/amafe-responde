# Decisiones técnicas — AMAFE Responde

Registro de decisiones empíricas y de diseño del pipeline RAG.
Convención: cada entrada indica fecha, decisión, evidencia y estado.

---

## 20260711 — Ingesta e indexado (config v3, congelada)

> ⚠️ Sección reconstruida a posteriori (20260713) a partir de encabezados de
> scripts y conversaciones. JJ: verificar y corregir lo que no cuadre.

- **Chunking por párrafos** (~1000 caracteres objetivo, solape de 1 párrafo,
  mínimo 50 caracteres por chunk, deduplicación por SHA-256 del contenido).
  Corpus bilingüe ES/EN etiquetado por slug (`en_gb` exacto o prefijo `en_gb_`).
- **Boilerplate estadístico**: líneas presentes en >40% de las páginas del
  mismo idioma se consideran menú/pie y se eliminan.
- **Enlaces markdown → solo texto visible**: las URLs CDN firmadas
  contaminaban los embeddings; la URL de la página vive en los metadatos.
- **Experimento: anteponer el título de página a cada chunk** → degradó la
  recuperación en todas las consultas de prueba → **revertido**.
- **Experimento: max_seq_length 128 → 256** → degradó los resultados
  (dilución por mean-pooling en ventanas largas) → **revertido**.
- Resultado: **config v3 congelada como óptimo medido** (605 chunks,
  MiniLM multilingüe, seq=128, ChromaDB coseno, top-k=5).

---

## 20260713 — Diseño de generacion.py (decisiones 1a / 2a / 3c / 4)

- **1a — Supresión del thinking de qwen3**: soft switch `/no_think` en el
  system prompt + limpieza regex de `<think>...</think>` como red de
  seguridad. Elegido frente a la API nativa de Ollama (`think: false`) por
  portabilidad a Groq en fase 2 sin mantener dos rutas de código.
- **2a — Arquitectura**: módulo reutilizable con
  `generar_respuesta(pregunta) -> dict` (respuesta, fuentes, chunks,
  puntuaciones, parámetros, timestamp) + bloque CLI. El dict de retorno es
  directamente el registro de trazabilidad (nivel avanzado del briefing) y
  la interfaz que consumirá app.py sin refactor.
- **3c — Guardarraíl "no sé" híbrido**: (capa 1) umbral de distancia
  configurable en .env que evita llamar al LLM si ningún chunk es
  suficientemente cercano; (capa 2) instrucciones de no-sé en el prompt
  para los casos grises que pasan el filtro.
- **4 — Parámetros de generación**: temperature y max_tokens en .env,
  con override `--temperature` en CLI para experimentos.

## 20260713 — Calibración del umbral de distancia (U1)

- Datos de calibración (busqueda.py, sin LLM):
  - "pedir cita" (buena): mejor similitud 0.3755 → distancia 0.6245
  - "auditorías" (floja): mejor similitud 0.5089 → distancia 0.4911
  - "piso en Móstoles" (fuera de corpus): mejor similitud 0.1801 → distancia 0.8199
- El umbral inicial 0.65 dejaba a la mejor pregunta un margen de solo 0.026.
- **Elegido U1: UMBRAL_DISTANCIA=0.75** (exige similitud ≥ 0.25), punto medio
  de la zona de separación observada. Recalibración fina prevista en S3 con
  el dataset de 20 preguntas.
- Hallazgo: el umbral mide confianza del emparejamiento semántico, no
  corrección del contenido — la pregunta floja (auditorías) puntúa MEJOR que
  la buena (cita). El caso auditorías-vs-privacidad debe resolverlo la capa 2.

## 20260713 — Experimento temperature 0.0 vs 0.2 (cierre decisión 4)

- Setup: qwen3:8b, seed=42, max_tokens=800, UMBRAL_DISTANCIA=0.75,
  4 preguntas × 2 temperaturas (~40 min en CPU).
  Log: logs/comparativa_temp_20260713110201L.jsonl (bruto).
- Resultado: **empate técnico** en corrección, citas y guardarraíles;
  diferencias solo estilísticas (~10% de longitud).
- **Elegido T-FINAL-a: LLM_TEMPERATURE=0.2**. Motivos: redacción marginalmente
  mejor en las dos preguntas con respuesta (0.0 produjo un cierre meta torpe
  en Espacio Joven); el log JSONL ya garantiza la trazabilidad de la
  respuesta exacta emitida; la ficha de qwen3 desaconseja el greedy decoding
  (T=0) por riesgo de repeticiones.
- Verificado además en las 8 generaciones:
  1. Cero fugas de `<think>` (decisión 1a validada).
  2. Guardarraíl-umbral filtró la pregunta fuera de corpus sin llamar al LLM
     (dist 0.8199 > 0.75, llm_llamado=false).
  3. Guardarraíl-prompt resolvió el caso gris auditorías/privacidad: los
     chunks pasan el filtro (dist 0.4911) pero el modelo emitió el mensaje
     de no-sé literal.
  4. Todos los teléfonos y emails de las respuestas trazados byte a byte a
     los chunks recuperados (regla 4 del prompt, verificación automática).

## 20260713 — Bugs y peculiaridades del entorno

- **`run comando > fichero` contamina el fichero**: el banner de run() sale
  por stdout y la redirección lo captura. Ocurrió dos veces (script de
  comparación v1 y regeneración del JSONL limpio). Fix del script:
  comparar_temperaturas_v2_20260713.sh (banner separado + parser tolerante).
  Fix estructural pendiente de decisión (banner por stderr en .bashrc).
- **Finales de línea mixtos en los JSONL**: Python en Windows escribe stdout
  con CRLF; los banners de bash usan LF; el grep de MSYS2 elimina el CR al
  filtrar. Consecuencia observada: un diff entre el JSONL bruto y el filtrado
  no encuentra ninguna línea común y vuelca ambos ficheros enteros (112 KB).
  No afecta a la validez de los datos (el CR final es whitespace para JSON).
