const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const tag = process.argv[2] || 'a';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  for (const scheme of ['light', 'dark']) {
    const p = await b.newPage({ viewport: { width: 1360, height: 900 }, colorScheme: scheme });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto('file:///home/claude/codage-live/index.html');
    await p.evaluate(() => {
      let s = 11; const r = (a, b) => { s = (s * 16807) % 2147483647; return a + (s / 2147483647) * (b - a); };
      FC.store.setMeta({ adv: 'FC Test' });
      const put = (e, min, h) => { FC.clock.set(min * 60000 + r(0, 50000)); FC.store.setMeta({ half: h }); FC.store.add(e); };
      for (let i = 0; i < 60; i++) put({ kind: 'pass', team: 'N', x: r(20, 90), y: r(8, 60), x2: r(25, 95), y2: r(8, 60), ok: r(0, 1) > .25 }, Math.floor(r(1, 44)), 1);
      for (let i = 0; i < 25; i++) put({ kind: 'pass', team: 'E', x: r(15, 85), y: r(8, 60), x2: r(10, 80), y2: r(8, 60), ok: r(0, 1) > .3 }, Math.floor(r(1, 44)), 1);
      for (let i = 0; i < 8; i++) put({ kind: 'pass_deseq', team: 'N', x: r(40, 70), y: r(10, 58), x2: r(75, 95), y2: r(20, 48), ok: r(0, 1) > .3 }, Math.floor(r(1, 44)), 1);
      for (let i = 0; i < 12; i++) put({ kind: 'recup', team: 'N', x: r(40, 95), y: r(8, 60) }, Math.floor(r(1, 44)), 1);
      for (let i = 0; i < 10; i++) put({ kind: 'perte', team: 'N', x: r(10, 60), y: r(8, 60) }, Math.floor(r(1, 44)), 1);
      for (let i = 0; i < 5; i++) put({ kind: 'shot', team: 'N', x: r(80, 96), y: r(20, 48), res: ['hors', 'cadre', 'but'][i % 3] }, Math.floor(r(5, 44)), 1);
      FC.store.setMeta({ half: 1 }); FC.clock.set(31 * 60000 + 12000);
    });
    for (const t of ['live', 'analysis', 'bilan', 'matches']) {
      await p.click('#tab-' + t); await p.waitForTimeout(350);
      await p.screenshot({ path: `R-${tag}-${scheme}-${t}.png`, fullPage: t !== 'live' });
    }
    console.log(scheme, errs);
    await p.close();
  }
  await b.close();
})();
