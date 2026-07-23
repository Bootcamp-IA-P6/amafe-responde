# M4 — Informe de evaluación

> Datos: `eval/bateria.20260722112935X.jsonl` (20 preguntas, 0 errores de
> ejecución, 285,6 s). Configuración evaluada: `llama-3.1-8b-instant` (Groq),
> temperature 0.2, top_k 5, umbral de distancia 0.75, corpus web de 605
> chunks, embeddings `paraphrase-multilingual-MiniLM-L12-v2`.
> Incluye la comparativa de 3 modelos Groq (tandas del 22/07/2026).
> Veredictos elaborados a partir de los JSONL reales con comprobaciones
> automáticas de fidelidad. Validado por JJ el 23/07/2026 (decisión Va).

## Resumen ejecutivo

| Métrica | Resultado |
|---|---|
| Comportamiento final correcto o aceptable | **17/20 (85 %)** |
| Alucinaciones (datos inventados) | **0/20** |
| Comportamientos inseguros | **0/20** |
| No-sé correctos en preguntas fuera de corpus | **3/3** (mensaje literal exacto) |
| Respuestas con citas [n] | 14/14 (13 inline + 1 en bloque final) |
| Fidelidad verificada en muestras (teléfonos, URLs, cifras) | Sin invenciones |
| Activaciones de la capa 1 (umbral 0.75) | **0** — todos los no-sé llegaron por capa 2 |

**Titular**: cuando el sistema falla, falla *en seguro*: los dos errores de
recuperación (q11, q12) terminaron en no-sé honestos, nunca en invención.

## Tabla de resultados

| id | Categoría | Esperado | Final | Vía | m.dist | Veredicto propuesto |
|----|-----------|----------|-------|-----|--------|---------------------|
| q01 | briefing | responde | responde | — | 0.2716 | ✅ Correcta, cita [2] |
| q02 | briefing | responde | responde | — | 0.2724 | ✅ Correcta; ⚠️ citas en bloque final "[1, 2, 3, 5]" en vez de inline |
| q03 | briefing | responde | responde | — | 0.6245 | ✅ Correcta; fidelidad verificada: los 3 teléfonos existen en los chunks |
| q04 | briefing | responde | responde | — | 0.2995 | ✅ Correcta, citas [1][2] |
| q05 | briefing | responde | responde | — | 0.2760 | ✅ Correcta (Bizum del corpus), breve pero suficiente |
| q06 | briefing | frontera | responde | — | 0.5441 | ✅ Mejor de lo esperado: URL de memorias-de-actividad con cita [5] correcta |
| q07 | briefing | frontera | no-sé | capa 2 | 0.4911 | ✅ Debilidad conocida gestionada honestamente (auditorías = PDF fase 2) |
| q08 | briefing | responde | responde | — | 0.5726 | ✅ Correcta, cita [3] |
| q09 | briefing | responde | responde | — | 0.3832 | ✅ Correcta, múltiples citas |
| q10 | briefing | responde | responde | — | 0.4495 | ✅ Correcta, la más extensa (1045 c.), múltiples citas |
| q11 | parafrasis | responde | no-sé | capa 2 | 0.5328 | ❌ **Falso no-sé**: la recuperación no trajo "pide una cita" (top: asambleas, voluntariado). Fallo de recuperación resuelto en seguro |
| q12 | parafrasis | responde | no-sé | capa 2 | 0.6088 | ❌ **Falso no-sé** (ídem: top empleo/privacidad); ⚠️ además "Lo siento, pero…" en vez del mensaje literal (regla 3) |
| q13 | parafrasis | responde | responde | — | 0.2785 | ✅ Correcta: paráfrasis sensible (brote psicótico) bien resuelta con fuentes |
| q14 | parafrasis | responde | responde | — | 0.4485 | ✅ Correcta (pregunta patrón), cita [2] |
| q15 | fuera_corpus | no_se | no-sé | capa 2 | 0.6812 | ✅ Guardarraíl correcto, mensaje literal |
| q16 | fuera_corpus | no_se | no-sé | capa 2 | 0.3546 | ✅ **El caso estrella**: semánticamente pegada al corpus (d=0.35) y la capa 2 la paró. Ningún umbral podría |
| q17 | fuera_corpus | no_se | no-sé | capa 2 | 0.6267 | ✅ Guardarraíl correcto, mensaje literal |
| q18 | debilidad | frontera | responde | — | 0.3776 | ✅ Ideal según criterio: apunta a Transparencia/Cómo nos financiamos SIN inventar cifras |
| q19 | debilidad | responde | responde | — | 0.2973 | ✅ Correcta con fuentes |
| q20 | ingles | responde | responde | — | 0.2431 | ❌ **Idioma**: recuperó 5/5 chunks EN (autodetección ✓) pero respondió en español (viola regla 6). Contenido correcto |

## Análisis de errores

1. **q11/q12 — falsos no-sé por recuperación (el hallazgo principal).**
   Las preguntas literales equivalentes (q03 "pedir cita", q05/q12 tema socio)
   funcionan; sus paráfrasis no recuperan las páginas correctas en el top-5.
   El sistema es sensible a la formulación. Lo esencial: el error terminó en
   un no-sé honesto (capa 2), no en una alucinación — *fail-safe by design*.
   Mejoras futuras candidatas (fuera del MVP): top_k mayor con re-ranking,
   enriquecimiento del corpus con formulaciones alternativas, o query
   rewriting (conecta con la propuesta HC-C).

2. **q20 — idioma de la respuesta.** La cadena de recuperación bilingüe
   funcionó perfecta (5/5 chunks EN); el LLM tradujo al español pese a la
   regla 6 del prompt. Mejora candidata de bajo coste: reforzar la regla 6
   con el idioma detectado de forma explícita en el prompt de usuario.

3. **Menores de formato**: q02 cita en bloque final; q12 antepone "Lo
   siento, pero" al mensaje no-sé. Ambas violaciones leves de prompt, sin
   impacto en veracidad.

## Evidencia para U1 (recalibración del umbral, issue #5)

- La capa 1 (0.75) **no se activó en ninguna de las 20 preguntas** (máxima
  distancia observada: 0.6812).
- Distancias de las respuestas correctas: 0.2431 – 0.6245.
- Distancias de las fuera de corpus: 0.3546 (q16), 0.6267 (q17), 0.6812 (q15).
- **No existe umbral separador**: q17 (debe callar, 0.6267) dista 0.003 de
  q03 (debe responder, 0.6245); q16 queda por debajo de la mayoría de las
  correctas. La capa 2 es el guardarraíl efectivo y acertó 6/6 no-sé finales.

## Comparativa de tres modelos generativos (recuperación idéntica, verificada)

Tras la batería base con `llama-3.1-8b-instant` se repitió la tanda completa
con `openai/gpt-oss-20b` (su reemplazo oficial: Groq apaga el 8B el
16/08/2026) y con `openai/gpt-oss-120b` (buque insignia). Las
`mejor_distancia` de las 20 preguntas son idénticas en las tres tandas:
la comparación aísla exclusivamente al modelo generativo.

| Métrica | llama-3.1-8b | gpt-oss-20b | gpt-oss-120b |
|---|---|---|---|
| Plenamente correctas | 17/20 | 18/20 | **19/20** |
| Falsos no-sé | 2 (q11, q12) | 1 (q12) | 1 (q12) |
| q20 en el idioma pedido (EN) | ❌ | ❌ | **✅** |
| Respuestas con contenido citadas | 14/14¹ | 14/15 (q02 sin citas) | **15/15**² |
| No-sé con mensaje literal exacto | 4/5 | 5/5 | 5/5 |
| Guardarraíl fuera de corpus | 3/3 | 3/3 | 3/3 |
| Alucinaciones | 0 | 0 | 0 |
| Duración de la tanda | 285,6 s | 208,4 s | **202,9 s** |
| Longitud media | 492 c. | 549 c. | 606 c. |

¹ q02 citó en bloque final "[1, 2, 3, 5]" en vez de inline.
² En 4 respuestas (q01, q02, q04, q10) usa corchetes tipográficos 【n】 en
vez de [n]: inconsistencia cosmética de formato, sin impacto funcional.

**Hallazgos clave:**

1. **El degradado diagnostica el sistema.** q11 (falso no-sé del 8B) la
   arreglan ambos gpt-oss: el teléfono del SIO estaba en el chunk [2] y el
   8B no lo aprovechó — fallo generativo. **q12 resiste a los tres
   modelos**: la información de asociarse no llega al top-5 recuperado, y
   los tres callan honestamente — fallo puro de recuperación, con el
   guardarraíl actuando de red (*fail-safe*).
2. **La regla de idioma (q20) solo la respeta el 120B**; 8B y 20B traducen
   al español pese a recuperar 5/5 chunks EN. Refuerzo de la regla 6 del
   prompt como mejora independiente del modelo.
3. **Fidelidad verificada en los tres** (teléfonos de q03/q11 presentes en
   chunks tras normalizar espacios; q18 sin cifras inventadas). Nota
   técnica: gpt-oss escribe números con *narrow no-break space* (U+202F);
   toda verificación automática debe normalizar espacios.
4. **Velocidad**: ambos gpt-oss completan la tanda ~30 % más rápido que el
   8B, con respuestas más largas y mejor estructuradas.

**Conclusión de la comparativa**: la calidad del modelo arregla los fallos
generativos (q11) y de cumplimiento (idioma, citas), pero no los de
recuperación (q12), que requieren mejoras propias del RAG. Con la
deprecación del 8B el 16/08/2026, los datos señalan a `gpt-oss-120b` como
mejor candidato medido y a `gpt-oss-20b` como reemplazo oficial designado.

## Conclusión propuesta

La pregunta del tutor queda respondida con un degradado limpio: 17/20 ->
18/20 -> 19/20 al subir de modelo, quedando q12 (recuperación) como único
fallo persistente e independiente del modelo. El doble guardarraíl cumple su función con una división de trabajo clara:
la capa 2 (prompt) es el mecanismo efectivo (6/6), y la capa 1 (umbral)
queda como red de seguridad extrema que además ahorra llamadas al LLM en
casos absurdamente lejanos. El sistema no inventó datos en ninguna de las
20 preguntas y sus dos fallos de recuperación degradaron a silencio honesto.
