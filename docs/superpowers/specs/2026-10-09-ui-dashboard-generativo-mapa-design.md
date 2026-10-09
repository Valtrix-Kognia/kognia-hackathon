# Kognia Voice — rediseño UI, dashboard generativo y mapa de Colombia

Fecha: 2026-10-09 · Estado: aprobado por la usuaria en conversación ("adelante con los cambios").

## Objetivo

Interfaz oscura y profesional donde cada elemento visual está conectado a datos reales:
voz → comprensión → consulta Socrata → respuesta → visualización → exploración.

## Restricciones

- Solo frontend. No se modifica el backend, `environment.production.ts`, los contratos de
  eventos (`RealtimeEvent` y payloads) ni el pipeline de audio.
- `ng test` y `ng build` deben seguir pasando.
- Ningún dato simulado; Gemini no produce gráficos.

## Decisiones

1. **Visualizaciones derivadas en frontend.** Un `VisualizationSpecBuilder` puro convierte cada
   `ips.query.completed` en especificaciones tipadas (`metric`, `table`, `bar_chart`,
   `horizontal_bar`, `donut_chart`, `line_chart`, `colombia_map`). La validación Pydantic no
   aplica porque el backend no cambia; el contrato es TypeScript y se prueba con unit tests.
   `line_chart` no se usa: el dataset no tiene dimensión temporal.
2. **Gráficos en SVG propio**, accesibles (tooltip, tabla alternativa, texto + icono), sin
   librería de gráficos.
3. **Mapa** con `d3-geo` (carga diferida). GeoJSON geoBoundaries gbOpen COL ADM1
   (OpenStreetMap, ODbL 1.0, 33 unidades con ISO 3166-2), simplificado solo por redondeo de
   coordenadas. Catálogo controlado nombre Socrata → ISO. Los distritos (Barranquilla,
   Cartagena, Santa Marta, Cali, Buenaventura) se suman a su departamento solo para sedes y
   registros (aditivos); prestadores únicos no se mapean (no aditivos). Sin datos ≠ cero.
   Datos iniciales: `GET /api/v1/ips/group?dimension=departamento` (API propia → Socrata).
   Se actualiza con respuestas del agente agrupadas por departamento. Clic: selección, zoom y
   estadísticas del departamento vía `/count` y `/group?dimension=naturaleza`.
4. **Evidencia:** herramienta, filtros, fecha, unidad, advertencias, insignia de caché
   (nota de agregados), separación datos verificados / resumen generado / limitaciones.
   No se muestra SoQL (el backend no lo envía).
5. **Accesibilidad:** subtítulos, entrada por texto (`lk.chat`, ya atendido por el agente),
   corrección de transcripción guardada aparte del original, tamaño de letra, teclado,
   foco visible, `prefers-reduced-motion`.
6. **Layout:** escritorio en tres columnas (voz · análisis con pestañas · transcripción);
   móvil con orbe primero y barra de pestañas.

## Validación

Unit tests (builder, catálogo geográfico, escala), `ng build` con presupuesto, capturas en
1920/1440/390 px con Chrome headless, consola sin errores, una corrida e2e corta para
confirmar que la latencia de voz no empeora.
