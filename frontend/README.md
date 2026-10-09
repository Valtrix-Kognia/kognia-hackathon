# Kognia Voice — frontend

Dashboard Angular 21 (componentes standalone, signals, detección de cambios sin zone.js, Tailwind 4).

```bash
npm install
npx ng serve                 # http://localhost:4200 (API en http://localhost:8000)
npx ng test --watch=false    # 23 pruebas (Vitest)
npx ng build                 # dist/frontend/browser
```

La URL de la API está en `src/environments/environment.ts` (desarrollo) y
`environment.production.ts` (producción).

## Organización

| Ruta | Contenido |
|---|---|
| `core/models/` | Contratos TypeScript de eventos (`realtime-event.model.ts`), resultados de IPS y visualizaciones |
| `core/services/voice-room.service.ts` | Sala LiveKit: conexión, micrófono, audio del agente, eventos, texto (`lk.chat`), modo de conversación, medición de reproducción |
| `core/services/conversation-store.service.ts` | Estado de la sesión con signals; descarta eventos de otras sesiones o desordenados |
| `core/services/agent-audio-monitor.ts` | Detecta cuándo el audio del agente es audible en el navegador |
| `core/services/visualization-builder.ts` | Convierte resultados de herramientas en especificaciones de gráficos |
| `core/services/dashboard-state.service.ts` | Consulta seleccionada, pestaña activa y actualización del mapa |
| `core/services/ips-api.service.ts` | Lecturas de la API con caché y deduplicación |
| `core/services/preferences.service.ts` | Tamaño de letra y subtítulos (persistidos en el navegador si es posible) |
| `features/conversation/` | Panel de voz, orbe de audio, estado y última decisión de turno |
| `features/transcription/` | Transcripción, línea temporal de hablantes, correcciones |
| `features/viz/` | Métricas, barras, dona, tabla y panel de visualización |
| `features/map/` | Mapa coroplético (`d3-geo`, carga diferida), catálogo nombre→ISO, escala por cuantiles |
| `features/evidence/` | Procedencia de cada respuesta |
| `features/emotions/`, `features/metrics/` | Sentimiento/emoción y latencia |
| `public/geo/colombia-departamentos.geojson` | Límites geoBoundaries ADM1 (OpenStreetMap, ODbL 1.0) |
| `public/staticwebapp.config.json` | Fallback de navegación para Azure Static Web Apps |

## Conversación

El modo de conversación lo decide el agente (`TURN_MODE` en el backend; por defecto `open`, conversación
natural sin palabra de activación). El dashboard lo recibe en `session.started`/`turn.mode` y adapta
sus indicaciones. El protocolo también admite cambiarlo con el atributo de participante
`kognia.turn_mode` (el token incluye ese permiso), aunque la interfaz no expone ese control.

## Diseño

Tokens en `src/styles.css` (`--kv-*`). Los colores de datos (series, hablantes, rampa del mapa) son
pasos oscuros de una paleta validada para daltonismo y contraste sobre `--kv-surface`; la identidad de
cada hablante sigue un orden fijo (Hablante N → serie N).

## Scripts de verificación

```bash
node e2e/ui-check.mjs <carpeta>                                          # capturas 1920/1440/390, mapa, selección, consola
node e2e/voice-e2e.mjs <audio.wav> <salida.json> [--screens <carpeta>]   # conversación real con el agente
```

Ambos usan el Chrome instalado (`playwright-core`, sin descargar navegadores).
