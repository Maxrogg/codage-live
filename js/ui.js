/* UI : onglets, panneau live, filtres d'analyse, tableaux. */
FC.ui = (function () {
  const C = FC.CONFIG, $ = function (id) { return document.getElementById(id); };
  let view = 'live', armedDel = null, armedTimer = null, armedZero = null;
  const VIEWS = ['live', 'analysis', 'bilan', 'video', 'matches'];

  function el(tag, cls, html) {
    const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n;
  }
  function flash(msg) {
    const f = $('flash'); f.textContent = msg; f.classList.add('on');
    clearTimeout(flash._t); flash._t = setTimeout(function () { f.classList.remove('on'); }, 1800);
  }

  // ---------- tableau de stats ----------
  function frac(a, n) { return a + ' / ' + n; }
  // Fiche de match façon « stats TV » : Nous à gauche, Eux à droite, barre de partage sous chaque ligne principale.
  function statsTable(container, half, compact) {
    const ev = FC.store.all(), a = FC.stats.summary(ev, 'N', half), b = FC.stats.summary(ev, 'E', half);
    const sub = function (t) { return ' <span class="sub">' + t + '</span>'; };
    // [libellé, valeur affichée, secondaire (caché en compact), valeur pour la barre]
    const rows = [
      ['Passes réussies', function (s) { return s.passes.ok + (s.passes.pct == null ? '' : sub(s.passes.pct + '%')); }, 0, function (s) { return s.passes.ok; }],
      ['Passes manquées', function (s) { return s.passes.ko; }, 1],
      ['Déséquilibres réussis', function (s) { return s.deseq.total; }, 0, function (s) { return s.deseq.total; }],
      ['passes', function (s) { return frac(s.deseq.passe.ok, s.deseq.passe.n); }, 1],
      ['conduites', function (s) { return frac(s.deseq.conduite.ok, s.deseq.conduite.n); }, 1],
      ['Entrées dans la surface', function (s) { return s.entrees.surf; }, 0, function (s) { return s.entrees.surf; }],
      ['Entrées dernier tiers', function (s) { return s.entrees.tiers; }, 1],
      ['Frappes', function (s) { return s.shots.n + sub((s.shots.cadre + s.shots.but) + ' cadr.'); }, 0, function (s) { return s.shots.n; }],
      ['xG (qualité des frappes)', function (s) { return s.shots.n ? FC.stats.fr1(s.shots.xg) : '–'; }, 0, function (s) { return s.shots.xg; }],
      ['dans la surface', function (s) { return s.shots.surface; }, 1],
      ['buts ÷ frappes', function (s) { return s.shots.eff == null ? '–' : s.shots.eff + '%'; }, 1],
      ['CPA', function (s) { return s.cpa.n + (s.cpa.n ? sub(s.cpa.frappes + ' → frappe') : ''); }, 0, function (s) { return s.cpa.n; }],
      ['corners · coups francs · touches', function (s) { return s.cpa.corner + ' · ' + s.cpa.cf + ' · ' + s.cpa.touche; }, 1],
      ['Duels gagnés (Z / E)', function (s) { return s.duels.n ? s.duels.won + sub(s.duels.pct + '%') : '–'; }, 0, function (s) { return s.duels.won; }],
      ['Récupérations', function (s) { return s.recup.n + sub('hautes ' + s.recup.haute); }, 0, function (s) { return s.recup.n; }],
      ['sur erreur technique adv.', function (s) { return s.recup.surRate; }, 1],
      ['Pertes', function (s) { return s.perte.n + sub('son tiers ' + s.perte.ownThird); }, 0, function (s) { return s.perte.n; }],
      ['sur erreur technique', function (s) { return s.perte.surRate; }, 1]
    ];
    let h = '<div class="facts"><div class="fh"><span class="n">Nous</span><span class="e">Eux</span></div>';
    rows.forEach(function (r) {
      if (compact && r[2]) return;
      if (r[2]) { h += '<div class="fr minor"><span class="v">' + r[1](a) + '</span><span class="l">' + r[0] + '</span><span class="v">' + r[1](b) + '</span></div>'; return; }
      const x = r[3](a) || 0, y = r[3](b) || 0, p = x + y ? Math.round(100 * x / (x + y)) : 50;
      h += '<div class="fr"><span class="v n">' + r[1](a) + '</span><span class="l">' + r[0] + '</span><span class="v e">' + r[1](b) + '</span>' +
        '<span class="bar' + (x + y ? '' : ' empty') + '"><i style="width:' + p + '%"></i></span></div>';
    });
    container.innerHTML = h + '</div>';
  }


  // ---------- matrices de zones ----------
  function matrixBlock(title, sub, m, total, rgb, mode, cnt) {
    let max = 0;
    if (mode === 'pct') m.forEach(function (r) { r.forEach(function (v) { if (v > max) max = v; }); });
    let h = '<div class="zone"><div class="zt">' + title + ' <span class="sub">' + sub + '</span></div><table><tbody>';
    const last = C.zones.cols - 1;
    let maxP = 0;
    if (mode === 'ratio') cnt.play.forEach(function (r) { r.forEach(function (v) { if (v > maxP) maxP = v; }); });
    m.forEach(function (row, li) {
      h += '<tr><th>' + C.zones.laneLabels[li] + '</th>';
      row.forEach(function (v, ci) {
        let al, txt;
        if (mode === 'ratio') {                      // intensité = taux de perte × poids du volume (une zone à 2 passes reste pâle)
          const np = cnt.play[li][ci], nl = cnt.lose[li][ci];
          al = v == null ? 0 : Math.min(1, v) * Math.pow(np / (maxP || 1), 0.5);
          txt = v == null ? '–' : Math.round(100 * v) + '%<br><span class="sub2">' + nl + '/' + np + '</span>';
        }
        else { al = max ? v / max : 0; txt = (total ? Math.round(100 * v / total) : 0) + '%'; }
        h += '<td style="background:rgba(' + rgb.join(',') + ',' + (al * 0.85).toFixed(2) + ');color:' + (al > 0.55 ? '#fff' : 'inherit') + '">' + txt + '</td>';
      });
      h += '</tr>';
    });
    h += '<tr class="ax"><th></th>';
    for (let c = 0; c <= last; c++) h += '<td>' + (c === 0 ? 'son camp' : c === last ? 'camp adv.' : 'zone ' + (c + 1)) + '</td>';
    return h + '</tr></tbody></table></div>';
  }
  function zoneBlock(container, team, half, result) {
    const ev = FC.store.all(), P = FC.viz.pal(), S = FC.stats;
    const tr = FC.viz.hexToRgb(P[team]), lr = FC.viz.hexToRgb(FC.viz.perteColor(P, team));
    const play = S.zoneMatrix(ev, team, half, 'from', result), arr = S.zoneMatrix(ev, team, half, 'to', result), lose = S.perteMatrix(ev, team, half);
    container.innerHTML =
      matrixBlock('Où on joue (départs)', '(' + play.total + ')', play.m, play.total, tr, 'pct') +
      matrixBlock('Où ça arrive (arrivées)', '(' + arr.total + ')', arr.m, arr.total, tr, 'pct') +
      matrixBlock('Où on perd', '(' + lose.total + ')', lose.m, lose.total, lr, 'pct') +
      matrixBlock('Pertes ÷ passes', '(zones ≥ 3 passes ; chiffres = pertes/passes)', S.ratioMatrix(ev, team, half, 3), 0, lr, 'ratio',
        { play: S.zoneMatrix(ev, team, half, 'from', 'all').m, lose: lose.m });
  }

  // ---------- vue live ----------
  function hintText() {
    const S = FC.input.state(), K = C.keys, d = S.down;
    if (S.pending) return '<b>Départ posé (' + C.teams[S.pending.team].label + ').</b> Déplace le curseur, <kbd>Espace</kbd> = arrivée réussie, <kbd>Espace</kbd> ×2 = <b>ratée</b> · <kbd>Ctrl</kbd> passe déséq. · <kbd>Shift</kbd> conduite déséq. · <kbd>Échap</kbd> annule';
    if (d.has(K.cpa)) return '<b>Mode CPA</b> — place le curseur à l\'endroit du ballon, <kbd>Espace</kbd> bref = <b class="n">Nous</b>, maintenu = <b class="e">Eux</b>. Corner, coup franc ou touche : déduit de la position';
    if (d.has(K.frappe)) return '<b>Mode frappe</b> — <kbd>Espace</kbd> = non cadrée, <kbd>Espace</kbd> ×2 = <b>cadrée</b>, puis <kbd>C</kbd> si but';
    return 'Pad = déplacer · <kbd>Espace</kbd> bref = <b class="n">Nous</b> · <kbd>Espace</kbd> maintenu = <b class="e">Eux</b> · <kbd>Z</kbd> récup · <kbd>E</kbd> perte · <kbd>R</kbd>+<kbd>Espace</kbd> frappe · <kbd>F</kbd>+<kbd>Espace</kbd> CPA · <kbd>Espace</kbd> ×2 = passe ratée / frappe cadrée';
  }
  function describe(e) {
    const kind = C.kinds[e.kind].label;
    let tag = '';
    if (C.kinds[e.kind].two) tag = e.ok ? ' ✓' : ' ✗';
    if (e.kind === 'shot') tag = ' — ' + C.shotResults[e.res] + ' (xG ' + FC.stats.fr1(FC.stats.xg(e)) + ')';
    if (e.kind === 'cpa') tag = ' — ' + C.cpaTypes[e.cpa || FC.stats.cpaType(e.team, e.x, e.y)];
    return FC.clock.fmt(e.t) + ' · ' + C.teams[e.team].label + ' · ' + kind + tag;
  }
  function renderLive() {
    const cv = $('live'); if (!cv.clientWidth) return;
    const m = FC.store.meta(), S = FC.input.state();
    FC.viz.drawLive(cv, { events: FC.store.all(), flip: m.flip, pending: S.pending, prov: S.prov, mouse: S.mouse });
    $('hint').innerHTML = hintText();
  }
  function renderSide() {
    const m = FC.store.meta(), ev = FC.store.all();
    $('count').textContent = ev.length + ' événement' + (ev.length > 1 ? 's' : '');
    $('half').textContent = m.half === 1 ? '1re mi-temps' : '2e mi-temps';
    $('btn-half').disabled = m.half === 2;
    $('dir').textContent = 'Nous attaquons vers ' + (m.flip ? 'la gauche' : 'la droite');
    const list = $('recent'); list.innerHTML = '';
    ev.slice(-8).reverse().forEach(function (e) {
      const li = el('li', e.team === 'N' ? 'n' : 'e'); li.textContent = describe(e); list.appendChild(li);
    });
    const rs = FC.store.resultOf(FC.store.current());
    $('sb-n').textContent = rs ? rs.sn : 0; $('sb-e').textContent = rs ? rs.se : 0;
    statsTable($('live-stats'), 0, true);
  }
  function tick() {
    $('clock').textContent = FC.clock.fmt(FC.clock.now());
    $('btn-clock').textContent = FC.clock.isRunning() ? '⏸ Pause' : '▶ Chrono';
  }

  // ---------- vue analyse ----------
  // Chaque préréglage = une liste de couches ; chaque couche est dessinée pour Nous puis pour Eux.
  const PRESETS = {
    all:   { label: 'Vue d\'ensemble', cols: 4, layers: ['deseq', 'diff', 'pertePasse', 'duel', 'jeu', 'shots'] },
    deseq: { label: 'Déséquilibres', cols: 2, layers: ['deseq'] },
    diff:  { label: 'Sûr / à risque', cols: 2, layers: ['diff'] },
    rp:    { label: 'Pertes & duels', cols: 3, dense: false, layers: ['pertePasse', 'duel'] },
    jeu:   { label: 'Où ça passe', cols: 2, layers: ['jeu', 'arr'] },
    shots: { label: 'Frappes & CPA', cols: 2, layers: ['shots', 'cpa'] }
  };
  const LAYER_PRESET = { deseq: 'deseq', diff: 'diff', pertePasse: 'rp', duel: 'rp', jeu: 'jeu', arr: 'jeu', shots: 'shots', cpa: 'shots' };
  let preset = 'all', builtFor = null, panels = [];

  function buildPanels() {
    const grid = $('an-grid'), pr = PRESETS[preset];
    grid.innerHTML = ''; panels = [];
    grid.style.setProperty('--cols', pr.cols); grid.classList.toggle('dense', pr.dense !== undefined ? pr.dense : pr.cols > 2);
    pr.layers.forEach(function (layer) {
      (layer === 'duel' ? ['N'] : ['N', 'E']).forEach(function (team) {
        const sec = el('section', 'card pan'), h2 = el('h2'), cv = el('canvas');
        sec.appendChild(h2); sec.appendChild(cv); grid.appendChild(sec);
        if (preset === 'all') { sec.classList.add('click'); sec.onclick = function () { setPreset(LAYER_PRESET[layer]); }; }
        panels.push({ team: team, layer: layer, h2: h2, cv: cv });
      });
    });
    builtFor = preset;
    $('an-det').open = preset !== 'all';
  }
  function setPreset(k) {
    preset = k;
    Array.prototype.forEach.call($('an-presets').children, function (b) { b.classList.toggle('on', b.dataset.k === k); });
    renderAnalysis();
  }
  function renderAnalysis() {
    if (view !== 'analysis') return;
    if (builtFor !== preset) buildPanels();
    const half = +$('f-half').value, result = $('f-result').value, ev = FC.store.all(), layers = PRESETS[preset].layers;
    $('f-result').disabled = !layers.some(function (l) { return l === 'jeu' || l === 'arr' || l === 'deseq'; });
    panels.forEach(function (p) {
      const info = FC.viz.drawAnalysis(p.cv, p.team, ev, half, p.layer, result);
      p.h2.textContent = FC.viz.layerTitle(p.layer, p.team) + ' ' + info;
    });
    ['N', 'E'].forEach(function (t) { zoneBlock($(t === 'N' ? 'zones-n' : 'zones-e'), t, half, result); });
    statsTable($('an-stats'), half);
    $('diff-key').hidden = layers.indexOf('diff') < 0;
    $('duel-key').hidden = layers.indexOf('duel') < 0;
  }

  // ---------- carte « Match » ----------
  const RES = { V: 'Victoire', N: 'Nul', D: 'Défaite' };
  function badge(r) {
    if (!r) return '<span class="sub">–</span>';
    return '<span class="badge ' + r.r + '">' + RES[r.r] + '</span>' + (r.deduced ? ' <span class="sub">(buts codés)</span>' : '');
  }
  function fillMatchCard(force) {
    const i = FC.store.info(), set = function (id, v) { const n = $(id); if (force || document.activeElement !== n) n.value = v == null ? '' : v; };
    set('m-adv', i.adv); set('m-date', i.date); set('m-sn', i.sn); set('m-se', i.se);
    $('m-res').innerHTML = badge(FC.store.resultOf(FC.store.current()));
    const g = FC.store.goals(FC.store.current());
    $('m-fill').textContent = 'Buts codés ' + g.N + '–' + g.E;
  }
  function num(v) { return v === '' ? null : Math.max(0, Math.min(30, Math.round(+v))); }

  // ---------- onglet Matchs ----------
  const KPI = [
    ['Nous'],
    ['Déséquilibres réussis', 'deseqN', 1], ['Passes réussies (%)', 'passPctN', 1], ['Pertes dans notre tiers', 'perteOwnN', -1],
    ['Récupérations hautes', 'recupHauteN', 1], ['Entrées dernier tiers', 'entTiersN', 1], ['Entrées dans la surface', 'entSurfN', 1],
    ['Frappes', 'shotsN', 1], ['Frappes cadrées', 'cadN', 1], ['Frappes dans la surface', 'shotsBoxN', 1], ['Buts', 'butsN', 1], ['xG', 'xgN', 1], ['CPA suivis d\'une frappe', 'cpaShotN', 1],
    ['Eux'],
    ['Déséquilibres réussis', 'deseqE', -1], ['Entrées dans la surface', 'entSurfE', -1], ['Frappes', 'shotsE', -1], ['Frappes cadrées', 'cadE', -1], ['xG', 'xgE', -1], ['CPA suivis d\'une frappe', 'cpaShotE', -1], ['Buts', 'butsE', -1]
  ];
  function avg(list, key) {
    const v = list.map(function (k) { return k[key]; }).filter(function (x) { return x != null; });
    return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null;
  }
  function fmtN(v) { return v == null ? '–' : String(Math.round(v * 10) / 10).replace('.', ','); }
  function renderSnaps() {
    const snaps = FC.backup.list();
    if (!snaps.length) { $('snap-list').innerHTML = '<p class="sub">Aucun point de sauvegarde pour l\'instant : le premier est pris après 20 actions codées.</p>'; return; }
    let h = '<table class="lib"><thead><tr><th>Quand</th><th>Match</th><th>Événements</th><th>Pourquoi</th><th></th></tr></thead><tbody>';
    snaps.forEach(function (s) {
      const d = new Date(s.ts), when = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      h += '<tr><td>' + when + '</td><td>' + (s.adv ? s.adv.replace(/</g, '&lt;') : '<span class="sub">(sans nom)</span>') + ' <span class="sub">' + (s.date || '') + '</span></td><td>' + s.n + '</td><td>' + s.reason.replace(/</g, '&lt;') +
        '</td><td class="act"><button data-restore="' + s.id + '">Restaurer</button></td></tr>';
    });
    $('snap-list').innerHTML = h + '</tbody></table>';
  }
  function renderMatches() {
    if (view !== 'matches') return;
    const all = FC.store.matches().slice().sort(function (a, b) { return (b.info.date || '').localeCompare(a.info.date || '') || b.upd - a.upd; });
    let h = '<table class="lib"><thead><tr><th>Date</th><th>Adversaire</th><th>Score</th><th>Résultat</th><th>Événements</th><th></th></tr></thead><tbody>';
    all.forEach(function (mt) {
      const r = FC.store.resultOf(mt), isCur = mt.id === FC.store.id();
      h += '<tr class="' + (isCur ? 'cur' : '') + '"><td>' + (mt.info.date || '') + '</td><td>' + (mt.info.adv ? mt.info.adv.replace(/</g, '&lt;') : '<span class="sub">(sans nom)</span>') +
        (isCur ? ' <span class="sub">· en cours</span>' : '') + '</td><td>' + (r ? r.sn + ' – ' + r.se : '–') + '</td><td>' + badge(r) + '</td><td>' + mt.events.length +
        '</td><td class="act"><button data-open="' + mt.id + '">' + (isCur ? 'Coder' : 'Ouvrir') + '</button><button data-del="' + mt.id + '"' +
        (armedDel === mt.id ? ' class="danger">Confirmer ?' : '>Supprimer') + '</button></td></tr>';
    });
    $('lib-list').innerHTML = h + '</tbody></table>';
    $('lib-note').textContent = all.length + ' match' + (all.length > 1 ? 's' : '') + ' · ' + FC.sync.label();

    renderSnaps();
    const groups = { V: [], N: [], D: [] }; let skipped = 0;
    all.forEach(function (mt) {
      const r = FC.store.resultOf(mt);
      if (!r || mt.events.length < 10) { skipped++; return; }
      groups[r.r].push(FC.stats.kpis(mt.events));
    });
    const gv = groups.V, gn = groups.N, gd = groups.D, small = Math.min(gv.length, gd.length) < 5;
    let c = '<table class="cmp"><thead><tr><th></th><th>Victoires (' + gv.length + ')</th><th>Nuls (' + gn.length + ')</th><th>Défaites (' + gd.length + ')</th><th>V − D</th></tr></thead><tbody>';
    KPI.forEach(function (k) {
      if (!k[1]) { c += '<tr class="grp"><td colspan="5">' + k[0] + '</td></tr>'; return; }
      const a = avg(gv, k[1]), b = avg(gn, k[1]), d = avg(gd, k[1]);
      let diff = '–', cls = '';
      if (a != null && d != null) {
        const x = a - d; diff = (x > 0 ? '+' : '') + fmtN(x);
        if (gv.length >= 2 && gd.length >= 2 && Math.abs(x) / Math.max(Math.abs(a), Math.abs(d), 1) >= 0.25) { cls = x * k[2] > 0 ? 'up' : 'down'; diff += ' ●'; }
      }
      c += '<tr><td>' + k[0] + '</td><td>' + fmtN(a) + '</td><td>' + fmtN(b) + '</td><td>' + fmtN(d) + '</td><td class="' + cls + '">' + diff + '</td></tr>';
    });
    c += '</tbody></table><p class="sub">● = écart d\'au moins 25 % entre victoires et défaites (2+ matchs de chaque côté) : <b class="up">vert</b> = dans le sens attendu (victoires meilleures), <b class="down">rouge</b> = à contre-sens.' +
      (skipped ? ' ' + skipped + ' match(s) ignoré(s) : pas de résultat ou moins de 10 événements.' : '') + '</p>' +
      (small ? '<p class="sub"><b>Prudence :</b> ' + gv.length + ' victoire(s) et ' + gd.length + ' défaite(s) seulement. Avec si peu de matchs, un écart peut venir du hasard, de l\'adversaire ou de ce qui a été codé. Vise 5+ matchs de chaque côté avant d\'en tirer une règle.</p>' : '');
    $('cmp').innerHTML = gv.length + gn.length + gd.length ? c : '<p class="sub">Aucun match avec résultat pour l\'instant. Saisis le score dans la carte « Match » (onglet Codage).</p>';
  }

  // ---------- vue bilan ----------
  const ICON = { good: '✓', warn: '⚠', info: '•' };
  function renderBilan() {
    if (view !== 'bilan') return;
    const half = +$('b-half').value, b = FC.stats.bilan(FC.store.all(), half);
    statsTable($('bi-stats'), half);
    ['nous', 'eux', 'duel'].forEach(function (k) {
      const ul = $('bi-' + k); ul.innerHTML = '';
      (b[k].length ? b[k] : [{ tone: 'info', text: 'Rien à signaler pour l\'instant.' }]).forEach(function (it) {
        const li = el('li', 'tone-' + it.tone, '<span class="ic">' + ICON[it.tone] + '</span><span></span>');
        li.lastChild.textContent = it.text; ul.appendChild(li);
      });
    });
    $('bi-note').textContent = b.n < 20 ? 'Peu de données (' + b.n + ' événements) : constats indicatifs.' : '';
    renderMomentum(half);
    renderTime(half);
  }
  function renderMomentum(half) {
    const d = FC.momentum.compute(FC.store.all(), half, +$('mo-win').value), box = $('mo-chart');
    $('mo-note').textContent = FC.momentum.summary(d);
    if (!d.hasClock) { box.innerHTML = ''; $('mo-rule').textContent = ''; return; }
    FC.chart.momentum(box, d, 'Momentum : avantage de Nous ou d\'Eux minute par minute');
    const M = C.momentum;
    $('mo-rule').textContent = 'Points : entrée dans la surface ' + M.entSurf + ' (sinon dernier tiers ' + M.entTiers + '), frappe ' + M.shot + ' (+' + M.shotOn + ' cadrée, +' + M.goal + ' but ; ×' + M.shotCol[3] + ' dans le dernier quart), déséquilibre réussi ' + M.deseq + ' (×' + M.deseqLane[2] + ' dans l\'axe, ×' + M.deseqLane[1] + ' intérieur, ×' + M.deseqLane[0] + ' sur le côté, selon l\'arrivée), récupération haute ' + M.recupHaute + '. Fenêtre glissante. Réglable dans config.js (momentum).';
  }
  function renderTime(half) {
    const metric = $('t-metric').value, t = FC.stats.timeline(FC.store.all(), metric, half), box = $('t-chart');
    if (!t.hasClock) { box.innerHTML = ''; $('t-note').textContent = 'Chrono jamais lancé : pas de courbe. Il démarre tout seul au premier geste de chaque mi-temps.'; return; }
    let n = t.buckets.length; while (n > 6 && !t.buckets[n - 1].N && !t.buckets[n - 1].E) n--;
    const bs = t.buckets.slice(0, n), name = $('t-metric').selectedOptions[0].textContent;
    FC.chart.bars(box, C.timeBuckets.slice(0, n).map(function (l) { return l + '\''; }),
      bs.map(function (x) { return x.N; }), bs.map(function (x) { return x.E; }), name + ' par tranche de 15 minutes, Nous contre Eux');
    $('t-note').textContent = 'Pertes et récupérations incluent celles déduites des passes ratées. ' + (half ? '' : 'La 2e mi-temps commence à 45\'.');
  }
  function bilanText() {
    const half = +$('b-half').value, b = FC.stats.bilan(FC.store.all(), half), out = [];
    out.push('BILAN — ' + ($('b-half').selectedOptions[0].textContent));
    [['NOTRE JEU', b.nous], ['LEUR JEU', b.eux], ['NOUS FACE À EUX', b.duel]].forEach(function (g) {
      out.push('', g[0]); g[1].forEach(function (it) { out.push(ICON[it.tone] + ' ' + it.text); });
    });
    out.push('', 'MOMENTUM', FC.momentum.summary(FC.momentum.compute(FC.store.all(), half, +$('mo-win').value)));
    return out.join('\n');
  }

  function setView(v) {
    view = v;
    VIEWS.forEach(function (k) { $('view-' + k).hidden = v !== k; $('tab-' + k).classList.toggle('on', v === k); });
    FC.input.setEnabled(v === 'live');
    refresh();
  }
  function refresh() { renderSide(); renderLive(); renderAnalysis(); renderBilan(); renderMatches(); FC.video.render(); fillMatchCard(false); tick(); }

  function copy(text, label) {
    try {
      navigator.clipboard.writeText(text).then(function () { flash(label + ' copié'); }, function () { flash('Copie refusée'); });
    } catch (e) { flash('Copie refusée'); }
  }
  function save(name, text, label) {
    FC.sync.download(name, text).then(function (r) {
      if (r === 'saved') flash(label + ' enregistré');
      else if (r === 'declined') flash('Téléchargement annulé');
      else copy(text, label);                           // pas de téléchargement possible ici : copie dans le presse-papiers
    });
  }
  function initButtons() {
    $('tab-live').onclick = function () { setView('live'); };
    $('tab-analysis').onclick = function () { setView('analysis'); };
    $('tab-bilan').onclick = function () { setView('bilan'); };
    $('tab-video').onclick = function () { setView('video'); };
    $('tab-matches').onclick = function () { setView('matches'); };
    $('b-half').onchange = renderBilan; $('t-metric').onchange = renderBilan; $('mo-win').onchange = renderBilan;
    $('m-adv').oninput = function () { FC.store.setInfo({ adv: this.value }); };
    $('m-date').onchange = function () { FC.store.setInfo({ date: this.value }); };
    $('m-sn').oninput = function () { FC.store.setInfo({ sn: num(this.value) }); fillMatchCard(false); };
    $('m-se').oninput = function () { FC.store.setInfo({ se: num(this.value) }); fillMatchCard(false); };
    $('m-fill').onclick = function () { const g = FC.store.goals(FC.store.current()); FC.store.setInfo({ sn: g.N, se: g.E }); fillMatchCard(true); };
    $('btn-new').onclick = function () { FC.store.newMatch(); setView('live'); flash('Nouveau match'); };
    $('lib-list').onclick = function (e) {
      const t = e.target; if (t.tagName !== 'BUTTON') return;
      if (t.dataset.open) { FC.store.switchTo(t.dataset.open); setView('live'); return; }
      if (t.dataset.del) {
        if (armedDel !== t.dataset.del) {
          armedDel = t.dataset.del; clearTimeout(armedTimer);
          armedTimer = setTimeout(function () { armedDel = null; renderMatches(); }, 3500); renderMatches(); return;
        }
        clearTimeout(armedTimer); armedDel = null; FC.store.remove(t.dataset.del); renderMatches();
      }
    };
    $('btn-import').onclick = function () { $('file-import').click(); };
    $('file-import').onchange = function () {
      const f = this.files[0]; this.value = ''; if (!f) return;
      const rd = new FileReader();
      rd.onload = function () {
        try { const r = FC.store.importFile(String(rd.result)); flash(r.total ? r.added + ' match(s) ajouté(s), ' + r.updated + ' mis à jour' : 'Aucun match dans ce fichier'); }
        catch (e) { flash('Fichier illisible'); }
      };
      rd.readAsText(f);
    };
    $('snap-list').onclick = function (e) {
      const t = e.target; if (t.tagName !== 'BUTTON' || !t.dataset.restore) return;
      const obj = FC.backup.get(t.dataset.restore);
      if (!obj) { flash('Copie introuvable'); return; }
      const mt = FC.store.restoreCopy(obj); flash('Restauré : ' + mt.info.adv); renderMatches();
    };
    $('btn-dl-csv').onclick = function () { save(FC.store.csvName(), FC.store.toCSV(), 'CSV'); };
    $('btn-dl-all').onclick = function () { save('sauvegarde_matchs.json', FC.store.allJSON(), 'Sauvegarde'); };
    $('btn-save-top').onclick = function () { $('btn-dl-all').onclick(); };
    $('btn-bilan-copy').onclick = function () { copy(bilanText(), 'Bilan'); };
    $('btn-clock').onclick = function () { FC.clock.toggle(); FC.store.setMeta({ elapsed: FC.clock.now() }); tick(); };
    $('btn-half').onclick = function () {
      if (FC.store.all().length) FC.backup.snap(FC.store.current(), 'mi-temps');
      FC.clock.pause(); FC.clock.set(C.halfStartMs);
      FC.store.setMeta({ half: 2, elapsed: C.halfStartMs, flip: true }); tick();
    };
    $('btn-flip').onclick = function () { FC.store.setMeta({ flip: !FC.store.meta().flip }); };
    $('btn-undo').onclick = function () { FC.input.undo(); };
    $('btn-json').onclick = function () { copy(FC.store.toJSON(), 'JSON'); };
    $('btn-csv').onclick = function () { copy(FC.store.toCSV(), 'CSV'); };
    $('btn-reset').onclick = function () { FC.store.newMatch(); flash('Nouveau match'); };
    $('btn-zero').onclick = function () {               // efface le match en cours (confirmation en 2 clics)
      const b = $('btn-zero');
      if (!armedZero) {
        b.textContent = 'Confirmer ? (efface ce match)'; b.classList.add('danger');
        armedZero = setTimeout(function () { armedZero = null; b.textContent = 'Remettre à zéro'; b.classList.remove('danger'); }, 3500);
        return;
      }
      clearTimeout(armedZero); armedZero = null; b.textContent = 'Remettre à zéro'; b.classList.remove('danger');
      FC.input.cancel(); FC.clock.pause(); FC.clock.set(0);
      FC.store.clear(); FC.store.setInfo({ sn: null, se: null }); fillMatchCard(true); tick(); flash('Match remis à zéro');
    };
    ['f-half', 'f-result'].forEach(function (id) { $(id).onchange = renderAnalysis; });
    const box = $('an-presets');
    Object.keys(PRESETS).forEach(function (k) {
      const b = el('button', 'chip' + (k === preset ? ' on' : ''), PRESETS[k].label); b.dataset.k = k; b.onclick = function () { setPreset(k); }; box.appendChild(b);
    });
  }
  function legend() {
    const K = C.keys, rows = [
      ['Pad', 'déplace le curseur'],
      ['Espace bref / maintenu', 'poser le point : Nous / Eux'],
      ['(ou A + Espace)', 'Eux aussi'],
      ['Espace, Espace', 'passe réussie (départ puis arrivée)'],
      ['Espace, Espace ×2', 'passe ratée (croix au bout)'],
      ['Ctrl + Espace (arrivée)', 'passe de déséquilibre'],
      ['Shift + Espace (arrivée)', 'conduite de déséquilibre'],
      ['Z (1 appui)', 'on récupère : triangle au curseur + perte d\'Eux'],
      ['E (1 appui)', 'on perd : croix rouge au curseur + récup d\'Eux'],
      ['R + Espace', 'frappe non cadrée'],
      ['R + Espace ×2', 'frappe cadrée'],
      ['C après la frappe', 'c\'est un but'],
      ['F + Espace', 'coup de pied arrêté (corner, coup franc, touche selon l\'endroit)'],
      ['Chrono', 'démarre tout seul au 1er geste de chaque mi-temps'],
      ['Échap', 'annule le geste en cours'],
      ['Ctrl + Z', 'annule le dernier événement']
    ];
    $('legend').innerHTML = rows.map(function (r) { return '<tr><th>' + r[0] + '</th><td>' + r[1] + '</td></tr>'; }).join('');
  }

  let storageOk = true;
  function updateChip() {
    const n = $('save-state'), st = FC.sync.status();
    n.textContent = storageOk ? FC.sync.label() : '⚠ Enregistrement local impossible : télécharge la sauvegarde JSON maintenant';
    n.classList.toggle('err', !storageOk || st.s === 'error'); n.title = st.d || '';
  }
  function init() {
    FC.store.load();
    const m = FC.store.meta(); FC.clock.set(m.elapsed || 0);
    // La page a été rechargée pendant que le chrono tournait : on reprend en ajoutant le temps écoulé (si moins de 3 h).
    const gap = m.wallAt ? Date.now() - m.wallAt : -1;
    if (m.running && gap >= 0 && gap < 3 * 3600000) { FC.clock.set((m.elapsed || 0) + gap); FC.clock.start(); }
    initButtons(); legend();
    FC.input.init($('live'), function () { renderLive(); });
    FC.store.onChange(function () { renderSide(); renderLive(); renderAnalysis(); renderBilan(); FC.video.render(); fillMatchCard(false); });
    FC.video.init({ describe: describe, flash: flash, save: save });
    FC.store.onLib(function () { renderMatches(); fillMatchCard(false); });
    FC.store.onSwitch(function (mt) {
      FC.input.cancel(); FC.clock.pause(); FC.clock.set(mt.meta.elapsed || 0); tick(); fillMatchCard(true);
    });
    FC.store.onStorage(function (ok) { if (ok !== storageOk) { storageOk = ok; updateChip(); } });
    FC.sync.onStatus(function () {
      const st = FC.sync.status();
      updateChip();
      $('save-note').textContent = st.s === 'local' ? 'Sauvegarde dans ce navigateur. Le cloud n\'est pas disponible ici : télécharge la sauvegarde complète de temps en temps.' : 'Sauvegarde automatique à chaque événement (navigateur + compte).';
      renderMatches();
    });
    window.addEventListener('resize', function () { renderLive(); renderAnalysis(); FC.video.render(); });
    if (window.ResizeObserver) new ResizeObserver(function () { renderLive(); renderAnalysis(); }).observe($('live'));
    setInterval(tick, 500);
    setView('live');
    updateChip();
    FC.sync.init();
  }
  return { init: init, refresh: refresh };
})();
