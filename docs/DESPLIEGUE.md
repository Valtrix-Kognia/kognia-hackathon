# Despliegue

Tres piezas independientes. Estado al escribir esta guía: **ninguna está desplegada todavía**; la
API se verificó instalándola en un entorno limpio, y las imágenes Docker no se han construido en
esta máquina (Docker Desktop no estaba en ejecución).

| Pieza | Imagen / artefacto | Destino sugerido |
|---|---|---|
| Worker de voz | `backend/Dockerfile` | LiveKit Cloud Agents |
| API HTTP | `backend/Dockerfile.api` | Azure Container Apps (o App Service con contenedor) |
| Frontend | `frontend/dist/frontend/browser` | Azure Static Web Apps |

## 1. Worker de voz en LiveKit Cloud

LiveKit Cloud inyecta `LIVEKIT_URL`, `LIVEKIT_API_KEY` y `LIVEKIT_API_SECRET` al agente; solo hay que
pasar los secretos propios.

```bash
cd backend
lk cloud auth                                   # elige el proyecto de LiveKit
printf 'SOCRATA_APP_TOKEN=%s\n' "<token>" > agent.secrets   # ignorado por git (*.secrets); bórralo al terminar
lk agent create --secrets-file agent.secrets    # primera vez: crea livekit.toml y despliega
lk agent deploy                                 # versiones siguientes
lk agent status
lk agent logs                                   # debe aparecer "registered worker" con agent_name kognia-voice
```

Notas:

- La imagen usa Python 3.12, instala el extra `agent` (LiveKit Agents, ai-coustics, pysentimiento,
  torch CPU) y descarga en la construcción los modelos del detector de turnos y de emociones.
- El nombre del agente (`LIVEKIT_AGENT_NAME`, por defecto `kognia-voice`) debe coincidir con el que
  despacha la API en el token.
- Versiona `livekit.toml` tras el primer `lk agent create`.

## 2. API en Azure Container Apps

```bash
cd backend
az group create -n kognia-rg -l eastus
az acr create -n kogniaacr -g kognia-rg --sku Basic --admin-enabled true
az acr build -r kogniaacr -t kognia-api:1 -f Dockerfile.api .
az containerapp env create -n kognia-env -g kognia-rg -l eastus
az containerapp create -n kognia-voice-api -g kognia-rg --environment kognia-env \
  --image kogniaacr.azurecr.io/kognia-api:1 --registry-server kogniaacr.azurecr.io \
  --target-port 8000 --ingress external --min-replicas 1 \
  --secrets livekit-key=<API_KEY> livekit-secret=<API_SECRET> socrata-token=<TOKEN> \
  --env-vars LIVEKIT_URL=wss://<proyecto>.livekit.cloud \
             LIVEKIT_API_KEY=secretref:livekit-key LIVEKIT_API_SECRET=secretref:livekit-secret \
             SOCRATA_APP_TOKEN=secretref:socrata-token \
             CORS_ORIGINS=https://<frontend>.azurestaticapps.net
```

- `CORS_ORIGINS` acepta una lista separada por comas o JSON.
- El límite de solicitudes es en memoria por réplica: con varias réplicas el límite efectivo se multiplica.
- Verificación: `curl https://<api>/health` → `{"status":"ok","voice_configured":true,...}` y
  `curl -X POST https://<api>/api/v1/sessions` → 201 con `livekit_url` del proyecto correcto.

## 3. Frontend en Azure Static Web Apps

`frontend/src/environments/environment.production.ts` define `apiBaseUrl`
(`https://kognia-voice-api.azurewebsites.net`). Debe coincidir con la URL pública de la API; si
cambia, actualízalo antes de compilar.

```bash
cd frontend
npm ci
npx ng build                                   # salida: dist/frontend/browser
npx @azure/static-web-apps-cli deploy dist/frontend/browser \
  --deployment-token <token-del-recurso-SWA> --env production
```

`public/staticwebapp.config.json` redirige cualquier ruta a `index.html` (aplicación de una página).

## 4. Verificación tras desplegar

1. Abrir la URL pública desde otro equipo y comprobar en la consola del navegador que no hay errores.
2. Pestaña **Mapa**: deben pintarse 33 departamentos (usa la API).
3. **Iniciar conversación**, autorizar micrófono, decir “Kognia, ¿cuántas IPS hay en el Quindío?”:
   respuesta hablada con 139 prestadores y 148 sedes, gráfico en Visualización y evidencia.
4. `lk agent logs` sin errores de `inference_quota_exceeded`; si aparecen, la cuota de LiveKit
   Inference del proyecto se agotó (ampliar el plan o usar otro proyecto).
5. Opcional: `node e2e/voice-e2e.mjs <wav> salida.json --url https://<frontend>` y
   `python -m bench.e2e_report salida.json <referencia>` para medir decisiones y latencia en producción.
