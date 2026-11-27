// Barre Espace après un clic ailleurs (vrais clics et vraies touches) : elle doit toujours coder, jamais « cliquer » un bouton
// ni s'écrire dans un champ. Cas réel : on tape le nom de l'adversaire, puis on revient sur le terrain avec le pad.
// Lancer : node tests/lancer.js focus
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const ok = (c, m) => { console.log((c ? 'OK   ' : 'ÉCHEC ') + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  await p.evaluate(() => localStorage.clear()); await p.reload();
  const pass = async () => {                          // une passe au pad : Espace, déplacement, Espace
    await p.evaluate(() => window.scrollTo(0, 0));        // cliquer en bas de la colonne fait défiler la page : on remonte au terrain
    const box = await p.locator('#live').boundingBox();
    const n0 = await p.evaluate(() => FC.store.all().length);
    await p.mouse.move(box.x + 200, box.y + 150); await p.keyboard.press(' ');
    await p.mouse.move(box.x + 400, box.y + 200); await p.keyboard.press(' '); await p.waitForTimeout(500);
    return (await p.evaluate(() => FC.store.all().length)) - n0;
  };
  for (const id of ['btn-zero', 'btn-flip', 'btn-undo']) {
    await p.click('#' + id);
    const st = await p.evaluate(() => [FC.store.all().length, FC.store.meta().flip]);
    const d = await pass();
    const st2 = await p.evaluate(() => [FC.store.all().length - 1, FC.store.meta().flip]);
    ok(d === 1 && JSON.stringify(st) === JSON.stringify(st2), 'après un clic sur ' + id + ' : Espace code une passe, le bouton n\'est pas recliqué');
  }
  ok(await p.evaluate(() => FC.store.all().length) === 2, 'la remise à zéro n\'a pas été confirmée par Espace (3 passes, 1 annulée)');
  await p.click('#m-adv'); await p.keyboard.type('Annecy');
  ok(await pass() === 1 && await p.evaluate(() => FC.store.info().adv) === 'Annecy', 'après le nom de l\'adversaire : nom gardé sans espaces en plus, Espace code');
  await p.click('#m-hmin'); await p.keyboard.press('Escape');
  ok(await pass() === 1, 'après la liste Mi-temps : Espace code');
  ok(!errs.length, 'aucune erreur JS ' + JSON.stringify(errs));
  await b.close();
})();
