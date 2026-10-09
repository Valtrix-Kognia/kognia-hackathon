# Kognia Voice — backend

Dos procesos comparten el mismo paquete `app`:

| Proceso | Comando | Responsabilidad |
|---|---|---|
| API HTTP | `uv run uvicorn app.main:app --port 8000` | Tokens de sesión LiveKit, endpoints de consulta de IPS, salud |
| Worker de voz | `uv run python app/voice/worker.py dev` (local) / `start` (producción) | Conversación en tiempo real con LiveKit Agents |

La API instala solo las dependencias base (`uv sync`); el worker necesita el extra `agent`
(`uv sync --extra agent`, incluye torch CPU y modelos de emoción).

## Módulos

| Ruta | Contenido |
|---|---|
| `app/infrastructure/socrata/` | `SocrataClient` (SODA3, reintentos acotados, límite de tamaño, tiempo HTTP por consulta), `SoqlQuery` (columnas en lista blanca, literales escapados), `QueryCache` (TTL + deduplicación en vuelo) |
| `app/application/services/` | `IpsQueryService` (conteos, rankings, búsqueda, detalle, resumen), `ValueCatalog` (valores reales del dataset), `AggregateCache` (conteos precargados), `SessionTokenService` (tokens de sala) |
| `app/domain/models/` | Contratos Pydantic: filtros, resultados, transcripción, emoción, eventos en tiempo real, columnas permitidas |
| `app/api/` | Rutas FastAPI, esquemas de consulta, manejo centralizado de errores, rate limiting |
| `app/voice/worker.py` | Composición de la sesión: STT, LLM, TTS, turnos, interrupciones, supresión de ruido, eventos |
| `app/voice/kognia_agent.py` | Agente: observa el STT por palabra, decide cada turno, traza LLM/TTS, retiene y une solicitudes |
| `app/voice/conversation_controller.py` | Estado de la conversación con micrófono compartido: transcripción, diarización, interrupción por “Kognia”, preguntas diferidas |
| `app/voice/turn_manager.py` | Política de turnos: activación, seguimiento, solicitudes incompletas, solapamiento, muletillas |
| `app/voice/wake_word.py` | Detección textual de “Kognia” por niveles (confirmada, probable, ambigua) con normalización fonética |
| `app/voice/speaker_diarization.py` | Tramos por hablante desde ids por palabra; fragmentos no atribuibles; señales de solapamiento |
| `app/voice/turn_alignment.py` | Alinea las transcripciones con el turno que LiveKit confirmó |
| `app/voice/ips_toolset.py` | Herramientas del LLM (`count_ips`, `group_ips`, `search_ips`, `get_ips_details`, `get_dataset_overview`), frase de espera, guardián de filtros |
| `app/voice/latency_metrics.py` | Traza por turno (`turn_id`) y resumen p50/p95, incluidas mediciones del navegador |
| `app/emotions/` | Clasificador pysentimiento y worker asíncrono que no bloquea el audio |
| `bench/` | Benchmarks y herramientas de evaluación (ver abajo) |

## Pruebas

```bash
uv run pytest -q                     # 139 pruebas unitarias (sin red)
uv run ruff check app tests bench
uv run ruff format app tests bench
```

## Benchmarks y evaluación

| Script | Qué mide |
|---|---|
| `bench/latency_run.py` | Latencia por etapa con el agente real vía `lk agent debugger --audio` |
| `bench/audio_bench.py` | Supresión de ruido × diarización × solapamiento con voces sintéticas en un canal |
| `bench/overlap_probe.py` | Palabras, hablantes y confianzas del STT por escenario |
| `bench/llm_ttft.py` / `bench/tts_ttfb.py` | A/B de primer token de Gemini y primer audio de Cartesia |
| `bench/e2e_audio.py` | Genera los WAV de las sesiones e2e (4 voces) y sus referencias |
| `bench/e2e_report.py` / `bench/e2e_compare.py` | Decisiones y latencia de una exportación del dashboard / comparación entre corridas |
| `bench/score_session.py` | Puntúa una sesión manual exportada contra un guion de referencia |

Resultados en `bench/results/`; análisis en [`../docs/DECISIONES_Y_METRICAS.md`](../docs/DECISIONES_Y_METRICAS.md).

## Configuración

Ver la tabla de variables en el [README principal](../README.md#configuración) y la plantilla
[`.env.example`](.env.example). El backend carga `.env` y `.env.local` del directorio `backend/`.
