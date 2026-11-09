// Import du fichier produit par ia/analyser.py (match_ia.json) dans l'appli : le match apparaît, cartes et Vidéo fonctionnent.
// Préparer : cd ia && python3 analyser.py /home/claude/work/OFF_PLACEE.mp4 --nous noir  (ou test_ia.py, qui affiche le chemin)
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const F = process.env.IA || '/home/claude/work/resultats_OFF_PLACEE/match_ia.json';
const ok = (c, m) => { console.log((c ? 'OK   ' : 'ÉCHEC ') + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const txt = fs.readFileSync(F, 'utf8');
  const r = await p.evaluate((t) => { localStorage.clear(); const r = FC.store.importFile(t); const m = FC.store.matches().find(x => x.id.startsWith('ia-')); FC.store.switchTo(m.id); return [r, FC.store.all().length, FC.store.info().adv]; }, txt);
  ok(r[0].added === 1 && r[1] > 0, 'match IA importé : ' + r[1] + ' actions, « ' + r[2] + ' »');
  await p.click('#tab-analysis'); await p.waitForTimeout(300);
  await p.click('#tab-bilan'); await p.waitForTimeout(300);
  await p.click('#tab-video'); await p.waitForTimeout(300);
  ok((await p.$$eval('#vd-list li', l => l.length)) > 0, 'onglet Vidéo : actions listées');
  ok((await p.textContent('#vd-k1')).includes('calée'), 'onglet Vidéo : calage repris du fichier IA');
  ok(errs.length === 0, 'aucune erreur JS ' + JSON.stringify(errs));
  await b.close();
})();
