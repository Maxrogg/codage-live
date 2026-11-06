/* SYNC : copie des matchs dans la base de l'artefact (privée, liée au compte), en plus du stockage local.
   Si la base n'est pas disponible, tout continue en local seulement. Statut : 'local' | 'saving' | 'cloud' | 'error'. */
FC.sync = (function () {
  let col = null, status = 'local', detail = '', timer = null, busy = false;
  const dirty = new Map(), gone = new Set(), subs = [];

  function set(s, d) { status = s; detail = d || ''; subs.forEach(function (f) { f(s, detail); }); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function limit(p, ms) { return Promise.race([p, wait(ms).then(function () { throw { code: 'timeout' }; })]); }

  async function flush() {
    if (busy || !col) return;
    busy = true; set('saving');
    try {
      while (dirty.size || gone.size) {
        const id = dirty.size ? dirty.keys().next().value : null;
        if (id) {
          const mt = dirty.get(id); dirty.delete(id);
          try { await col.doc(id).set(clone(mt)); }
          catch (e) { if (e && e.code === 'unavailable') { await wait(800); await col.doc(id).set(clone(mt)); } else throw e; }
        } else {
          const g = gone.values().next().value; gone.delete(g);
          await col.doc(g).delete();
        }
      }
      set('cloud');
    } catch (e) { set('error', (e && e.code) || 'erreur'); }
    busy = false;
  }
  function schedule() { clearTimeout(timer); timer = setTimeout(flush, 1200); }

  async function init() {
    if (typeof claude === 'undefined' || !claude.use) return set('local');
    try {
      const results = await Promise.all([claude.use('db'), claude.use('user')]);
      const db = results[0], user = results[1];
      const id = user && user.id ? await user.id() : null;
      if (!db || !id) return set('local');
      col = db.collection('data/users/' + id);
      set('saving');
      const snap = await limit(col.get(), 10000);
      const remote = {};
      snap.docs.forEach(function (d) { if (d.exists) remote[d.id] = d.data(); });
      Object.keys(remote).forEach(function (k) {                    // le cloud est plus récent : on le prend
        const loc = FC.store.get(k);
        if (!loc || (remote[k].upd || 0) > loc.upd) FC.store.importMatch(clone(remote[k]));
      });
      const cur = FC.store.current();                               // match vide créé au démarrage alors que le cloud en contient : on l'écarte
      if (!cur.events.length && !cur.info.adv && FC.store.matches().length > 1) FC.store.remove(cur.id);
      FC.store.matches().forEach(function (mt) {                    // le local est plus récent ou absent du cloud : on pousse
        if (!mt.events.length && !mt.info.adv) return;
        if (!remote[mt.id] || mt.upd > (remote[mt.id].upd || 0)) dirty.set(mt.id, mt);
      });
      if (dirty.size) await flush(); else set('cloud');
    } catch (e) { col = null; set('local', (e && e.code) || ''); }
  }

  FC.store.onSave(function (mt) { if (!col) return; dirty.set(mt.id, mt); schedule(); });
  FC.store.onDelete(function (id) { dirty.delete(id); if (!col) return; gone.add(id); schedule(); });
  document.addEventListener('visibilitychange', function () { if (document.hidden && col && (dirty.size || gone.size)) { clearTimeout(timer); flush(); } });

  return {
    init: init,
    status: function () { return { s: status, d: detail }; },
    onStatus: function (f) { subs.push(f); },
    label: function () {
      return { local: 'Sauvegarde : ce navigateur seulement', saving: 'Sauvegarde en cours…', cloud: 'Sauvegardé ✓ (compte + navigateur)', error: 'Cloud en échec — copie locale OK' }[status];
    },
    // Proposer un fichier au téléchargement. Résout 'saved' | 'declined' | 'na' (indisponible).
    download: async function (filename, text) {
      try {
        if (typeof claude === 'undefined' || !claude.use) {            // application installée / fichier local : téléchargement normal
          const a = document.createElement('a');
          a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' })); a.download = filename;
          document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
          return 'saved';
        }
        const dl = await claude.use('downloads');
        if (!dl) return 'na';
        await dl.save({ filename: filename, data: text });
        return 'saved';
      } catch (e) { return e && e.code === 'declined' ? 'declined' : 'na'; }
    }
  };
})();
