// SPDX-License-Identifier: Apache-2.0
// Read-only layout proof for a local preview. This never establishes live readiness.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const base = process.env.PREVIEW_BASE_URL;
assert.ok(base && new URL(base).hostname === '127.0.0.1', 'preview must be local');
const source = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
assert.equal(source, process.env.EXPECTED_SOURCE_REVISION, 'test the exact admitted source');
const workingTreeDirty = Boolean(execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim());
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href);
const directory = process.env.RESPONSIVE_REPORT_DIR || 'reports/responsive-ui';
fs.mkdirSync(directory, { recursive: true });
const report = { schema: 'szl.responsive-preview/v1', source_revision: source, working_tree_dirty: workingTreeDirty, observed_at: new Date().toISOString(), scope: 'local layout preview; external data and authority are not qualified; zoom cases apply CSS zoom', live_verified: false, effects_executed: false, cases: [], complete: false };
const routes = (process.env.RESPONSIVE_ROUTES || '/').split(',');
const cases = [
  ['phone-320', 320, 800, 1], ['phone-375', 375, 812, 1],
  ['tablet-768', 768, 1024, 1], ['desktop-1024', 1024, 768, 1],
  ['desktop-1440', 1440, 900, 1], ['theatre-2560', 2560, 1440, 1],
  ['ultrawide-3440', 3440, 1440, 1], ['short-phone', 320, 450, 1],
  ['zoom-200', 1280, 900, 2], ['zoom-400', 1280, 900, 4],
  ['forced-colors', 375, 812, 1], ['no-script', 375, 812, 1],
];
let browser;
try {
  let listening = false;
  for (let attempt = 0; attempt < 80; attempt++) {
    try { if ((await fetch(base, { signal: AbortSignal.timeout(1000) })).ok) { listening = true; break; } } catch { /* Owned preview is still starting within the fixed deadline. */ }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert.ok(listening, 'local preview did not become available');
  browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE, args: ['--no-sandbox', '--disable-dev-shm-usage'] } : {}) });
  for (const route of routes) {
    const target = new URL(route, base);
    assert.equal(target.origin, new URL(base).origin, 'routes must stay in the local preview');
    for (const [name, width, height, zoom] of cases) {
      const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce', forcedColors: name === 'forced-colors' ? 'active' : 'none', javaScriptEnabled: name !== 'no-script' });
      const blockedRequests = [];
      await context.route('**/*', intercepted => {
        const request = intercepted.request();
        if (request.method() !== 'GET' || new URL(request.url()).origin !== target.origin) {
          blockedRequests.push({ method: request.method(), url: request.url() });
          return intercepted.abort('blockedbyclient');
        }
        return intercepted.continue();
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(target.href, { waitUntil: 'domcontentloaded' });
      await page.evaluate(async () => { await document.fonts.ready; });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (zoom !== 1) await page.evaluate(value => { document.documentElement.style.zoom = String(value); }, zoom);
      const measured = await page.evaluate(() => {
        const viewport = document.documentElement.clientWidth;
        const visible = element => {
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        };
        const identify = element => ({ tag: element.tagName, id: element.id, class: String(element.className).slice(0, 180) });
        const overlays = [...document.querySelectorAll('header,nav,aside,section,div')].filter(element => {
          if (!visible(element) || !['fixed', 'sticky'].includes(getComputedStyle(element).position) || !element.querySelector('a,button,input,textarea,select')) return false;
          const rect = element.getBoundingClientRect();
          return rect.width * rect.height > innerWidth * innerHeight * .88;
        }).map(identify);
        const clippedHeadings = [...document.querySelectorAll('h1,h2,h3')].filter(element => visible(element) && element.scrollWidth > element.clientWidth + 2).map(identify);
        const logo = document.querySelector('.native-mark img');
        const icon = logo ? { width: parseFloat(getComputedStyle(logo).width), height: parseFloat(getComputedStyle(logo).height), loaded: logo.complete && logo.naturalWidth > 0, clear_space: parseFloat(getComputedStyle(logo.parentElement).paddingLeft) } : null;
        const smallLabels = [...document.querySelectorAll('.state,.reading small,.stat small,.asset-foot,.family a')].filter(element => visible(element) && parseFloat(getComputedStyle(element).fontSize) < 12).map(identify);
        const hiddenNavigation = [...document.querySelectorAll('.family a')].filter(element => { const rect = element.getBoundingClientRect(); return rect.left < -1 || rect.right > innerWidth + 1; }).map(identify);
        const aliasMarkupLeaked = document.documentElement.dataset.nativeView === 'workspace' && /<\/?code>/.test(document.querySelector('.instrument').innerText);
        return { title: document.title, has_main: Boolean(document.querySelector('main')), h1_count: document.querySelectorAll('h1').length, text_characters: document.body.innerText.trim().length, native_icon: icon, small_evidence_labels: smallLabels, hidden_navigation: hiddenNavigation, alias_markup_leaked: aliasMarkupLeaked, overflow_px: Math.max(0, document.documentElement.scrollWidth - viewport), blocking_overlays: overlays, clipped_headings: clippedHeadings, error_overlay: Boolean(document.querySelector('[data-nextjs-dialog],vite-error-overlay')) };
      });
      const result = { route, case: name, width, height, zoom, http_status: response?.status() ?? null, ...measured, page_errors: errors, blocked_requests: blockedRequests };
      result.passed = result.http_status === 200 && measured.has_main && measured.h1_count === 1 && measured.text_characters > 100 && measured.overflow_px <= 1 && measured.blocking_overlays.length === 0 && measured.clipped_headings.length === 0 && measured.native_icon?.loaded && measured.native_icon.width === 32 && measured.native_icon.height === 32 && measured.native_icon.clear_space >= 8 && measured.small_evidence_labels.length === 0 && measured.hidden_navigation.length === 0 && !measured.alias_markup_leaked && !measured.error_overlay && errors.length === 0 && blockedRequests.length === 0;
      if (!result.passed || ['phone-320', 'desktop-1440', 'zoom-400'].includes(name)) {
        const filename = `${route.replace(/[^a-z0-9]+/gi, '-') || 'home'}--${name}.png`;
        await page.screenshot({ path: path.join(directory, filename) });
        result.screenshot = filename;
      }
      report.cases.push(result);
      await context.close();
    }
  }
  report.complete = true;
  assert.ok(report.cases.every(result => result.passed), 'responsive layout exceptions remain; inspect the retained report and screenshots');
} catch (error) {
  report.error = error.message;
  process.exitCode = 1;
} finally {
  await browser?.close();
  fs.writeFileSync(path.join(directory, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ source_revision: source, cases: report.cases.length, passed: report.cases.filter(result => result.passed).length, complete: report.complete, error: report.error ?? null }));
}
