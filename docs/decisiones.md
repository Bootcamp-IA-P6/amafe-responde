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

## 20260721 — M2b: historial y persistencia en la app Streamlit

Encargo del tutor sobre la app M2. Material de estudio: tutorial oficial de
apps conversacionales de Streamlit
(https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps),
adaptado al contrato propio (dict completo de `generar_respuesta()`, `.env` en
lugar de `secrets.toml`, sin streaming: el contrato devuelve el dict cerrado y
con Groq la latencia es de segundos).

- **HA1a — Historial visual por dicts completos**: `st.session_state.historial`
  guarda el dict íntegro de `generar_respuesta()` por turno; el bocadillo del
  asistente se pinta con la misma lógica rica de M2 (respuesta+citas+fuentes+
  expander D1a, o aviso no-sé+descartados) más caption de trazabilidad por
  turno (modelo, temperature, umbral, timestamp). Descartada HA1b (solo texto):
  perdía fuentes y guardarraíles visibles.
- **HA2b — Preguntas sugeridas solo con historial vacío** (estilo ChatGPT):
  desaparecen al primer turno y reaparecen tras limpiar. Descartadas HA2a
  (siempre visibles) y HA2c (sidebar).
- **HB1b — Recarga manual del historial**: botón "Cargar historial anterior"
  que relee `logs/consultas_app.jsonl` (D3a) completo, antepone los turnos al
  historial en curso, descarta líneas corruptas contándolas, y se deshabilita
  tras cargar (una vez por sesión; se rehabilita al limpiar). Descartadas HB1a
  (recarga automática de N) y HB1c (todo siempre). La recarga NUNCA reescribe
  el JSONL (verificado byte a byte en pruebas).
- **HB2a — Limpiar solo lo visual**: el botón vacía `session_state.historial`;
  el JSONL es el registro de trazabilidad y no se toca.
- **HC0 — Sin memoria conversacional del LLM**: fuera de alcance salvo
  petición explícita del tutor; `generar_respuesta()` queda intacta.
- **S1 — Spinner dinámico**: "varios minutos" solo si `LLM_BASE_URL` apunta a
  localhost; con backend en nube, mensaje con el nombre del modelo.
- **Incidencia detectada en pruebas**: el `disabled` del botón de recarga se
  evaluaba antes de procesar el clic (un rerun tarde), dejando una ventana de
  doble clic que duplicaría turnos. Corregido con `st.rerun()` inmediato tras
  cargar y tras limpiar; cubierto por los casos 4 y 5.
- **Verificación**: `tests/test_app_m2b.py` (AppTest, mock de `generacion` con
  el contrato real verificado sobre `logs/consultas_app.jsonl`): 6/6 casos
  verdes — respuesta completa con JSONL de 1 línea LF pura, no-sé sin fuentes,
  HA2b, recarga sin reescritura y con corruptas descartadas, limpieza sin
  tocar el JSONL, y error de backend sin registro.

## 20260722 — Mapa de URLs del proyecto (U-M1b, U-M2b)

Adaptación al P12 del centro de navegación `docs/URLS.md` del P10JJ.

- **U-M1b — Generación por script**: `scripts/show_urls.sh` regenera
  `docs/URLS.md` completo en cada ejecución: issues y PRs reales vía
  `gh api` (separando PRs por la clave `pull_request` de la API), inventario
  de ficheros clave vía `git ls-files` (src/, app/, tests/ — los módulos
  nuevos entran solos), enlaces RAW desde `main`, Kanban #77 y recursos
  externos. Salida con LF puro y salto de línea final (`newline="\n"`).
  El fichero generado lleva aviso de "no editar a mano". Descartada U-M1a
  (mantenimiento manual): la "última revisión" dejaría de ser veraz.
- **U-M2b — PR propio**: rama `feature/urls-mapa` tras el merge de M2b
  (un PR = un tema). Descartada U-M2a (colar el mapa en el PR de M2b).
- La primera versión estática sellada (URLS.20260722090634X.md) queda en
  `downloads/` como referencia local, fuera del repo: un solo origen de
  verdad, el generado.
- **Verificación en sandbox**: ejecución del script con shims de `gh`/`uv`
  y fixtures que replican la forma real de la API (captura real de issues
  actualizada con el transcript del merge #11; pulls con el esquema estándar).
  Resultado: 8 issues y 3 PRs mergeados listados, bloques dinámicos
  correctos sobre main@40f9770, cero CRLF, salto final presente. En la
  máquina real `gh api` va autenticado (sin el rate limit anónimo que
  afectó al sandbox).

## 20260722-23 — M4: batería de evaluación, comparativa de modelos y umbral (issues #4 y #5)

Encargo: dataset de 20 preguntas + informe de evaluación (nivel avanzado del
briefing), ampliado por indicación del tutor con comparativa de modelos de
más calidad en Groq (nivel experto) tras cancelar la tanda local qwen3:8b
(un smoke real midió 360 s/pregunta en CPU: ~2 h la tanda completa).

- **Q1c — Dataset mixto**: 20 candidatas redactadas por Claude en 5 bloques
  (10 literales del briefing, 4 paráfrasis, 3 fuera de corpus, 2 sobre la
  debilidad financiación/auditorías, 1 en inglés), vetadas y aprobadas por
  JJ sin cambios. Congelado en `eval/preguntas.jsonl` (id, pregunta,
  categoría, esperado, nota). Descartadas Q1a (sin veto) y Q1b (desde cero).
- **Q2a — Evaluación manual estructurada** (guardarraíl, fuentes, fidelidad,
  citas) con informe en `eval/informe_evaluacion.md`. RAGAS (Q2b) queda
  como línea futura.
- **Runner**: `eval/runner_bateria.py` (pausa configurable para el free
  tier, fusión dataset+trazabilidad, error registrado sin detener tanda;
  stdout=ruta de datos, stderr=progreso — R1). Probado con
  `tests/test_runner_m4.py`: 3/3 verdes con mock del contrato real
  inyectado vía sys.modules (wrapper runpy).
- **Q4a — Batería antes que umbral**: las distancias reales de las 20
  preguntas son la evidencia de U1. Descartada Q4b (recalibrar a ojo).
- **Tres tandas** (22/07): `llama-3.1-8b-instant` (285,6 s),
  `openai/gpt-oss-20b` (208,4 s) y `openai/gpt-oss-120b` (202,9 s) —
  G2b y G2a marcadas sucesivamente por JJ. Recuperación idéntica verificada
  en las tres (mismas mejor_distancia): la comparación aísla la generación.
  Resultados: 17/20 → 18/20 → 19/20; q12 (falso no-sé) resiste a los tres
  = fallo puro de recuperación con degradación segura (fail-safe); q11 la
  arreglan ambos gpt-oss (el dato estaba en el chunk [2]: fallo generativo
  del 8B); q20 solo el 120B responde en inglés; 0 alucinaciones en 60
  generaciones (fidelidad verificada normalizando espacios: gpt-oss usa
  narrow no-break space U+202F en cifras).
- **U1a — Mantener UMBRAL_DISTANCIA=0.75** (cierra issue #5): la capa 1 no
  se activó en ninguna de las 60 generaciones (máx. distancia 0.6812) y no
  existe umbral separador (q17=0.6267 debe callar vs q03=0.6245 debe
  responder; q16=0.3546 fuera de corpus por debajo de la mayoría de las
  correctas). La capa 2 (prompt) queda documentada como guardarraíl
  efectivo: 6/6 no-sé finales correctos. Descartadas U1b (0.65) y U1c (0.70).
- **G3a — Modelo de producción: `openai/gpt-oss-120b`**: mejor medido
  (19/20), único que respeta el idioma (q20) y cita el 100 % de las
  respuestas; además la migración desde llama-3.1-8b-instant es obligatoria
  (Groq lo apaga el 16/08/2026, anuncio del 17/06). Matiz documentado:
  cita ocasionalmente con corchetes tipográficos 【n】 (cosmético).
  Cambios: `.env` local de JJ, `.env.example` y tabla del README.
  Descartadas G3b (gpt-oss-20b, 18/20) y G3c (ronda extra de prompts).
- **Mejoras sistémicas detectadas** (independientes del modelo, fuera de
  M4): reforzar regla 6 del prompt (idioma; 8B y 20B tradujeron q20) y
  regla 2 (citas en respuestas tipo lista, q02). Candidatas a mini-issue.
- **Va — Informe validado** por JJ (23/07) sobre el borrador v3 con
  comparativa triple; materiales de apoyo generados para la evaluación
  manual: respuestas de los 3 modelos y atlas del corpus con los 605
  chunks íntegros (documentos de trabajo, fuera del repo).

## 20260723 — IDX1a: índice ChromaDB incluido en el repo (preparación M6a)

Streamlit Community Cloud despliega desde el repo de GitHub, y `chroma_db/`
estaba gitignorado: la app en la nube no tendría índice.

- **IDX1a — Commitear `chroma_db/`** (11 MB medidos con `du -sh`): arranque
  inmediato en la nube sin coste de cómputo, y quien clona el repo puede usar
  la app sin ejecutar ingesta ni indexado. `.gitignore` ajustado
  (`!chroma_db/`). Descartada IDX1b (reconstruir el índice al arrancar desde
  `data/processed/chunks.jsonl`): primer arranque lento y RAM justa en el
  tier gratuito con el modelo de embeddings cargado.
- Efecto colateral positivo documentado en el README: instalación sin corpus
  local (los pasos de ingesta/indexado quedan solo para regenerarlo).

## 20260723 — M6a: despliegue en Streamlit Community Cloud (issue #15)

Orden del tutor (22/07): desplegar en Streamlit Cloud antes de dockerizar.
App pública en producción: **https://amafe-responde.streamlit.app**

- **Dependencias para la nube**: `requirements.txt` generado desde `uv.lock`
  (`uv export`) y adaptado a CPU: `torch==2.13.0+cpu` con el índice CPU de
  PyTorch y 16 paquetes nvidia/triton eliminados (la variante CUDA, ~3-4 GB,
  es inútil sin GPU y arriesga los límites del tier gratuito). PR #16.
- **Hotfix torchvision** (PR #17): en la nube, `transformers` importa
  `torchvision` (image_processing_zoedepth) y no estaba en el lock — en
  local existía instalado aparte (era el origen de los tracebacks del
  watcher). Añadido `torchvision==0.28.0+cpu`; emparejamiento verificado en
  PyPI (0.28.0 requiere exactamente torch==2.13.0).
- **Configuración del despliegue**: repo `Bootcamp-IA-P6/amafe-responde`,
  rama `main`, main file `app/app.py`, Python 3.12. El índice ChromaDB viaja
  en el repo (IDX1a): arranque sin ingesta ni indexado.
- **Secrets**: LLM_BASE_URL, LLM_MODEL y LLM_API_KEY en el panel de la app
  (TOML de nivel raíz → expuestos como variables de entorno → `os.getenv`
  los lee sin cambios de código). La clave de Groq nunca toca el repo.
  Incidencia documentada: el editor de Secrets de App settings no aceptaba
  ratón en tres navegadores/modos; solución: enfocar el editor navegando
  con Tab y pegar con Ctrl+V (solo admite pegado). Alternativa documentada:
  el campo Secrets de "Advanced settings" al desplegar.
- **Verificación en producción** (vídeo del 23/07, fotogramas extraídos):
  la app responde "¿Qué es el Espacio Joven?" con cita, fuentes enlazadas,
  expander de fragmentos y caption de trazabilidad mostrando
  `openai/gpt-oss-120b` (G3a en producción).
- **Notas operativas**: app pública (las consultas de terceros consumen el
  free tier de Groq); `logs/consultas_app.jsonl` en la nube es efímero (se
  pierde en cada reinicio) — el registro de referencia sigue siendo el local.

## 20260724 — M5: dockerización de la aplicación (issue #6)

Imagen Docker autocontenida, construida y verificada en local (Docker 29.1.3
sobre Windows 11/WSL2). Build de ~10 min; imagen 1,52 GB (4,79 GB en disco
local por las capas descomprimidas).

- **Dockerfile** (`python:3.12-slim`): dependencias del `requirements.txt`
  CPU de M6a (capa cacheable), modelo de embeddings horneado en build
  (BLD1a) con `HF_HUB_OFFLINE=1` fijado después (el runtime no toca la red
  para embeddings), COPY selectivo (`src/`, `app/`, `chroma_db/`), usuario
  sin privilegios UID 1000 (recomendación de HF Spaces) y `logs/`
  escribible. `.dockerignore` como blindaje adicional (nunca `.env`, `.git`
  ni `logs/`).
- **Secretos solo en runtime**: `docker run --env-file .env`; verificado que
  `docker run --rm amafe-responde env | grep LLM` sale vacío — la imagen no
  contiene credenciales.
- **Incidencia y lección — dotenv parsea, `--env-file` no**: un comentario
  en línea en el `.env` (`UMBRAL_DISTANCIA=0.75   # ...`) funciona en local
  porque python-dotenv recorta el comentario, pero `docker --env-file` pasa
  el valor íntegro y `float()` revienta. Regla adoptada: en `.env`, los
  comentarios SIEMPRE en línea propia y los valores sin comillas
  (detector: `grep -n "=.*#" .env`).
- **Detalle asumido**: el filtro del requirements eliminó los paquetes
  `nvidia-*`/`triton` pero se colaron `cuda-bindings`/`cuda-pathfinder`/
  `cuda-toolkit` (~7 MB, arrastrados por dependencias); inofensivos sin
  GPU, no justifican rebuild.
- **Verificación (mini-M4 en el contenedor, capturas del 24/07)**:
  "¿Qué es el Espacio Joven?" → respuesta con citas, fuentes y caption
  `openai/gpt-oss-120b · umbral 0.75`; "¿Cuánto cuesta la entrada al Museo
  del Prado?" → no-sé. Observación registrada para mini-issue posterior:
  cuando el no-sé llega por capa 2 (llm_llamado=true), la app muestra
  "Fuentes consultadas" bajo el mensaje — inconsistencia visual heredada
  de M2, sin impacto en veracidad.

