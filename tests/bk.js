const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const snaps = () => p.evaluate(() => FC.backup.list().map(s => s.reason + ':' + s.n));
  await p.evaluate(() => { FC.store.setInfo({ adv: 'Test BK' }); for (let i = 0; i < 45; i++) FC.store.add({ kind: 'recup', team: 'N', x: 40 + i % 5, y: 30, t: i * 1000 }); });
  console.log('après 45 événements :', await snaps());
  await p.evaluate(() => { for (let i = 0; i < 90; i++) FC.store.add({ kind: 'recup', team: 'N', x: 50, y: 30, t: 60000 + i * 1000 }); });
  const s2 = await snaps(); console.log('après 135 événements :', s2.length, 'points, autos de ce match <= 4:', s2.filter(x => x.startsWith('automatique')).length <= 4);
  // remise à zéro -> point « avant remise à zéro » avec 135 événements
  await p.click('#btn-zero'); await p.click('#btn-zero'); await p.waitForTimeout(150);
  console.log('événements après zéro:', await p.evaluate(() => FC.store.all().length), '| dernier point:', (await snaps())[0]);
  // restauration
  await p.click('#tab-matches'); await p.waitForTimeout(200);
  console.log('lignes de points:', await p.locator('#snap-list tbody tr').count());
  const row = p.locator('#snap-list tr', { hasText: 'avant remise à zéro' }).first(); await row.locator('button').click(); await p.waitForTimeout(200);
  console.log('matchs:', await p.evaluate(() => FC.store.matches().map(m => m.info.adv + ':' + m.events.length).join(' ; ')));
  // suppression -> point
  await p.locator('button[data-del]').first().click(); await p.locator('button.danger[data-del]').click(); await p.waitForTimeout(150);
  console.log('avant suppression présent:', (await snaps()).some(x => x.startsWith('avant suppression')));
  // échec de stockage -> pastille d'alerte
  await p.evaluate(() => { const orig = Storage.prototype.setItem; window.__orig = orig; Storage.prototype.setItem = function (k, v) { if (k.indexOf('fc2-m-') === 0) throw new DOMException('full', 'QuotaExceededError'); return orig.call(this, k, v); }; });
  await p.evaluate(() => FC.store.add({ kind: 'recup', team: 'N', x: 50, y: 30 }));
  console.log('pastille en échec:', await p.textContent('#save-state'));
  await p.evaluate(() => { Storage.prototype.setItem = window.__orig; FC.store.add({ kind: 'recup', team: 'N', x: 50, y: 30 }); });
  console.log('pastille rétablie:', await p.textContent('#save-state'));
  await p.screenshot({ path: '/home/claude/test/bk.png', fullPage: true });
  console.log('errors', errs); await b.close();
})();
