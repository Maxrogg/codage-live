/* VIDÉO : relie le codage au film du match (fichier MP4 ouvert depuis le PC, rien n'est envoyé ni copié).
   Calage par mi-temps : k1 / k2 = seconde de la vidéo où le chrono de la mi-temps vaut son départ
   (00:00 en 1re, 45:00 en 2e). Temps vidéo d'une action = k[mi-temps] + (chrono - départ) / 1000.
   Le calage est gardé dans le match (meta.video) ; le fichier, lui, doit être rouvert après un rechargement. */
FC.video = (function () {
  const C = FC.CONFIG, $ = function (id) { return document.getElementById(id); };
  const LEAD = 4;                                      // s : on démarre un peu avant l'action pour voir la mise en place
  const FILTERS = {
    all:    { label: 'Tout',          f: function () { return true; } },
    deseq:  { label: 'Déséquilibres', f: function (e) { return C.deseqKinds.indexOf(e.kind) >= 0; } },
    shot:   { label: 'Frappes',       f: function (e) { return e.kind === 'shot'; } },
    perte:  { label: 'Pertes',        f: function (e) { return e.kind === 'perte' || (C.kinds[e.kind].two && !e.ok); } },
    recup:  { label: 'Récupérations', f: function (e) { return e.kind === 'recup'; } },
    cpa:    { label: 'CPA',           f: function (e) { return e.kind === 'cpa'; } },
    pass:   { label: 'Passes',        f: function (e) { return e.kind === 'pass'; } }
  };
  let filter = 'all', team = 'N', sel = null, fileName = '', url = null, describe = null, flash = function () {};

  function vmeta() { return FC.store.meta().video || {}; }
  function setV(patch) { FC.store.setMeta({ video: Object.assign({}, vmeta(), patch) }); }
  function start(h) { return h === 2 ? C.halfStartMs : 0; }
  // Seconde de la vidéo pour une action (null si la mi-temps n'est pas calée).
  function vt(e, v) {
    v = v || vmeta(); const k = e.half === 2 ? v.k2 : v.k1;
    return k == null ? null : Math.max(0, k + (e.t - start(e.half)) / 1000);
  }
  function fmt(s) {
    if (s == null) return '–';
    s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60;
    return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0');
  }
  function list() {
    const f = FILTERS[filter].f;
    return FC.store.all().filter(function (e) { return (team === 'all' || e.team === team) && f(e); });
  }
  function player() { return $('vd'); }

  function seek(e) {
    sel = e.id; const s = vt(e), p = player();
    if (s != null && p.src) { p.currentTime = Math.max(0, s - LEAD); p.play().catch(function () { /* lecture bloquée : l'utilisateur clique Lecture */ }); }
    else if (s == null) flash('Cale d\'abord la ' + (e.half === 2 ? '2e' : '1re') + ' mi-temps');
    else flash('Ouvre d\'abord le fichier vidéo');
    render();
  }
  function step(d) {
    const l = list(); if (!l.length) return;
    let i = l.findIndex(function (e) { return e.id === sel; });
    i = i < 0 ? (d > 0 ? 0 : l.length - 1) : Math.min(l.length - 1, Math.max(0, i + d));
    seek(l[i]);
  }
  // « C'est ici » : l'action sélectionnée se passe à l'instant affiché par le lecteur → on en déduit le calage de sa mi-temps.
  function syncOnSelected() {
    const e = FC.store.all().find(function (x) { return x.id === sel; }), p = player();
    if (!e) { flash('Choisis d\'abord une action dans la liste'); return; }
    if (!p.src) { flash('Ouvre d\'abord le fichier vidéo'); return; }
    const k = p.currentTime - (e.t - start(e.half)) / 1000, patch = {};
    patch[e.half === 2 ? 'k2' : 'k1'] = Math.round(k * 10) / 10;
    setV(patch); flash((e.half === 2 ? '2e' : '1re') + ' mi-temps calée');
  }
  function kickoff(h) {
    const p = player(); if (!p.src) { flash('Ouvre d\'abord le fichier vidéo'); return; }
    const patch = {}; patch[h === 2 ? 'k2' : 'k1'] = Math.round(p.currentTime * 10) / 10;
    setV(patch); flash('Coup d\'envoi ' + (h === 2 ? '2e' : '1re') + ' mi-temps calé à ' + fmt(p.currentTime));
  }
  function nudge(h, d) {
    const v = vmeta(), key = h === 2 ? 'k2' : 'k1'; if (v[key] == null) return;
    const patch = {}; patch[key] = Math.round((v[key] + d) * 10) / 10; setV(patch);
  }

  // Export pour l'analyse automatique : les actions codées avec leur seconde dans la vidéo.
  function exportObj() {
    const mt = FC.store.current(), v = vmeta();
    return { format: 'codage-live/actions-video', version: 1, match: { id: mt.id, info: mt.info },
      video: { fichier: v.name || null, k1: v.k1 == null ? null : v.k1, k2: v.k2 == null ? null : v.k2 },
      repere: 'mètres, 105 x 68, Nous attaque vers la droite (x = 105 = but adverse)',
      actions: mt.events.map(function (e) { return Object.assign({}, e, { video_s: vt(e, v) == null ? null : Math.round(vt(e, v) * 10) / 10 }); }) };
  }

  function renderSync() {
    const v = vmeta();
    ['1', '2'].forEach(function (h) {
      const k = v['k' + h];
      $('vd-k' + h).textContent = k == null ? 'pas calée' : 'calée : chrono ' + (h === '1' ? '00:00' : '45:00') + ' = ' + fmt(k) + ' dans la vidéo';
    });
    const p = player();
    $('vd-file').textContent = p.src ? fileName : (v.name ? 'Rouvre « ' + v.name + ' » (le fichier n\'est pas gardé après un rechargement)' : 'Aucun fichier ouvert');
  }
  function renderList() {
    const box = $('vd-list'), l = list(), v = vmeta();
    $('vd-n').textContent = l.length + ' action' + (l.length > 1 ? 's' : '');
    box.innerHTML = '';
    if (!l.length) { box.innerHTML = '<li class="sub">Aucune action pour ce filtre.</li>'; return; }
    l.forEach(function (e) {
      const li = document.createElement('li'), s = vt(e, v);
      li.className = (e.team === 'N' ? 'n' : 'e') + (e.id === sel ? ' sel' : '') + (s == null ? ' nosync' : '');
      li.innerHTML = '<span class="vt">' + fmt(s) + '</span>' + describe(e);
      li.onclick = function () { seek(e); };
      box.appendChild(li);
    });
    const cur = box.querySelector('.sel'); if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'nearest' });
  }
  function renderMini() {
    const cv = $('vd-pitch'); if (!cv.clientWidth) return;
    const e = FC.store.all().find(function (x) { return x.id === sel; });
    FC.viz.drawLive(cv, { events: e ? [e] : [], flip: false });
  }
  function render() {
    if ($('view-video').hidden) return;
    renderSync(); renderList(); renderMini();
    Array.prototype.forEach.call($('vd-filters').children, function (b) { b.classList.toggle('on', b.dataset.k === filter); });
    Array.prototype.forEach.call($('vd-team').children, function (b) { b.classList.toggle('on', b.dataset.k === team); });
  }

  function init(opts) {
    describe = opts.describe; flash = opts.flash;
    const box = $('vd-filters');
    Object.keys(FILTERS).forEach(function (k) {
      const b = document.createElement('button'); b.className = 'chip'; b.dataset.k = k; b.textContent = FILTERS[k].label;
      b.onclick = function () { filter = k; render(); }; box.appendChild(b);
    });
    Array.prototype.forEach.call($('vd-team').children, function (b) { b.onclick = function () { team = b.dataset.k; render(); }; });
    $('vd-open').onclick = function () { $('vd-input').click(); };
    $('vd-input').onchange = function () {
      const f = this.files && this.files[0]; if (!f) return;
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(f); fileName = f.name; player().src = url;
      if (vmeta().name !== f.name) setV({ name: f.name }); else render();
      this.value = '';
    };
    $('vd-ko1').onclick = function () { kickoff(1); };
    $('vd-ko2').onclick = function () { kickoff(2); };
    $('vd-here').onclick = syncOnSelected;
    $('vd-m1').onclick = function () { nudge(1, -1); }; $('vd-p1').onclick = function () { nudge(1, 1); };
    $('vd-m2').onclick = function () { nudge(2, -1); }; $('vd-p2').onclick = function () { nudge(2, 1); };
    $('vd-prev').onclick = function () { step(-1); };
    $('vd-next').onclick = function () { step(1); };
    $('vd-export').onclick = function () {
      const i = FC.store.info();
      opts.save('actions_video_' + (i.date || '') + '_' + ((i.adv || 'adversaire').replace(/[^\w-]+/g, '_')) + '.json', JSON.stringify(exportObj(), null, 1), 'Export');
    };
    // Raccourcis de l'onglet : J / K = action précédente / suivante, L = lecture / pause.
    document.addEventListener('keydown', function (ev) {
      if ($('view-video').hidden || /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target || {}).tagName || '')) return;
      const k = ev.key.toLowerCase();
      if (k === 'k') { step(1); ev.preventDefault(); }
      else if (k === 'j') { step(-1); ev.preventDefault(); }
      else if (k === 'l') { const p = player(); if (p.src) { p.paused ? p.play() : p.pause(); } ev.preventDefault(); }
    });
  }
  return { init: init, render: render, vt: vt, fmt: fmt, exportObj: exportObj };
})();
