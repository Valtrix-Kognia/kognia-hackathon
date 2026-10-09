# Protocolo de pruebas: varias personas con un solo micrófono

Las pruebas automáticas (`backend/bench/audio_bench.py`) usan voces sintéticas y miden un
**límite superior**. Este protocolo mide el comportamiento real con personas. Ninguna de
estas pruebas se considera aprobada sin el archivo exportado y el reporte del evaluador.

## Preparación

1. Un único portátil, un único micrófono (el integrado o uno de mesa), a 0,5–1,5 m de las personas.
2. Abrir el dashboard, elegir el modo de turnos indicado en la tabla y pulsar **Iniciar conversación**.
3. Al terminar cada escenario: **Exportar** → guarda `kognia-<sesión>.json`.
4. Evaluar:

```bash
cd backend
PYTHONPATH=. .venv/Scripts/python bench/score_session.py kognia-<sesión>.json bench/references/<escenario>.json
```

El reporte entrega WER, precisión de atribución de hablantes, intervenciones omitidas,
activaciones falsas y omitidas, solicitudes de repetición, intervenciones con voces
superpuestas y latencia p50/p95 (agente y navegador).

Para escenarios sin archivo de referencia, crear uno con el mismo formato:
`[{"person": "P1", "text": "lo que se dijo", "addressed": true|false}]`.

## Escenarios

| # | Escenario | Modo | Qué se espera | Referencia |
|---|-----------|------|---------------|------------|
| 1 | Una persona, silencio | Kognia | WER bajo, 1 hablante | crear |
| 2 | Una persona con ventilador encendido | Kognia | WER similar al #1 | crear |
| 3 | Una persona con música de fondo | Kognia | WER similar al #1 | crear |
| 4 | Dos personas por turnos | Kognia | 2 etiquetas, atribución alta | `04_dos_personas_turnos.json` |
| 5 | Tres personas por turnos | Kognia | ≥2 etiquetas; Deepgram puede fusionar voces parecidas | `05_tres_personas_turnos.json` |
| 6 | Cuatro personas por turnos | Kognia | ≥3 etiquetas | `06_cuatro_personas_turnos.json` |
| 7 | Dos personas hablando a la vez | Kognia | Chip “voces superpuestas” y/o “¿podrías repetirla?” | crear |
| 8 | Tres personas a la vez | Kognia | Igual que #7; nunca respuesta con datos inventados | crear |
| 9 | Conversación ambiental sin dirigirse al agente | Kognia | 0 activaciones falsas; solo responde la última | `09_conversacion_ambiental.json` |
| 10 | Interrupción diciendo “Kognia, para” mientras responde | Kognia | El audio se corta | crear |
| 11 | Una persona habla mientras el agente responde (sin “Kognia”) | Kognia | El agente no se interrumpe | crear |
| 12 | Dos personas conversan durante la respuesta | Kognia | El agente no se interrumpe; no responde a la charla | `12_dos_conversan_durante_respuesta.json` |
| 13 | Pregunta breve (“Kognia, ¿IPS en Pasto?”) | Kognia | Respuesta correcta | crear |
| 14 | Pregunta larga con pausas de 1–2 s | Kognia | No se corta la pregunta | crear |
| 15 | Acentos colombianos (paisa, costeño, rolo, pastuso…) | Kognia | WER comparable entre acentos | crear |

Repetir 4, 9, 11 y 12 en **Conversación abierta** para comparar activaciones falsas e
interrupciones entre modos.

## Registro de resultados

Guardar cada reporte en `backend/bench/results/manual/<escenario>-<fecha>.json`. No se deben
reportar métricas sin el archivo correspondiente.
