const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  for (const scheme of ['light', 'dark']) {
  const p = await b.newPage({ viewport: { width: 1360, height: 900 }, colorScheme: scheme }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const box = await p.locator('#live').boundingBox();
  const at = async (fx, fy) => { const s = await p.evaluate(([x, y]) => { const g = document.getElementById('live')._g; return FC.pitch.toScreen(g, x, y, FC.store.meta().flip); }, [fx, fy]); await p.mouse.move(box.x + s[0], box.y + s[1]); };
  await at(104, 1); await p.keyboard.down('f'); await p.keyboard.press(' '); await p.keyboard.up('f');          // corner Nous
  await at(97, 30); await p.keyboard.down('r'); await p.keyboard.press(' '); await p.keyboard.up('r'); await p.waitForTimeout(400); await p.keyboard.press('c');
  await at(1, 67); await p.keyboard.down('f'); await p.keyboard.down(' '); await p.waitForTimeout(450); await p.keyboard.up(' '); await p.keyboard.up('f');   // corner Eux (maintenu)
  await at(70, 30); await p.keyboard.down('f'); await p.keyboard.press(' '); await p.keyboard.up('f');            // coup franc Nous
  const evs = await p.evaluate(() => FC.store.all().map(e => e.team + ':' + e.kind + ':' + (e.cpa || e.res || '')).join(' '));
  console.log(scheme, evs, '| récents :', (await p.textContent('#recent')).slice(0, 120));
  await p.evaluate(() => { for (let i = 0; i < 6; i++) FC.store.add({ kind: 'shot', team: 'N', x: 80 + i * 4, y: 20 + i * 5, res: ['hors', 'cadre'][i % 2] }); });
  await p.click('#tab-analysis'); await p.click('text=Frappes & CPA'); await p.waitForTimeout(300);
  await p.screenshot({ path: scheme + '-cpa.png' });
  console.log(errs);
  await p.close(); }
  await b.close();
})();
