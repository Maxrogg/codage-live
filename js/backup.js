/* BACKUP : points de sauvegarde automatiques (copies complètes d'un match à un instant donné), en plus de l'enregistrement
   à chaque événement. Servent à revenir en arrière après une erreur (remise à zéro, suppression, import, plantage).
   Déclencheurs : tous les 20 événements, toutes les 3 min d'activité, quand la page se cache, et AVANT toute action destructive. */
FC.backup = (function () {
  const IDX = 'fc2-snaps', PFX = 'fc2-snap-', MAX = 24, AUTO_PER_MATCH = 4, EVERY_EVENTS = 20, EVERY_MS = 180000;
  const last = {};                                       // matchId -> { n, ts } dernier point pris (pour ne pas en prendre trop)

  function readIdx() { try { return JSON.parse(localStorage.getItem(IDX) || '[]'); } catch (e) { return []; } }
  function writeIdx(a) { try { localStorage.setItem(IDX, JSON.stringify(a)); } catch (e) { /* ignore */ } }
  function drop(idx, id) { try { localStorage.removeItem(PFX + id); } catch (e) { /* ignore */ } return idx.filter(function (x) { return x.id !== id; }); }
  function dropOldest(idx, pred) {                       // supprime le plus ancien point correspondant ; renvoie la liste ou null
    const old = idx.filter(pred).sort(function (a, b) { return a.ts - b.ts; })[0];
    return old ? drop(idx, old.id) : null;
  }

  function snap(mt, reason, kind) {
    if (!mt) return null;
    const ts = Date.now(), id = ts.toString(36) + Math.random().toString(36).slice(2, 5), body = JSON.stringify(mt);
    let idx = readIdx(), ok = false;
    for (let t = 0; t < 6 && !ok; t++) {
      try { localStorage.setItem(PFX + id, body); ok = true; }
      catch (e) { const n = dropOldest(idx, function (x) { return x.kind === 'auto'; }) || dropOldest(idx, function () { return true; }); if (!n) break; idx = n; }
    }
    if (!ok) return null;
    idx.push({ id: id, ts: ts, reason: reason, kind: kind || 'safe', mid: mt.id, adv: mt.info.adv, date: mt.info.date, n: mt.events.length });
    let n;                                               // points automatiques d'un même match : on garde les plus récents
    while (idx.filter(function (x) { return x.kind === 'auto' && x.mid === mt.id; }).length > AUTO_PER_MATCH &&
           (n = dropOldest(idx, function (x) { return x.kind === 'auto' && x.mid === mt.id; }))) idx = n;
    while (idx.length > MAX && (n = dropOldest(idx, function (x) { return x.kind === 'auto'; }) || dropOldest(idx, function () { return true; }))) idx = n;
    writeIdx(idx);
    last[mt.id] = { n: mt.events.length, ts: ts };
    return id;
  }
  // Appelé après chaque événement ajouté.
  function tick(mt) {
    const l = last[mt.id];
    if (!l) { last[mt.id] = { n: mt.events.length - 1, ts: Date.now() }; return; }
    if (mt.events.length - l.n >= EVERY_EVENTS || (mt.events.length !== l.n && Date.now() - l.ts >= EVERY_MS)) snap(mt, 'automatique', 'auto');
  }
  function purgeAuto() {                                 // libère de la place si l'enregistrement local échoue
    let idx = readIdx(), n = 0, x;
    while ((x = idx.filter(function (e) { return e.kind === 'auto'; })[0])) { idx = drop(idx, x.id); n++; }
    writeIdx(idx); return n > 0;
  }
  function list() { return readIdx().sort(function (a, b) { return b.ts - a.ts; }); }
  function get(id) { try { return JSON.parse(localStorage.getItem(PFX + id)); } catch (e) { return null; } }
  function remove(id) { writeIdx(drop(readIdx(), id)); }

  document.addEventListener('visibilitychange', function () {   // l'onglet se cache / se ferme : dernier point si ça a bougé
    if (!document.hidden || !FC.store.current) return;
    const mt = FC.store.current(), l = last[mt.id];
    if (mt.events.length && (!l || l.n !== mt.events.length)) snap(mt, 'à la fermeture / changement d\'onglet', 'auto');
  });

  return { snap: snap, tick: tick, list: list, get: get, remove: remove, purge: purgeAuto };
})();
