// Saisie et mi-temps (nov. 2026) : Rétablir (Ctrl+Y), mi-temps qui change de côté, retour en 1re en 2 clics,
// durée des mi-temps (40 / 45) et tranches de 15 min par mi-temps, ⇄ Nous/Eux, ✕ suppression en 2 clics,
// notes (touche N) rangées à part des actions, lecture enchaînée (liste des notes dans l'onglet Vidéo).
// Lancer : node tests/lancer.js saisie2
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const ok = (c, m) => { console.log((c ? 'OK   ' : 'ÉCHEC ') + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const r = await p.evaluate(async () => {
    const W = ms => new Promise(x => setTimeout(x, ms)), P = FC.input._press, n = {}, o = {};
    const key = (k, x = {}) => document.dispatchEvent(new KeyboardEvent('keydown', Object.assign({ key: k, bubbles: true, cancelable: true }, x)));
    localStorage.clear(); FC.store.newMatch();
    o.defMin = FC.store.h2Start() / 60000;
    FC.store.setMeta({ flip: true }); FC.clock.set(600000);
    for (let i = 0; i < 3; i++) { P(n, 'N', [20 + i * 10, 30]); await W(5); P(n, 'N', [30 + i * 10, 35]); await W(400); }
    const ids = JSON.stringify(FC.store.all().map(e => [e.id, e.t, e.half]));
    key('z', { ctrlKey: true }); key('z', { ctrlKey: true }); o.undo = FC.store.all().length;
    key('y', { ctrlKey: true }); key('z', { ctrlKey: true, shiftKey: true });
    o.redoSame = JSON.stringify(FC.store.all().map(e => [e.id, e.t, e.half])) === ids;
    key('z', { ctrlKey: true }); P(n, 'N', [50, 30]); await W(5); P(n, 'N', [60, 30]); await W(400); key('y', { ctrlKey: true });
    o.redoCleared = FC.store.all().length === 3 && !FC.store.canRedo();
    // mi-temps (45 par défaut) : change de côté même si la 1re était inversée
    const hb = document.getElementById('btn-half'); hb.click();
    o.h2 = [FC.store.meta().half, FC.store.meta().flip, FC.clock.fmt(FC.clock.now())];
    FC.clock.set(45 * 60000 + 120000); P(n, 'E', [20, 30]); await W(5); P(n, 'E', [35, 30]); await W(400);
    // passage à 40 min : la 2e mi-temps suit
    const s = document.getElementById('m-hmin'); s.value = '40'; s.onchange.call(s);
    o.min40 = [FC.store.meta().halfMin, FC.clock.fmt(FC.store.all().slice(-1)[0].t), [...s.options].map(x => x.value).join('/')];
    const tl = FC.stats.timeline(FC.store.all(), 'shots', 0, FC.store.h2Start());
    o.slices = tl.buckets.map(x => x.label).join(' ');
    // retour en 1re en 2 clics
    hb.click(); o.armed = hb.textContent; hb.click();
    const last = FC.store.all().slice(-1)[0];
    o.back = [FC.store.meta().half, FC.store.meta().flip, last.half];
    // ⇄ et ✕
    document.querySelector('#recent button[data-swap="' + last.id + '"]').click();
    o.swap = FC.store.all().slice(-1)[0].team;
    const rm = () => document.querySelector('#recent button[data-rm="1"]');
    rm().click(); o.rmArmed = FC.store.all().length; rm().click(); o.rmDone = FC.store.all().map(e => e.id).indexOf(1) < 0;
    // notes
    const before = FC.store.all().length; FC.clock.set(25 * 60000);
    key('n'); await W(30); const inp = document.getElementById('note-in');
    o.noteFocus = document.activeElement === inp; inp.value = 'bloc trop bas';
    inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    key('n'); await W(30); inp.value = 'jeter'; inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    o.notes = FC.store.notes().map(x => FC.clock.fmt(x.t) + ' ' + x.text).join('|');
    o.notesApart = FC.store.all().length === before;
    o.csvNote = FC.store.toCSV().split('\n').slice(-1)[0];
    document.getElementById('tab-video').click();
    [...document.querySelectorAll('#vd-filters button')].find(x => x.dataset.k === 'note').click();
    o.vdNotes = document.querySelectorAll('#vd-list li.nt').length;
    o.chainBtn = !!document.getElementById('vd-chain') && !!document.getElementById('dr-toggle');
    return o;
  });
  ok(r.defMin === 45, 'mi-temps de 45 min par défaut');
  ok(r.undo === 1 && r.redoSame, 'Ctrl+Z ×2 puis Ctrl+Y / Ctrl+Maj+Z : actions remises à l\'identique');
  ok(r.redoCleared, 'une nouvelle action vide « Rétablir »');
  ok(r.h2[0] === 2 && r.h2[1] === false && r.h2[2] === '45:00', 'mi-temps : 2e, côté inversé, chrono 45:00 ' + JSON.stringify(r.h2));
  ok(r.min40[0] === 40 && r.min40[1] === '42:00' && r.min40[2] === '40/45', 'durée 40 min : action de 2e recalée ' + JSON.stringify(r.min40));
  ok(r.slices === '0–15 15–30 30–40 40–55 55–70 70–80', 'tranches de 15 min par mi-temps : ' + r.slices);
  ok(/Confirmer/.test(r.armed) && r.back[0] === 1 && r.back[1] === true && r.back[2] === 1, 'retour en 1re en 2 clics ' + JSON.stringify(r.back));
  ok(r.swap === 'N', '⇄ passe l\'action d\'Eux à Nous');
  ok(r.rmArmed === 4 && r.rmDone, '✕ supprime au 2e clic seulement');
  ok(r.noteFocus && r.notes === '25:00 bloc trop bas' && r.notesApart, 'note N : gardée au temps de l\'appui, Échap annule, actions inchangées');
  ok(/,note,.*"bloc trop bas"$/.test(r.csvNote), 'note dans le CSV : ' + r.csvNote);
  ok(r.vdNotes === 1 && r.chainBtn, 'onglet Vidéo : filtre Notes, boutons Enchaîner et Dessiner');
  ok(!errs.length, 'aucune erreur JS ' + JSON.stringify(errs));
  await b.close();
})();
