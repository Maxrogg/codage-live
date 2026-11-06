/* STORE : bibliothèque de matchs + sauvegarde locale (la synchro cloud est dans sync.js).
   Un match = { id, info:{adv,date,sn,se}, events, seq, meta, upd }.
   Coordonnées en mètres dans le repère NORMALISÉ : "Nous" attaque toujours vers la droite
   (x: 0 = notre but, 105 = but adverse ; y: 0..68). */
FC.store = (function () {
  const IDX = 'fc2-index', MK = 'fc2-m-', OLD = 'fc-live-v1';
  const matches = {};
  let cur = null;
  const subs = [], libSubs = [], saveSubs = [], delSubs = [], switchSubs = [], storageSubs = [];

  function today() { return new Date().toISOString().slice(0, 10); }
  function uid() { return 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function blank() {
    return { id: uid(), info: { adv: '', date: today(), sn: null, se: null }, events: [], seq: 0,
      meta: { half: 1, elapsed: 0, flip: false }, upd: Date.now() };
  }
  function norm(m) {                                    // tolère d'anciennes sauvegardes
    m.info = Object.assign({ adv: '', date: today(), sn: null, se: null }, m.info || {});
    m.events = m.events || []; m.seq = m.seq || 0;
    m.meta = Object.assign({ half: 1, elapsed: 0, flip: false }, m.meta || {});
    m.upd = m.upd || Date.now();
    return m;
  }
  function saveIndex() {
    try { localStorage.setItem(IDX, JSON.stringify({ cur: cur, ids: Object.keys(matches) })); } catch (e) { /* ignore */ }
  }
  function saveLocal(m) {
    let ok = true;
    try { localStorage.setItem(MK + m.id, JSON.stringify(m)); }
    catch (e) {                                          // plein ou indisponible : on libère les points auto puis on réessaie une fois
      ok = false;
      if (FC.backup && FC.backup.purge()) { try { localStorage.setItem(MK + m.id, JSON.stringify(m)); ok = true; } catch (e2) { /* ignore */ } }
    }
    saveIndex();
    storageSubs.forEach(function (f) { f(ok); });
    return ok;
  }
  function touch(m) { m.upd = Date.now(); saveLocal(m); saveSubs.forEach(function (f) { f(m); }); }
  function emit() { subs.forEach(function (f) { f(); }); libSubs.forEach(function (f) { f(); }); }
  function m() { return matches[cur]; }

  // Résultat vu de Nous : score saisi, sinon buts codés (déduit).
  function goals(mt) {
    const g = { N: 0, E: 0 };
    mt.events.forEach(function (e) { if (e.kind === 'shot' && e.res === 'but') g[e.team]++; });
    return g;
  }
  function resultOf(mt) {
    let a = mt.info.sn, b = mt.info.se, deduced = false;
    if (a == null || b == null || a === '' || b === '') {
      if (!mt.events.length) return null;
      const g = goals(mt); a = g.N; b = g.E; deduced = true;
    }
    return { sn: +a, se: +b, r: a > b ? 'V' : a < b ? 'D' : 'N', deduced: deduced };
  }

  function select(id) {
    cur = id; saveIndex();
    switchSubs.forEach(function (f) { f(m()); });
    emit();
  }

  return {
    load: function () {
      let idx = null;
      try { idx = JSON.parse(localStorage.getItem(IDX) || 'null'); } catch (e) { /* ignore */ }
      if (idx && idx.ids) {
        idx.ids.forEach(function (id) {
          try { const raw = localStorage.getItem(MK + id); if (raw) matches[id] = norm(JSON.parse(raw)); } catch (e) { /* ignore */ }
        });
      }
      if (!Object.keys(matches).length) {              // migration de l'ancienne version (un seul match)
        const mt = blank();
        try {
          const raw = localStorage.getItem(OLD);
          if (raw) { const d = JSON.parse(raw); mt.events = d.events || []; mt.seq = d.seq || 0; mt.meta = Object.assign(mt.meta, d.meta || {}); }
        } catch (e) { /* ignore */ }
        matches[mt.id] = norm(mt); saveLocal(mt);
        cur = mt.id;
      } else cur = (idx && matches[idx.cur]) ? idx.cur : Object.keys(matches)[0];
      saveIndex();
    },
    onChange: function (f) { subs.push(f); },          // le match courant a changé
    onLib: function (f) { libSubs.push(f); },          // la liste / les infos ont changé
    onSave: function (f) { saveSubs.push(f); },        // un match est à synchroniser
    onDelete: function (f) { delSubs.push(f); },
    onSwitch: function (f) { switchSubs.push(f); },
    onStorage: function (f) { storageSubs.push(f); },    // f(true|false) : l'enregistrement local a réussi / échoué

    all: function () { return m().events; },
    meta: function () { return m().meta; },
    info: function () { return m().info; },
    id: function () { return cur; },
    current: function () { return m(); },
    get: function (id) { return matches[id]; },
    matches: function () { return Object.keys(matches).map(function (k) { return matches[k]; }); },
    resultOf: resultOf, goals: goals,

    add: function (ev) {
      const mt = m();
      ev.id = ++mt.seq; ev.half = mt.meta.half;
      if (ev.t == null) ev.t = FC.clock.now();
      mt.meta.elapsed = FC.clock.now();
      mt.events.push(ev); touch(mt); if (FC.backup) FC.backup.tick(mt); emit(); return ev;
    },
    patchLast: function (fn) { const mt = m(), e = mt.events[mt.events.length - 1]; if (e) { fn(e); touch(mt); emit(); } return e; },
    undo: function () { const mt = m(), e = mt.events.pop(); touch(mt); emit(); return e; },
    setMeta: function (patch) { const mt = m(); Object.assign(mt.meta, patch); touch(mt); emit(); },
    setInfo: function (patch) { const mt = m(); Object.assign(mt.info, patch); touch(mt); libSubs.forEach(function (f) { f(); }); },
    clear: function () {                                // vide le match courant (tests)
      const mt = m(); if (FC.backup && mt.events.length) FC.backup.snap(mt, 'avant remise à zéro');
      mt.events = []; mt.seq = 0; mt.meta = { half: 1, elapsed: 0, flip: false }; touch(mt); emit();
    },

    // --- bibliothèque ---
    newMatch: function () {
      const mt = m();
      if (mt && !mt.events.length && !mt.info.adv) return mt;      // le match courant est déjà vide : on le garde
      if (FC.backup && mt && mt.events.length) FC.backup.snap(mt, 'avant nouveau match');
      const n = blank(); matches[n.id] = n; saveLocal(n); saveSubs.forEach(function (f) { f(n); });
      select(n.id); return n;
    },
    switchTo: function (id) { if (matches[id] && id !== cur) select(id); },
    remove: function (id) {
      if (!matches[id]) return;
      if (FC.backup && matches[id].events.length) FC.backup.snap(matches[id], 'avant suppression');
      delete matches[id];
      try { localStorage.removeItem(MK + id); } catch (e) { /* ignore */ }
      delSubs.forEach(function (f) { f(id); });
      if (id === cur) {
        const rest = Object.keys(matches);
        if (rest.length) { rest.sort(function (a, b) { return matches[b].upd - matches[a].upd; }); select(rest[0]); }
        else { const n = blank(); matches[n.id] = n; saveLocal(n); select(n.id); }
      } else { saveIndex(); emit(); }
    },
    importMatch: function (obj) {                       // match venu du cloud (plus récent que le local)
      const mt = norm(obj); matches[mt.id] = mt; saveLocal(mt);
      if (mt.id === cur) { switchSubs.forEach(function (f) { f(mt); }); }
      emit();
    },

    // Restaure un point de sauvegarde sous forme de NOUVEAU match (rien n'est écrasé).
    restoreCopy: function (obj) {
      const mt = norm(JSON.parse(JSON.stringify(obj))), d = new Date();
      mt.id = uid(); mt.upd = Date.now();
      mt.info.adv = (mt.info.adv || 'Match') + ' (restauré ' + String(d.getHours()).padStart(2, '0') + 'h' + String(d.getMinutes()).padStart(2, '0') + ')';
      matches[mt.id] = mt; saveLocal(mt); saveSubs.forEach(function (f) { f(mt); }); emit();
      return mt;
    },
    // Import d'un fichier de sauvegarde (sauvegarde complète ou un seul match). Garde le plus récent en cas de doublon.
    importFile: function (text) {
      const d = JSON.parse(text), list = d.matches ? d.matches : (d.events ? [d] : []);
      let added = 0, updated = 0;
      list.forEach(function (o) {
        if (!o || !Array.isArray(o.events)) return;
        if (!o.id) o.id = uid();
        const old = matches[o.id], mt = norm(o);
        if (old && old.upd >= mt.upd) return;
        if (old && FC.backup && old.events.length) FC.backup.snap(old, 'avant import');
        old ? updated++ : added++;
        matches[mt.id] = mt; saveLocal(mt); saveSubs.forEach(function (f) { f(mt); });
        if (mt.id === cur) switchSubs.forEach(function (f) { f(mt); });
      });
      saveIndex(); emit();
      return { added: added, updated: updated, total: list.length };
    },
    toJSON: function () { return JSON.stringify(m(), null, 1); },
    allJSON: function () { return JSON.stringify({ version: 2, matches: this.matches() }, null, 1); },
    csvName: function () {
      const i = m().info;
      return 'match_' + (i.date || '') + '_' + ((i.adv || 'adversaire').replace(/[^\w-]+/g, '_')) + '.csv';
    },
    toCSV: function () {
      const head = 'id,mi_temps,minute,equipe,type,ok,x,y,x2,y2,resultat_frappe';
      const r = function (v) { return v == null ? '' : (typeof v === 'number' ? Math.round(v * 10) / 10 : v); };
      const rows = m().events.map(function (e) {
        return [e.id, e.half, FC.clock.fmt(e.t), e.team, e.kind, e.ok == null ? '' : (e.ok ? 1 : 0),
          r(e.x), r(e.y), r(e.x2), r(e.y2), e.res || ''].join(',');
      });
      return [head].concat(rows).join('\n');
    }
  };
})();
