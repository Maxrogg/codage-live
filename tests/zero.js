const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  await p.evaluate(() => { FC.store.setInfo({ adv: 'X', sn: 2, se: 1 }); FC.clock.start(); for (let i = 0; i < 5; i++) FC.store.add({ kind: 'recup', team: 'N', x: 50, y: 30 }); });
  await p.waitForTimeout(1200);
  console.log('avant:', await p.evaluate(() => [FC.store.all().length, FC.clock.isRunning(), FC.store.info().sn]));
  await p.click('#btn-zero'); console.log('1er clic:', await p.textContent('#btn-zero'), '| events', await p.evaluate(() => FC.store.all().length));
  await p.click('#btn-zero'); await p.waitForTimeout(200);
  console.log('après:', await p.evaluate(() => [FC.store.all().length, FC.clock.isRunning(), FC.clock.now(), FC.store.info().sn, FC.store.info().adv, FC.store.meta().half]), '| clock:', await p.textContent('#clock'));
  await p.reload(); await p.waitForTimeout(300);
  console.log('après reload:', await p.evaluate(() => [FC.store.all().length, FC.store.matches().length]), 'errors', errs); await b.close();
})();
