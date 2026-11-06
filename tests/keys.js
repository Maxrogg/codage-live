const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const box = await p.locator('#live').boundingBox();
  const at = (x, y) => [box.x + 14 + x * ((box.width - 28) / 105), box.y + 14 + y * ((box.width - 28) / 105)];
  const wait = ms => p.waitForTimeout(ms);
  const dump = async () => p.evaluate(() => FC.store.all().map(e => e.team + ':' + e.kind + (e.res ? ':' + e.res : '') + '@' + Math.round(e.x) + ',' + Math.round(e.y)).join(' | '));
  await p.mouse.click(...at(50, 34));
  await p.mouse.move(...at(30, 20)); await p.keyboard.press('z'); await wait(50);
  await p.mouse.move(...at(70, 40)); await p.keyboard.press('e'); await wait(50);
  console.log('Z puis E :', await dump());
  // maintenir Z ne répète pas
  await p.mouse.move(...at(40, 10)); await p.keyboard.down('z'); await wait(600); await p.keyboard.up('z');
  console.log('Z maintenu =', await p.evaluate(() => FC.store.all().length), 'événements (attendu 3)');
  // frappe : R + Espace cadrée (double appui) puis C = but
  await p.mouse.move(...at(95, 34)); await p.keyboard.down('r'); await p.keyboard.press('Space'); await p.keyboard.press('Space'); await p.keyboard.up('r'); await wait(450);
  await p.keyboard.press('c'); await wait(50);
  console.log('frappe R :', (await dump()).split(' | ').pop());
  // E ne doit plus faire de frappe ; Q/W ne font plus rien
  const n0 = await p.evaluate(() => FC.store.all().length); await p.keyboard.press('q'); await p.keyboard.press('w'); await wait(100);
  console.log('Q/W ignorés :', await p.evaluate(() => FC.store.all().length) === n0);
  // stats : Z a créé 1 récup N + 1 perte E ; E a créé 1 perte N + 1 récup E
  console.log(await p.evaluate(() => { const a = FC.stats.summary(FC.store.all(), 'N', 0), b = FC.stats.summary(FC.store.all(), 'E', 0); return 'N récup ' + a.recup.n + ' perte ' + a.perte.n + ' | E récup ' + b.recup.n + ' perte ' + b.perte.n; }));
  // hors terrain : pas d'événement
  await p.mouse.move(5, 5); await p.keyboard.press('z'); console.log('curseur hors terrain -> ', await p.evaluate(() => FC.store.all().length) === n0 ? 'ignoré' : 'ajouté');
  // Ctrl+Z = annuler (pas une récup)
  await p.mouse.move(...at(50, 34)); await p.keyboard.press('Control+z'); await wait(50);
  console.log('Ctrl+Z annule :', await p.evaluate(() => FC.store.all().length) === n0 - 1);
  await p.screenshot({ path: '/home/claude/test/keys.png' });
  console.log('errors', errs); await b.close();
})();
