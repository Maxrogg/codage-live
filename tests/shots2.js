const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  for (const scheme of ['light', 'dark']) {
    const p = await b.newPage({ viewport: { width: 1360, height: 900 }, colorScheme: scheme });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto('file:///home/claude/codage-live/index.html');
    await p.evaluate(() => {
      let s = 11; const r = (a, b) => { s = (s * 16807) % 2147483647; return a + (s / 2147483647) * (b - a); };
      const M = 60000;
      const put = (e, min, h) => { FC.clock.set(min * M + r(0, 50000)); FC.store.setMeta({ half: h }); FC.store.add(e); };
      const att = (team, min, h, kind) => { // action offensive de team vers le but adverse
        const dir = team === 'N' ? 1 : -1, x0 = team === 'N' ? 60 : 45, y = r(15, 53);
        if (kind === 'surf') put({ kind: 'pass', team, x: x0 + 10 * dir, y, x2: team === 'N' ? 94 : 11, y2: 34, ok: true }, min, h);
        else if (kind === 'deseq') put({ kind: 'pass_deseq', team, x: x0, y, x2: x0 + 22 * dir, y2: 34, ok: true }, min, h);
        else if (kind === 'shot') put({ kind: 'shot', team, x: team === 'N' ? 92 : 13, y, res: ['hors', 'cadre'][Math.round(r(0, 1))] }, min, h);
        else if (kind === 'but') put({ kind: 'shot', team, x: team === 'N' ? 94 : 11, y: 34, res: 'but' }, min, h);
        else put({ kind: 'recup', team, x: team === 'N' ? 80 : 25, y }, min, h);
      };
      const plan = [[1, 0, 16, 'N', 1.6], [1, 17, 24, 'E', .4], [1, 25, 41, 'E', 1.3], [1, 42, 46, 'N', .7],
                    [2, 46, 58, 'E', 1.2], [2, 59, 68, 'N', .6], [2, 69, 88, 'N', 1.5]];
      plan.forEach(([h, a, z, team, rate]) => { for (let m = a; m <= z; m++) { const n = Math.random() < rate % 1 ? Math.ceil(rate) : Math.floor(rate); for (let i = 0; i < n; i++) att(team, m, h, ['surf', 'deseq', 'shot', 'recup', 'recup'][Math.floor(r(0, 5))]); } });
      att('N', 11, 1, 'but'); att('E', 34, 1, 'but'); att('E', 53, 2, 'but'); att('N', 78, 2, 'but'); att('N', 84, 2, 'but');
      FC.store.setMeta({ half: 2 });
    });
    await p.click('#tab-bilan'); await p.waitForTimeout(400);
    await p.screenshot({ path: scheme + '-mom.png', fullPage: true });
    console.log(scheme, await p.textContent('#mo-note'), errs);
    if (scheme === 'light') { await p.selectOption('#b-half', '1'); await p.waitForTimeout(200); await p.screenshot({ path: 'light-mom-h1.png' });
      await p.selectOption('#b-half', '0'); await p.selectOption('#mo-win', '10'); await p.waitForTimeout(200); await p.locator('#mo-chart').screenshot({ path: 'light-mom-w10.png' }); }
    await p.close();
  }
  await b.close();
})();
