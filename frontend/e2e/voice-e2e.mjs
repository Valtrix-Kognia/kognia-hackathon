// End-to-end voice run in a real Chrome: a WAV file acts as the microphone, the dashboard
// talks to the live agent through LiveKit, and the session export is saved for scoring.
// Usage: node e2e/voice-e2e.mjs <wav> <out.json> [--mode wake_word|open] [--url http://localhost:4200]
import { chromium } from 'playwright-core';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const [, , wavArg, outArg, ...rest] = process.argv;
if (!wavArg || !outArg) {
  console.error('Uso: node e2e/voice-e2e.mjs <wav> <salida.json> [--mode wake_word|open] [--url ...]');
  process.exit(2);
}
const option = (name, fallback) => {
  const index = rest.indexOf(`--${name}`);
  return index >= 0 ? rest[index + 1] : fallback;
};
const url = option('url', 'http://localhost:4200');
const mode = option('mode', 'wake_word');
const chromePath = option('chrome', 'C:/Program Files/Google/Chrome/Application/chrome.exe');
const wav = resolve(wavArg);

const header = readFileSync(wav);
const byteRate = header.readUInt32LE(28);
const dataBytes = header.length - 44;
const durationS = dataBytes / byteRate;

const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
  args: [
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${wav}%noloop`,
    '--autoplay-policy=no-user-gesture-required',
  ],
});
const context = await browser.newContext({ permissions: ['microphone'], acceptDownloads: true });
const page = await context.newPage();
const consoleLines = [];
page.on('console', (msg) => consoleLines.push(`[${msg.type()}] ${msg.text()}`));

await page.goto(url, { waitUntil: 'networkidle' });
await page.getByRole('radio', { name: mode === 'open' ? 'Conversación abierta' : 'Activación “Kognia”' }).click();
const started = Date.now();
await page.getByRole('button', { name: 'Iniciar conversación' }).click();
try {
  await page.locator('app-connection-status').getByText('Conectado').waitFor({ timeout: 30000 });
} catch (error) {
  await page.screenshot({ path: resolve(outArg).replace(/\.json$/, '.fallo.png'), fullPage: true });
  writeFileSync(resolve(outArg).replace(/\.json$/, '.console.log'), consoleLines.join('\n'));
  console.error('No se conectó:', String(error), consoleLines.slice(-15).join('\n'));
  await browser.close();
  process.exit(1);
}
console.log(`conectado en ${Date.now() - started} ms; reproduciendo ${durationS.toFixed(1)} s de audio`);

await page.waitForTimeout((durationS + 25) * 1000);

const downloadPromise = page.waitForEvent('download');
await page.getByRole('button', { name: 'Exportar' }).click();
const download = await downloadPromise;
await download.saveAs(resolve(outArg));
writeFileSync(resolve(outArg).replace(/\.json$/, '.console.log'), consoleLines.join('\n'));
console.log(`exportado: ${outArg}`);

await page.getByRole('button', { name: 'Finalizar' }).click().catch(() => undefined);
await browser.close();
