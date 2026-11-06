const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, acceptDownloads: true });
  const p = await ctx.newPage(); await p.addInitScript(() => { document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('details').forEach(d => d.open = true)); }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://localhost:8765/index.html');
  await p.evaluate(() => navigator.serviceWorker.ready); await p.waitForTimeout(800);
  console.log('SW actif:', await p.evaluate(() => !!navigator.serviceWorker.controller || navigator.serviceWorker.ready.then(r => !!r.active)));
  console.log('manifest:', await p.evaluate(() => fetch('manifest.webmanifest').then(r => r.json()).then(j => j.name)));
  console.log('caches:', await p.evaluate(async () => { const k = await caches.keys(); const c = await caches.open(k[0]); return k[0] + ' ' + (await c.keys()).length + ' fichiers'; }));
  // coupe le réseau, recharge
  await ctx.setOffline(true); await p.reload(); await p.waitForTimeout(500);
  console.log('hors ligne, page chargée:', await p.evaluate(() => typeof FC !== 'undefined' && !!FC.ui), '| titre:', await p.title());
  // code un événement hors ligne, recharge, vérifie la sauvegarde
  const box = await p.locator('#live').boundingBox();
  await p.mouse.move(box.x + 200, box.y + 150); await p.keyboard.press('z'); await p.waitForTimeout(100);
  await p.reload(); await p.waitForTimeout(400);
  console.log('événements après reload hors ligne:', await p.evaluate(() => FC.store.all().length), '| état:', await p.textContent('#save-state'));
  // téléchargement natif (CSV) + import
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#btn-dl-csv')]);
  console.log('téléchargement:', dl.suggestedFilename());
  const [dl2] = await Promise.all([p.waitForEvent('download'), p.click('#btn-dl-all')]);
  const path = await dl2.path(); const txt = require('fs').readFileSync(path, 'utf8'); console.log('sauvegarde JSON:', JSON.parse(txt).matches.length, 'match(s)');
  // import : un autre match avec un id inconnu + un match plus récent du même id
  const imp = { version: 2, matches: [{ id: 'm_import1', info: { adv: 'Importé', date: '2026-10-01', sn: 2, se: 0 }, events: [{ id: 1, kind: 'recup', team: 'N', x: 50, y: 30, half: 1, t: 0 }], seq: 1, meta: { half: 1, elapsed: 0, flip: false }, upd: Date.now() }] };
  require('fs').writeFileSync('/tmp/imp.json', JSON.stringify(imp));
  await p.setInputFiles('#file-import', '/tmp/imp.json'); await p.waitForTimeout(300);
  console.log('après import:', await p.evaluate(() => FC.store.matches().map(m => m.info.adv + ':' + m.events.length).join(' ; ')));
  await p.click('#tab-matches'); console.log('lignes liste:', await p.locator('#lib-list tbody tr').count());
  await p.screenshot({ path: '/home/claude/test/pwa.png' });
  console.log('errors', errs); await b.close();
})();
