const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  for (const scheme of ['light', 'dark']) {
    const p = await b.newPage({ viewport: { width: 1360, height: 900 }, colorScheme: scheme });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto('file:///home/claude/codage-live/index.html');
    await p.evaluate(() => {
      let s = 7; const r = (a, b) => { s = (s * 16807) % 2147483647; return a + (s / 2147483647) * (b - a); };
      const put = (e, min, h) => { FC.clock.set(min * 60000 + r(0, 50000)); FC.store.setMeta({ half: h }); FC.store.add(e); };
      for (let i = 0; i < 70; i++) put({ kind: 'pass', team: 'N', x: r(20, 90), y: r(8, 60), x2: r(25, 95), y2: r(8, 60), ok: r(0, 1) > .25 }, Math.floor(r(1, 40)), 1);
      // duels : gagnés plutôt en haut/avant, perdus plutôt dans notre moitié
      for (let i = 0; i < 18; i++) put({ kind: 'recup', team: 'N', x: r(55, 95), y: r(8, 60) }, Math.floor(r(1, 40)), 1);
      for (let i = 0; i < 16; i++) put({ kind: 'perte', team: 'N', x: r(10, 50), y: r(8, 60) }, Math.floor(r(1, 40)), 1);
      for (let i = 0; i < 6; i++) { put({ kind: 'recup', team: 'N', x: r(10, 50), y: r(8, 60) }, 20, 2); put({ kind: 'perte', team: 'N', x: r(55, 95), y: r(8, 60) }, 21, 2); }
      FC.store.setMeta({ half: 2 });
    });
    await p.click('#tab-analyse').catch(async () => { await p.click('text=Analyse'); });
    await p.waitForTimeout(300);
    const info = await p.evaluate(() => { const s = FC.stats.summary(FC.store.current().events, 'N', 0); return s.duels; });
    console.log(scheme, 'duels', JSON.stringify(info));
    await p.screenshot({ path: scheme + '-all.png', fullPage: true });
    const opts = await p.$$eval('select option', o => o.map(x => x.value + ':' + x.textContent).join(' | '));
    console.log(opts.slice(0, 300));
    console.log(errs);
    await p.close();
  }
  await b.close();
})();
