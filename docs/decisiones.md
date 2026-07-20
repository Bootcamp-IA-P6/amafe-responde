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

## 20260713 — Inventario de PDFs y decisión de alcance (P1 → O1 → O2)

- inventario_pdf.py v1.1 (solo lectura) sobre CORPUS_PATH: 128 PDFs en disco,
  86 únicos (42 copias por hash SHA-256, incluidas copias con sufijo CDN).
- Tipos: DIGITAL=34, ESCANEADO=28, MIXTO=24. Páginas que requerirían OCR: 721.
- Hallazgo crítico: las auditorías (10 docs, 305 pág) son 100% escaneadas:
  cero caracteres extraíbles. Las memorias 2016-2025 (12 docs, 1,19M chars) y
  los boletines 2022+ son extraíbles ya; total listo sin OCR: 2,87M chars
  (~4-5x el corpus web actual).
- v1 → v1.1: el patrón de auditoría no cazaba la serie Informe_y_cuentas
  2015-2021 (sin la palabra "auditoría"); añadido patrón 'cuentas', medido
  contra los 106 nombres reales del tree.
- 5 documentos sensibles identificados y excluidos (actas firmadas,
  delegación de voto, candidatos a junta). Estrategia: lista blanca, nunca
  lista negra.
- Decisión de alcance: O1 elegida (extraer texto de DIGITAL+MIXTO aprobados +
  chunk de METADATOS por cada ESCANEADO aprobado: la pregunta del briefing
  "qué información pública existe sobre auditorías" se responde con
  existencia+ubicación, sin OCR). O2 (OCR Tesseract, ~721 pág) como fase
  posterior sin rehacer nada. O3 descartada.
- Orden de trabajo: ingesta_pdf.py antes que app.py (el corpus x5 justifica
  el adelanto).

## 20260714 — Fix estructural run/banner por stderr (R1)

- Cierra el pendiente del 20260713: `banner()` y `run()` del `.bashrc` emiten ahora sus líneas informativas por **stderr** (`>&2`).
- Motivo: `run comando > fichero` capturaba el banner en el fichero redirigido y contaminó dos veces los JSONL de experimentos.
- Verificado el 20260714: la redirección de stdout ya no arrastra el banner; los logs JSONL quedan limpios sin parser tolerante.

## 20260714 — Cambio de alcance: MVP solo-web (H1)

- Decisión del responsable de formación/patrocinador: **priorizar un MVP que use únicamente el corpus web actual** (605 chunks); la incorporación de PDFs pasa a fases sucesivas.
- Consecuencias:
    - La revisión manual de la lista blanca de PDFs queda **PAUSADA, no descartada** (etiquetas [OKI]/[OKI+NOMBRES] conservadas donde estaban).
    - `ingesta_pdf.py` (D1a/D2a/D3a) e `indexado` v2 se aplazan; las decisiones de diseño ya tomadas siguen vigentes para cuando se retomen.
    - La pregunta del briefing sobre auditorías queda como **limitación conocida y documentada** del MVP: argumento de roadmap para fase 2, no defecto.
- **H1a — Hoja de ruta MVP confirmada por JJ (20260714):**
    - M1. Repo público en GitHub (org Bootcamp-IA-P6, gh CLI, licencia MIT, README técnico, GitHub Projects como Kanban).
    - M2. `app.py` con Streamlit: pregunta, respuesta con citas, fuentes con URL, no-sé, preguntas sugeridas, log JSONL.
    - M3. Groq como LLM (cosecha de la decisión 1a: cambio de 3 variables del .env). Primera clave secreta real del proyecto.
    - M4. Batería de 20 preguntas + runner del informe de evaluación; ejecución comparada Ollama vs Groq; recalibración de U1.
    - M5. Dockerización (app ligera; LLM fuera vía API).
    - M6. Despliegue (Streamlit Community Cloud vs HF Spaces, a decidir entonces).
- Orden acordado dentro de M1 (H1d): registrar esta entrada → auditoría pre-push del repo (historial de .env, secretos, exclusiones) → LICENSE MIT + .gitignore ampliado → `gh repo create --public --source=. --push`

## 20260715 — Incidencia M1: push adelantado y remediación (R2a, C1a)

- **Incidencia (20260714)**: el primer `gh repo create --push` se ejecutó
  antes de aplicar las exclusiones E1a y de resolver los hallazgos de la
  auditoría pre-push. El repo público contuvo durante ~2 h logs de trabajo
  y el CSV del inventario de PDFs (nombres de fichero procedentes de la web
  pública de AMAFE, incluidos los 5 documentos excluidos de la lista blanca).
- Verificaciones de la auditoría: `.env` nunca estuvo en el historial
  (A1=0); el único match del barrido de secretos (A3=1) se verificó como
  falso positivo (la línea `api_key=LLM_API_KEY` de generacion.py).
- **Remediación R2a**: backup .tgz pre-filtro → `git filter-repo` purgando
  `logs/*.log` y `*inventario_pdf*.csv` de todo el historial (15 commits
  conservados, 0 apariciones tras la purga) → borrado del repo remoto
  contaminado → republicación del historial limpio (20260715). Hashes
  reescritos: los enlaces a commits anteriores quedan invalidados.
- **Revisión de sensibilidad sobre el backup real** (43 ficheros tracked):
  sin rutas locales, sin nombres de máquina ni datos personales; todos los
  emails y teléfonos del corpus son contactos oficiales públicos de AMAFE
  (info@, móvil de contacto, CIF), que el asistente debe poder citar.
- **C1a — Email de autor**: se mantiene el email personal en los commits
  (decisión consciente; ya expuesto en repos públicos anteriores).
  Mitigación hacia adelante: ajustes de privacidad de email en GitHub y
  bloqueo de pushes que expongan el email.
- Verificación post-republicación vía API de GitHub: 44 ficheros, `logs/`
  solo con `.gitkeep`, cero CSV/logs, licencia MIT reconocida, 16 commits
  descriptivos.
- **Lección para el checklist**: el push es SIEMPRE el último paso;
  auditoría → hallazgos resueltos → exclusiones → LICENSE → push.

## 20260720 — M3: Groq como LLM en la nube (G1b)

- Contexto de catálogo (verificado en console.groq.com/docs/models el
  20260720): los modelos Qwen en Groq están solo en *preview* (no aptos para
  producción), descartando repetir la familia del modelo local.
- **G1b elegido: `llama-3.1-8b-instant`** (producción, ~560 t/s, $0.05/$0.08
  por 1M tokens, gratis en el free tier). Motivo: el más rápido y barato de
  los candidatos y de tamaño hermano del qwen3:8b local — habilita una
  comparativa "de igual a igual" en la batería M4. Alternativas registradas:
  llama-3.3-70b-versatile (más calidad, más coste) y gpt-oss-20b (razonador,
  más incógnitas de API).
- Cambio efectivo: solo las 3 variables del .env previstas por la decisión 1a
  (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY). Cero cambios de código.
- **Primera ejecución** (logs/groq_primera.20260720131337L.json), misma
  pregunta patrón "¿Qué es el Espacio Joven?":
  - Recuperación idéntica byte a byte a la de Ollama (mismos 5 chunks y
    similitudes): la capa de recuperación no depende del LLM, verificado.
  - Latencia del pipeline completo ≈13 s (frente a ~5 min del qwen3:8b en
    CPU); la generación pura en Groq es de segundos.
  - Cero fugas de <think>: con Llama, el /no_think y la regex de 1a quedan
    como red de seguridad inerte, según lo diseñado.
- **Observación cualitativa nº1 para M4 (fidelidad de atribución)**: la
  respuesta atribuye a Espacio Joven una afirmación genérica del chunk
  salud_mental__024 sobre recursos de intervención temprana; el contenido
  existe en la fuente, la atribución es una extensión del modelo (el qwen
  local no empleó ese chunk). Candidata a criterio de la batería de 20.
- Free tier de Groq verificado como suficiente para M4 (límites por
  organización: ~30 req/min y 6K-30K tokens/min según modelo); el runner de
  la batería incluirá una pausa entre preguntas.
- Seguridad: clave nueva y exclusiva del proyecto, presente solo en .env
  (gitignorado; historial verificado A1=0). El dict de trazabilidad no
  transporta la clave (verificado sobre JSON real).

