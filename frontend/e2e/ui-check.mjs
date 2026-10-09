// Visual/functional check of the dashboard in headless Chrome against the local API.
// Usage: node e2e/ui-check.mjs <output-dir> [--url http://localhost:4200]
import { chromium } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const outDir = resolve(process.argv[2] ?? 'ui-check');
const urlIndex = process.argv.indexOf('--url');
const url = urlIndex > 0 ? process.argv[urlIndex + 1] : 'http://localhost:4200';
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const report = { viewports: {}, errors: [] };

for (const [name, viewport] of Object.entries({
  desktop_1920: { width: 1920, height: 1080 },
  laptop_1440: { width: 1440, height: 900 },
  mobile_390: { width: 390, height: 844 },
})) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  page.on('pageerror', (e) => consoleErrors.push(String(e)));
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'networkidle' });
  const loadMs = Date.now() - t0;
  await page.screenshot({ path: `${outDir}/${name}-inicio.png`, fullPage: false });

  if (name === 'mobile_390') await page.getByRole('button', { name: 'Datos y mapa' }).click();
  await page.getByRole('tab', { name: 'Mapa' }).click();
  const mapStart = Date.now();
  await page.locator('app-colombia-map path').nth(30).waitFor({ timeout: 30000 });
  await page.waitForFunction(() => !document.querySelector('app-map-panel .skeleton'), null, { timeout: 30000 });
  const mapMs = Date.now() - mapStart;
  const filled = await page.locator('app-colombia-map path').evaluateAll((paths) => ({
    total: paths.length,
    withData: paths.filter((p) => !p.getAttribute('fill')?.startsWith('url(')).length,
  }));
  await page.screenshot({ path: `${outDir}/${name}-mapa.png`, fullPage: false });

  const antioquia = page.locator('app-colombia-map path[aria-label^="Antioquia"]');
  await antioquia.focus();
  await page.keyboard.press('Enter');
  await page.getByText('Departamento seleccionado').waitFor({ timeout: 20000 });
  await page.locator('app-map-panel table tbody tr').first().waitFor({ timeout: 20000 });
  const stats = await page.locator('app-map-panel table tbody tr').first().innerText();
  await page.screenshot({ path: `${outDir}/${name}-seleccion.png`, fullPage: false });
  await page.keyboard.press('Escape');

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  report.viewports[name] = { loadMs, mapMs, filled, antioquiaRow: stats.replace(/\s+/g, ' '), horizontalOverflowPx: overflow, consoleErrors };
  await page.close();
}

writeFileSync(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
