const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  await p.evaluate(() => {
    let s = 11; const r = () => (s = (s * 16807) % 2147483647) / 2147483647, jit = (c, w) => c + (r() - .5) * w;
    for (let i = 0; i < 220; i++) {
      const team = r() < .5 ? 'N' : 'E', fx = x => team === 'N' ? x : 105 - x, u = r(), x = jit(team === 'N' ? 45 : 50, 50), y = jit(34, 50), t = i * 20000;
      const cl = (v, a, b2) => Math.max(a, Math.min(b2, v));
      if (u < .5) FC.store.add({ kind: 'pass', team, x: fx(cl(x, 3, 100)), y: cl(y, 3, 65), x2: fx(cl(x + 10, 3, 100)), y2: cl(y + 5, 3, 65), ok: r() < .75, t });
      else if (u < .65) FC.store.add({ kind: r() < .6 ? 'pass_deseq' : 'carry_deseq', team, x: fx(cl(x, 3, 90)), y: cl(y, 3, 65), x2: fx(cl(x + 20, 3, 100)), y2: cl(y + 8, 3, 65), ok: r() < .7, t });
      else if (u < .78) FC.store.add({ kind: 'recup', team, x: fx(cl(x, 3, 100)), y: cl(y, 3, 65), t });
      else if (u < .9) FC.store.add({ kind: 'perte', team, x: fx(cl(x, 3, 100)), y: cl(y, 3, 65), t });
      else FC.store.add({ kind: 'shot', team, x: fx(88 + r() * 10), y: 20 + r() * 28, res: ['hors', 'cadre', 'but'][Math.floor(r() * 3)], t });
    }
  });
  await p.click('#tab-analysis'); await p.waitForTimeout(400);
  await p.screenshot({ path: '/home/claude/test/an-all.png', fullPage: true });
  console.log('panels all:', await p.locator('#an-grid canvas').count());
  for (const k of ['rp', 'jeu', 'deseq', 'diff']) {
    await p.click('#an-presets button[data-k="' + k + '"]'); await p.waitForTimeout(250);
    console.log(k, 'panels', await p.locator('#an-grid canvas').count(), '| diff-key hidden:', await p.locator('#diff-key').isHidden());
    await p.screenshot({ path: '/home/claude/test/an-' + k + '.png', fullPage: false });
  }
  // clic sur petite carte -> préréglage
  await p.click('#an-presets button[data-k="all"]'); await p.waitForTimeout(200);
  await p.locator('#an-grid .pan').nth(2).click(); await p.waitForTimeout(200);
  console.log('après clic carte 3 (diff Nous):', await p.locator('#an-presets button.on').textContent());
  console.log('errors', errs); await b.close();
})();
