const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); await p.addInitScript(()=>document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('details').forEach(d=>d.open=true)));
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await p.goto('file:///home/claude/codage-live/index.html'); await p.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
  const box = await p.locator('#live').boundingBox();
  const at = (x, y) => [box.x + 14 + x * ((box.width - 28) / 105), box.y + 14 + y * ((box.width - 28) / 105)];
  // 1. chrono auto au premier geste
  console.log('chrono avant', await p.evaluate(() => FC.clock.isRunning()));
  await p.mouse.click(...at(50, 34));
  await p.mouse.move(...at(30, 30)); await p.keyboard.press('Space'); await p.waitForTimeout(100);
  console.log('chrono après 1er point', await p.evaluate(() => FC.clock.isRunning()));
  await p.mouse.move(...at(60, 30)); await p.keyboard.press('Space'); await p.waitForTimeout(500);
  console.log('events', await p.evaluate(() => FC.store.all().length), 'état', await p.textContent('#save-state'));
  // 2. carte Match
  await p.fill('#m-adv', 'FC Annecy'); await p.fill('#m-sn', '3'); await p.fill('#m-se', '1');
  console.log('badge', await p.textContent('#m-res'));
  // saisie dans un champ ne déclenche pas de geste
  await p.focus('#m-adv'); await p.keyboard.press('Space'); await p.keyboard.type('q');
  console.log('events après frappe clavier dans champ', await p.evaluate(() => FC.store.all().length));
  // 3. jeu de données synthétique : 6 matchs
  await p.evaluate(() => {
    function rnd(seed) { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; }
    const cfg = [['Annecy', 3, 1, .8], ['Lyon B', 2, 0, .75], ['Grenoble', 1, 1, .6], ['Bourg', 0, 2, .55], ['Thonon', 1, 3, .5], ['Valence', 2, 1, .78]];
    cfg.forEach(([adv, sn, se, q], k) => {
      FC.store.newMatch(); const r = rnd(7 + k * 13); FC.store.setInfo({ adv, sn, se, date: '2026-10-' + String(5 + k * 7).padStart(2, '0') });
      for (let i = 0; i < 90; i++) {
        const half = i < 45 ? 1 : 2; FC.store.setMeta({ half }); const t = Math.floor(r() * 45 * 60000) + (half === 2 ? 45 * 60000 : 0);
        const team = r() < .5 ? 'N' : 'E', dir = team === 'N' ? 1 : -1, x = 20 + r() * 60, y = 8 + r() * 52;
        const u = r();
        if (u < .55) FC.store.add({ kind: 'pass', team, x: team === 'N' ? x : 105 - x, y, x2: team === 'N' ? Math.min(100, x + 12) : 105 - Math.min(100, x + 12), y2: y + 4, ok: r() < (team === 'N' ? q : .65), t });
        else if (u < .7) FC.store.add({ kind: 'pass_deseq', team, x: team === 'N' ? x : 105 - x, y, x2: team === 'N' ? Math.min(100, x + 25) : 105 - Math.min(100, x + 25), y2: 34, ok: r() < q, t });
        else if (u < .8) FC.store.add({ kind: 'recup', team, x: team === 'N' ? x : 105 - x, y, t });
        else if (u < .9) FC.store.add({ kind: 'perte', team, x: team === 'N' ? x : 105 - x, y, t });
        else FC.store.add({ kind: 'shot', team, x: team === 'N' ? 88 + r() * 10 : 17 - r() * 10, y: 20 + r() * 28, res: ['hors', 'cadre', 'but'][Math.floor(r() * 3)], t });
      }
    });
    FC.store.switchTo(FC.store.matches().filter(m => m.info.adv === 'Annecy')[0].id);
  });
  await p.click('#tab-matches'); await p.waitForTimeout(300);
  await p.screenshot({ path: '/home/claude/test/m-matchs.png', fullPage: true });
  console.log('cmp head:', (await p.textContent('#cmp table thead')).replace(/\s+/g, ' '));
  console.log('lib rows:', await p.locator('#lib-list tbody tr').count());
  // 4. bilan + courbe
  await p.click('#tab-bilan'); await p.waitForTimeout(300);
  await p.screenshot({ path: '/home/claude/test/m-bilan.png', fullPage: true });
  await p.selectOption('#t-metric', 'perte'); await p.waitForTimeout(150);
  console.log('rects', await p.locator('#t-chart rect').count(), '| note:', await p.textContent('#t-note'));
  // 5. suppression armée
  await p.click('#tab-matches');
  const before = await p.locator('#lib-list tbody tr').count();
  await p.locator('button[data-del]').last().click(); await p.waitForTimeout(100);
  console.log('après 1er clic supprimer:', await p.locator('#lib-list tbody tr').count(), '(attendu', before + ')');
  await p.locator('button.danger[data-del]').click(); await p.waitForTimeout(150);
  console.log('après confirmation:', await p.locator('#lib-list tbody tr').count());
  // 6. persistance après rechargement
  const ids = await p.evaluate(() => FC.store.matches().length);
  await p.reload(); await p.waitForTimeout(500);
  console.log('matchs avant/après reload', ids, await p.evaluate(() => FC.store.matches().length), '| save-state:', await p.textContent('#save-state'));
  // 7. nouveau match réutilise un match vide
  await p.click('#btn-reset'); await p.click('#btn-reset');
  console.log('matchs après 2x nouveau:', await p.evaluate(() => FC.store.matches().length));
  await p.click('#tab-live'); await p.screenshot({ path: '/home/claude/test/m-live.png', fullPage: true });
  console.log('errors:', errs);
  await b.close();
})();
