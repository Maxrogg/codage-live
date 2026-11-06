/* INPUT : le pad déplace le curseur, la barre Espace pose le point (bref = Nous, maintenu = Eux). Produit des événements via FC.store.add.
   Passe / conduite / frappe : l'événement est "en attente" pendant dblMs ; un 2e appui proche
   dans ce délai = double appui (passe ratée, frappe cadrée). Sinon il est validé tel quel. */
FC.input = (function () {
  const C = FC.CONFIG, K = C.keys;
  const S = { down: new Set(), pending: null, prov: null, mouse: null, space: null };
  let canvas = null, enabled = true, onUpdate = function () {};

  function modKind(e) { return e.ctrlKey ? C.modifiers.ctrl : e.shiftKey ? C.modifiers.shift : null; }
  function flip() { return FC.store.meta().flip; }
  function point(e) {
    const r = canvas.getBoundingClientRect();
    return FC.pitch.toField(canvas._g, e.clientX - r.left, e.clientY - r.top, flip());
  }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }

  // Premier geste d'une mi-temps : le chrono démarre tout seul.
  function autoStart() {
    const m = FC.store.meta();
    if (FC.clock.isRunning() || FC.store.all().some(function (e) { return e.half === m.half; })) return;
    FC.clock.start(); FC.store.setMeta({ elapsed: FC.clock.now() });
  }

  function commit() {
    if (!S.prov) return;
    clearTimeout(S.prov.timer);
    const ev = S.prov.ev; S.prov = null;
    FC.store.add(ev); onUpdate();
  }
  function hold(ev, at) {
    commit(); autoStart();
    ev.t = FC.clock.now();
    S.pending = null;
    S.prov = { ev: ev, at: at, timer: setTimeout(commit, C.dblMs) };
    onUpdate();
  }
  function add(ev) { commit(); autoStart(); FC.store.add(ev); S.pending = null; onUpdate(); }
  function drop() { if (S.prov) { clearTimeout(S.prov.timer); S.prov = null; } S.pending = null; onUpdate(); }

  function press(e, team, p) {                         // appui sur Espace à la position p du curseur
    const x = p[0], y = p[1];

    if (S.prov) {                                     // 2e clic dans la fenêtre ?
      if (dist(p, S.prov.at) <= C.dblDist) {
        const ev = S.prov.ev;
        if (ev.kind === 'shot') ev.res = 'cadre';
        else { ev.ok = false; const mk = modKind(e); if (mk && ev.kind === 'pass') ev.kind = mk; }
        commit(); return;
      }
      commit();
    }
    if (S.down.has(K.frappe)) return hold({ kind: 'shot', team: team, x: x, y: y, res: 'hors' }, p);
    if (!S.pending) { autoStart(); S.pending = { team: team, x: x, y: y, kind: modKind(e) }; return onUpdate(); }
    const q = S.pending;
    if (dist([q.x, q.y], p) < C.minLen) return;       // double-clic accidentel sur le départ
    hold({ kind: modKind(e) || q.kind || 'pass', team: q.team, x: q.x, y: q.y, x2: x, y2: y, ok: true }, p);
  }

  // Z / E : un seul appui, au curseur. Récup de Nous (reflet = perte d'Eux) ou perte de Nous (reflet = récup d'Eux).
  function quick(kind) {
    if (!S.mouse) return;
    add({ kind: kind, team: 'N', x: S.mouse[0], y: S.mouse[1] });
  }
  function goal() {                                   // touche C : la dernière frappe était un but
    if (S.prov && S.prov.ev.kind === 'shot') { S.prov.ev.res = 'but'; commit(); return; }
    FC.store.patchLast(function (e) { if (e.kind === 'shot') e.res = 'but'; });
    onUpdate();
  }
  function undo() {
    if (S.prov || S.pending) { drop(); return; }
    FC.store.undo(); onUpdate();
  }
  // Espace : appui bref = Nous (validé au relâchement), maintenu holdMs = Eux (validé dès le seuil).
  // Un 2e appui proche d'un geste en attente = double appui (ratée / cadrée), traité tout de suite.
  function clearSpace() { if (S.space) { clearTimeout(S.space.timer); S.space = null; } }
  function spaceDown(e) {
    if (!enabled || !S.mouse) return;
    const p = S.mouse, snap = { ctrlKey: e.ctrlKey, shiftKey: e.shiftKey };
    clearSpace();
    if (S.prov && dist(p, S.prov.at) <= C.dblDist) { press(snap, 'N', p); return; }
    const team = S.down.has(K.eux) ? 'E' : 'N';
    const sp = { p: p, snap: snap, team: team, fired: false };
    sp.timer = setTimeout(function () { sp.fired = true; press(snap, 'E', p); }, C.holdMs);
    S.space = sp;
  }
  function spaceUp() {
    const sp = S.space; if (!sp) return;
    clearTimeout(sp.timer); S.space = null;
    if (!sp.fired) press(sp.snap, sp.team, sp.p);
  }
  function typing(e) { return /^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || ''); }

  function init(cv, update) {
    canvas = cv; onUpdate = update;
    cv.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    cv.addEventListener('mousedown', function (e) {    // le clic ne pose rien : il redonne juste le focus au clavier
      e.preventDefault();
      if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
      window.focus();
    });
    cv.addEventListener('mousemove', function (e) { S.mouse = point(e); if (S.pending) onUpdate(); });
    cv.addEventListener('mouseleave', function () { S.mouse = null; if (S.pending) onUpdate(); });

    document.addEventListener('keydown', function (e) {
      if (!enabled || typing(e)) return;
      const k = e.key.toLowerCase();
      if (e.key === 'Alt') e.preventDefault();
      if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); undo(); return; }
      if (k === ' ') { e.preventDefault(); if (!e.repeat) spaceDown(e); return; }
      if (k === K.annuler) { e.preventDefault(); drop(); return; }
      if (e.ctrlKey || e.metaKey || e.altKey) return;      // Ctrl/Alt + lettre = raccourci du navigateur, pas le nôtre
      if (k === K.but && !e.repeat) { goal(); return; }
      if (k === K.recup) { if (!e.repeat) quick('recup'); return; }
      if (k === K.perte) { if (!e.repeat) quick('perte'); return; }
      if (k.length === 1) { S.down.add(k); onUpdate(); }
    });
    document.addEventListener('keyup', function (e) {
      if (e.key === ' ' || e.key === 'Alt') e.preventDefault();
      if (e.key === ' ') spaceUp();
      S.down.delete(e.key.toLowerCase()); onUpdate();
    });
    window.addEventListener('blur', function () { S.down.clear(); clearSpace(); onUpdate(); });
  }

  return {
    init: init, state: function () { return S; }, undo: undo, cancel: drop,
    setEnabled: function (v) { enabled = v; if (!v) { S.down.clear(); drop(); } },
    _press: press, _quick: quick, _goal: goal, _spaceDown: spaceDown, _spaceUp: spaceUp                        // exposés pour les tests
  };
})();
