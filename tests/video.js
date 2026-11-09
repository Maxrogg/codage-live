// Onglet Vidéo : ouverture d'un fichier, calage par mi-temps, saut à une action, « C'est ici », export, CSV, rechargement.
// Vidéo de test : ffmpeg -f lavfi -i testsrc2=size=640x360:rate=25 -t 180 -pix_fmt yuv420p -c:v libx264 /home/claude/work/test.mp4
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const VID = process.env.VID || '/home/claude/work/test.mp4';
const ok = (c, m) => { console.log((c ? 'OK   ' : 'ÉCHEC ') + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  await p.evaluate(() => {
    localStorage.clear(); FC.store.newMatch(); FC.store.setInfo({ adv: 'Test vidéo' });
    const add = (o) => FC.store.add(o);
    add({ kind: 'pass_deseq', team: 'N', x: 40, y: 30, x2: 70, y2: 34, ok: true, t: 30000 });
    add({ kind: 'shot', team: 'N', x: 95, y: 34, res: 'cadre', t: 62000 });
    add({ kind: 'perte', team: 'N', x: 50, y: 20, t: 75000 });
    FC.store.setMeta({ half: 2 });
    add({ kind: 'recup', team: 'N', x: 60, y: 40, t: 45 * 60000 + 20000 });
  });
  await p.click('#tab-video'); await p.waitForTimeout(200);
  ok((await p.$$eval('#vd-list li', l => l.length)) === 4, 'liste : 4 actions de Nous');
  ok((await p.textContent('#vd-k1')).includes('pas calée'), '1re mi-temps pas calée au départ');
  await p.setInputFiles('#vd-input', VID);
  await p.waitForFunction(() => document.getElementById('vd').readyState >= 1, null, { timeout: 15000 });
  // coup d'envoi 1re à 10 s, 2e à 120 s
  await p.evaluate(() => { document.getElementById('vd').currentTime = 10; }); await p.waitForTimeout(300);
  await p.click('#vd-ko1');
  await p.evaluate(() => { document.getElementById('vd').currentTime = 120; }); await p.waitForTimeout(300);
  await p.click('#vd-ko2');
  const v = await p.evaluate(() => FC.store.meta().video);
  ok(v.k1 === 10 && v.k2 === 120 && v.name === 'test.mp4', 'calage enregistré dans le match : ' + JSON.stringify(v));
  // clic sur la frappe (chrono 01:02) → vidéo 10 + 62 - 4 = 68 s
  await p.click('#vd-list li:nth-child(2)'); await p.waitForTimeout(600);
  let t = await p.evaluate(() => document.getElementById('vd').currentTime);
  ok(Math.abs(t - 68) < 1.5, 'saut à la frappe : vidéo à ' + t.toFixed(1) + ' s (attendu ~68)');
  // 2e mi-temps : récup à 45:20 → 120 + 20 - 4 = 136 s
  await p.keyboard.press('k'); await p.keyboard.press('k'); await p.waitForTimeout(600);
  t = await p.evaluate(() => document.getElementById('vd').currentTime);
  ok(Math.abs(t - 136) < 1.5, 'touche K ×2 → récup 2e mi-temps : ' + t.toFixed(1) + ' s (attendu ~136)');
  // « C'est ici » sur la frappe : on dit qu'elle se passe à 80 s → k1 = 80 - 62 = 18
  await p.click('#vd-list li:nth-child(2)'); await p.waitForTimeout(300);
  await p.evaluate(() => { const v = document.getElementById('vd'); v.pause(); v.currentTime = 80; }); await p.waitForTimeout(300);
  await p.click('#vd-here');
  ok((await p.evaluate(() => FC.store.meta().video.k1)) === 18, 'C\'est ici : k1 recalé à 18');
  await p.click('#vd-p1');
  ok((await p.evaluate(() => FC.store.meta().video.k1)) === 19, '+1 s : k1 = 19');
  // filtres
  await p.click('#vd-filters [data-k="shot"]'); ok((await p.$$eval('#vd-list li', l => l.length)) === 1, 'filtre Frappes : 1');
  await p.click('#vd-filters [data-k="all"]');
  // export et CSV
  const ex = await p.evaluate(() => FC.video.exportObj());
  ok(ex.actions.length === 4 && ex.actions[1].video_s === 81 && ex.actions[3].video_s === 140, 'export : temps vidéo des actions ' + ex.actions.map(a => a.video_s).join(', '));
  const csv = await p.evaluate(() => FC.store.toCSV());
  ok(csv.split('\n')[0].endsWith('video_s') && csv.split('\n')[2].endsWith(',81'), 'CSV : colonne video_s');
  await p.screenshot({ path: '/home/claude/work/video_tab.png' });
  // rechargement : calage gardé, fichier à rouvrir
  await p.reload(); await p.waitForTimeout(300); await p.click('#tab-video'); await p.waitForTimeout(200);
  ok((await p.evaluate(() => FC.store.meta().video.k1)) === 19, 'après rechargement : calage gardé');
  ok((await p.textContent('#vd-file')).includes('Rouvre'), 'après rechargement : invite à rouvrir le fichier');
  // l'onglet Codage n'est pas gêné (saisie clavier coupée hors Codage, réactivée au retour)
  await p.click('#tab-live'); await p.waitForTimeout(100);
  ok(await p.evaluate(() => !document.getElementById('view-live').hidden), 'retour à Codage');
  ok(errs.length === 0, 'aucune erreur JS ' + JSON.stringify(errs));
  await b.close();
})();
