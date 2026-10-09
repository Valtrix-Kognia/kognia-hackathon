# Decisiones técnicas y métricas

Cada decisión se apoya en una medición registrada en `backend/bench/results/`. Donde una prueba no
se pudo ejecutar, se indica.

## 1. Fuente de datos y consultas

| Decisión | Motivo / evidencia |
|---|---|
| El LLM solo elige herramientas tipadas; el backend construye SoQL | Evita consultas arbitrarias; listas blancas de columnas y literales escapados (pruebas `test_soql.py`) |
| Catálogo de valores descargado de la API | `upper('quindío')` en SoQL no encontró coincidencias; el catálogo resuelve tildes, alias y ambigüedades (Armenia en dos departamentos) |
| Reportar prestadores únicos, sedes y registros | 41.427 filas = líneas de capacidad; 9.320 prestadores; 10.921 sedes |
| Guardián de filtros no mencionados | En la corrida e2e v3 Gemini añadió `nivel_atencion="sin dato"` y dividió por naturaleza, cambiando la población contada |
| Agregados precargados (conteos por departamento × naturaleza) | Mismas cifras que la consulta en vivo (4/4 conteos y ranking idénticos) en 0–1 ms frente a 250–1.250 ms |
| Timeout 8 s sin reintento ante timeout | Se midieron consultas de 84 s en datos.gov.co sin app token; reintentar una consulta lenta no ayuda |
| “Cali” → “SANTIAGO DE CALI” por sufijo | El municipio oficial no coincidía por prefijo |

## 2. Audio con micrófono compartido

### Supresión de ruido

`QUAIL_VF_*` (*voice focus*) aísla al hablante principal y eliminaría voces secundarias; se usa
`QUAIL_L`. El navegador desactiva su propio supresor (para no atenuar dos veces a quien está lejos)
y conserva cancelación de eco y AGC.

Benchmark offline (`bench/audio_bench.py`): voces sintéticas distintas mezcladas en un solo canal,
ruido de ventilador y música a SNR 5 dB, cuatro configuraciones, STT de producción con diarización.
Resultados (`audio_bench_v1_switch_rule.json`, `audio_bench_v2_cluster_rule.json`):

| Escenario | Hablantes | Detectados | Atribución por palabra |
|---|---|---|---|
| 2 personas por turnos | 2 | 2 | 100 % |
| 3 personas por turnos | 3 | 2 | 75 % (Deepgram funde dos voces) |
| 4 personas por turnos | 4 | 3 | ~82 % (QUAIL_L) |

Entre ejecuciones de la misma configuración la variación fue grande (la atribución de 4 personas sin
procesamiento pasó de 0,54 a 0,83), así que **las diferencias entre configuraciones de ruido no son
concluyentes** con datos sintéticos. `QUAIL_L` se mantiene por diseño (no aísla voces) y consume
~4 ms de CPU por trama de 10 ms. El ruido sintético a 5 dB no degradó la transcripción en ninguna
configuración.

### Solapamiento

Primera regla (alternancia rápida de hablantes): 0 de 8 solapamientos detectados. Al revisar las
palabras (`bench/overlap_probe.py`) se vio que en voces superpuestas aparecen **grupos de palabras de
baja confianza** y palabras perdidas. Regla final: alternancia rápida, o tramos cortos de varios
hablantes, o ≥2 palabras con confianza < 0,80 en una ventana de 3 **con al menos dos hablantes**
(esta última condición se añadió tras un falso positivo en una prueba en vivo con una sola voz).
Con la regla de grupos sin esa condición: 4/8 detectados, 1/24 falsos positivos.

### Turnos

| Problema observado | Corrección |
|---|---|
| Al hacer el habla del agente no interrumpible, LiveKit confirma el turno pero lo omite (“skipping reply”) y sus transcripciones contaminaban el turno siguiente | Alineación de transcripciones con el texto confirmado; los restos se publican como `omitido_mientras_hablaba` |
| Preguntas sobre IPS dichas mientras Kognia habla se perdían | Se difieren y se responden al terminar |
| “Kognia. Necesito que me” + “digas…” se respondía a medias | Retención de solicitudes incompletas y unión con la continuación del mismo hablante (5 s) |
| “Kognia.” solo generaba una llamada al LLM | Responde “Te escucho” con TTS directo y abre una ventana de escucha |
| El saludo abría la ventana de seguimiento | La ventana solo se abre tras responder un turno dirigido a Kognia |
| El STT omitió “Kognia” al inicio | También se aceptan preguntas claras sobre IPS (verbo interrogativo + término del dominio) |
| Diarización cambia de id en fragmentos cortos | Fragmentos de < 3 palabras pueden unirse aunque cambie el id si llegan en < 3 s |

**Modo por defecto.** Tras las pruebas con usuarios del equipo se cambió a conversación natural
(`open`): la exigencia de decir “Kognia” restaba fluidez. En ese cambio apareció un defecto: el token de
sesión no permitía al navegador actualizar su atributo de modo y LiveKit lo rechazaba sin error, por
lo que el agente seguía exigiendo la palabra de activación. Se añadió el permiso
`canUpdateOwnMetadata` y `open` pasó a ser el valor por defecto del agente. Verificación en modo
audio: “Hola, ¿cómo estás?” y “¿Qué estamos viendo en pantalla?” respondidas, “Okay.” ignorada,
“¿Cuántas IPS hay en Caldas?” respondida con consulta (193 prestadores, 211 sedes).

Prueba funcional del modo de activación en audio (agente real, voz sintética): conversación ajena ignorada 3/3,
pregunta con “Kognia” respondida con consulta, seguimiento a 6,7 s respondido con contexto,
pregunta ajena a 21,9 s ignorada.

## 3. Latencia

### Instrumentación

Cada turno tiene un `turn_id` compartido por backend y navegador. El worker marca, con relojes
monotónicos y relativo a la confirmación del turno: fin de habla, decisión, inicio y primer token de
cada llamada al LLM, inicio/fin de herramientas (y tiempo HTTP puro de Socrata), primer texto y primer
audio del TTS, inicio de reproducción e interrupciones. El navegador mide la aparición real de energía
en el audio del agente (no el indicador de hablante activo del servidor) y la envía al backend con el
mismo `turn_id`; si llega una decisión nueva antes del audio, la medición anterior queda como
“reemplazada” en lugar de inflarse.

Las muestras de 5–7 s del navegador en la primera versión correspondían a turnos lentos reales
(primer token del LLM de 3,2–3,6 s) y a decisiones recibidas mientras el agente seguía hablando la
respuesta anterior; con el agente en silencio, la diferencia navegador−servidor fue estable en
0,3–0,4 s.

### Microbenchmarks A/B (alternados)

`bench/llm_ttft.py` — primera respuesta de Gemini con las herramientas reales (n=8 por variante):

| Variante | TTFT p50 / p95 | Herramienta correcta |
|---|---|---|
| Actual (gemini-2.5-flash) | 1.935 / 2.832 ms | 7/8 |
| `reasoning_effort=none` | 1.531 / 2.824 ms | 6/8 |
| Prompt compacto | 2.123 / 3.986 ms | 6/8 |
| Historial de 20 turnos | 2.197 / 2.430 ms | 8/8 |
| gemini-2.5-flash-lite | 1.491 / 1.976 ms | 5/8 |

Se mantiene Gemini 2.5 Flash con el prompt actual (las variantes rápidas pierden precisión de
herramientas) y se acota el historial a 20 elementos.

`bench/tts_ttfb.py` — primer audio de Cartesia (n=9): sonic-3 996 ms, sonic-turbo 1.020 ms,
sonic-3.5 1.032 ms (p50); silencio inicial 50 ms. Se mantiene sonic-3.

### Antes / después

Prueba con el agente real y voz sintética por el pipeline de audio completo (`bench/latency_run.py`,
8 preguntas, CPU sin otras cargas):

| p50 / p95 | Línea base | Final, sin frase de espera | Final, con frase de espera |
|---|---|---|---|
| Primer audio | 3.976 / 5.718 ms | 4.011 / 7.035 ms | **2.564 / 5.045 ms** |
| Respuesta con datos | 3.976 / 5.718 ms | 4.011 / 7.035 ms | 4.508 / 6.956 ms |
| Fin de turno | 698 / 2.076 ms | 554 / 2.496 ms | 482 / 609 ms |

La frase de espera (“Un momento, consulto los datos oficiales”, sin cifras) reduce la espera
percibida ~1,4 s y retrasa ~0,5 s la respuesta con datos.

Navegador real e2e (`frontend/e2e/voice-e2e.mjs` + `bench/e2e_compare.py`):

| p50 / p95 | v1 (antes) | v3 (correcciones) |
|---|---|---|
| Primer audio | 4.287 / 5.587 ms (n=7) | 4.011 / 7.098 ms (n=12) |
| Primer token del LLM | 1.540 / 2.829 ms | 2.080 / 3.851 ms |
| TTS primer audio | 588 / 1.765 ms | 401 / 545 ms |
| HTTP Socrata | 3.189 / 5.441 ms | 1.037 / 2.361 ms |
| Navegador: decisión → audio | 4.174 / 6.787 ms | 3.806 / 6.649 ms |
| Decisiones correctas | 10/13 (sesión A) | ver `sesion_*_v3.report.json` |

La variación del primer token de Gemini entre corridas (0,9–3,9 s) domina el primer audio. La corrida
v4 quedó incompleta porque se agotó la cuota de LiveKit Inference del proyecto.

## 4. Dashboard

| Decisión | Motivo |
|---|---|
| Visualizaciones derivadas en el frontend desde resultados de herramientas | No se modificó el backend; el LLM no produce datos para gráficos |
| SVG propio en lugar de librería de gráficos | Control de accesibilidad y peso; solo `d3-geo` para el mapa |
| Paletas validadas con el validador de dataviz | Categórica (8 tonos, ΔE CVD adyacente ≥ 8,4 sobre `#111C31`) y secuencial monótona |
| Distritos sumados al departamento solo para sedes/registros | Prestadores únicos no son aditivos |
| Mapa con datos completos de la API y resaltado de lo que Kognia menciona | Un top-N pintaría el resto como “sin datos” |
| Anillos del GeoJSON reorientados | d3-geo (esférico) dibujaba el complemento del polígono |

Verificación visual (Chrome sin interfaz, 1920/1440/390 px): 33/33 departamentos con datos,
selección por teclado con cifras correctas, sin errores de consola ni desbordamiento horizontal;
mapa visible en 0,5–0,7 s; carga inicial 90 kB transferidos.
