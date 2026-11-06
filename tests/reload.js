// Rechargement pendant le match (chrono), types inconnus, date locale.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, timezoneId: 'Europe/Paris' });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const box = await p.locator('#live').boundingBox();
  await p.mouse.move(box.x + 300, box.y + 150); await p.keyboard.press('z');      // 1er geste : le chrono démarre
  await p.evaluate(() => { FC.clock.set(20 * 60000); FC.clock.start(); });        // on est à 20'
  await p.mouse.move(box.x + 320, box.y + 170); await p.keyboard.press('z');
  await p.waitForTimeout(1500);
  await p.reload(); await p.waitForTimeout(300);
  const st = await p.evaluate(() => ({ run: FC.clock.isRunning(), t: FC.clock.now() }));
  console.log('après reload : chrono tourne', st.run, '| temps', Math.round(st.t / 1000), 's (attendu ≥ 1201)');
  if (!st.run || st.t < 1201000) throw new Error('chrono non repris');
  // pause puis reload : doit rester arrêté
  await p.click('#btn-clock'); await p.reload(); await p.waitForTimeout(200);
  console.log('pause + reload : chrono tourne', await p.evaluate(() => FC.clock.isRunning()));
  // ancien type « dribble » dans une sauvegarde importée
  await p.evaluate(() => { FC.store.importFile(JSON.stringify({ matches: [{ id: 'x1', info: { adv: 'Vieux' }, upd: Date.now() + 5,
    events: [{ id: 1, kind: 'dribble', team: 'N', x: 50, y: 30, half: 1, t: 0 }, { id: 2, kind: 'recup', team: 'N', x: 60, y: 30, half: 1, t: 1000 }] }] })); FC.store.switchTo('x1'); });
  for (const t of ['analysis', 'bilan', 'matches', 'live']) { await p.click('#tab-' + t); await p.waitForTimeout(100); }
  const lg = await p.evaluate(() => [FC.store.all().length, FC.store.current().legacy.length, JSON.parse(FC.store.allJSON()).matches.find(m => m.id === 'x1').legacy[0].kind]);
  console.log('dribble : événements', lg[0], '| mis de côté', lg[1], lg[2], '(gardé dans la sauvegarde)');
  // date locale : 00:30 à Paris le 7/11 = 23:30 UTC le 6/11
  const d = await p.evaluate(() => { const real = Date; const fixed = new real('2026-11-06T23:30:00Z').getTime();
    window.Date = class extends real { constructor(...a) { a.length ? super(...a) : super(fixed); } static now() { return fixed; } };
    const n = FC.store.newMatch(); FC.store.setInfo({ adv: 'tmp' }); window.Date = real; return n.info.date; });
  console.log('date à 00:30 (Paris) :', d, d === '2026-11-07' ? 'OK' : 'FAUX');
  console.log('errors', errs); await b.close();
  if (errs.length || d !== '2026-11-07') process.exit(1);
})();
