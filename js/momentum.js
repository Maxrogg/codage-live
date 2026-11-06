/* MOMENTUM : qui domine, minute après minute. Calcul pur (aucun accès à l'écran), testable seul.
   Pression d'une équipe = somme des points de ses actions offensives dans la fenêtre ; momentum = Nous − Eux.
   Les points sont dans FC.CONFIG.momentum. Chaque mi-temps est tracée à part (pas de chevauchement si la 1re dépasse 45'). */
FC.momentum = (function () {
  const C = FC.CONFIG, S = FC.stats, MIN = 60000;

  // Points d'une action pour l'équipe qui la fait.
  function weightOf(e) {
    const M = C.momentum; let w = 0;
    if (C.kinds[e.kind].two && e.ok) {
      if (!S.inBox(e.team, e.x, e.y) && S.inBox(e.team, e.x2, e.y2)) w += M.entSurf;
      else if (S.rel(e.team, e.x, e.y).third < 2 && S.rel(e.team, e.x2, e.y2).third === 2) w += M.entTiers;
      if (S.DESEQ.indexOf(e.kind) >= 0) w += M.deseq * M.deseqLane[S.zone(e.team, e.x2, e.y2).lane];
    }
    if (e.kind === 'shot') {
      const k = M.shotCol[S.zone(e.team, e.x, e.y).col];     // frappe dans le dernier quart : vaut plus (cadrée ou non)
      w += (M.shot + (e.res === 'cadre' || e.res === 'but' ? M.shotOn : 0)) * k;
      if (e.res === 'but') w += M.goal;
    }
    if (e.kind === 'recup' && S.rel(e.team, e.x, e.y).third === 2) w += M.recupHaute;
    return w;
  }

  // half : 0 = match entier, 1 ou 2. win : fenêtre en minutes. Renvoie { hasClock } si le chrono n'a jamais servi.
  function compute(events, half, win) {
    const M = C.momentum; win = win || M.win;
    if (!events.some(function (e) { return e.t > 0; })) return { hasClock: false };
    const list = S.withDerived(events).filter(function (e) { return !half || e.half === half; })
      .map(function (e) { return { t: e.t || 0, team: e.team, half: e.half, w: weightOf(e) }; })
      .filter(function (e) { return e.w > 0; });
    const maxT = function (h) {
      let m = 0; events.forEach(function (e) { if (e.half === h && (e.t || 0) > m) m = e.t; }); return m;
    };
    const has2 = events.some(function (e) { return e.half === 2; });
    const halves = half ? [half] : (has2 ? [1, 2] : [1]);
    const segs = []; let x = 0;
    halves.forEach(function (h) {
      const start = h === 2 ? Math.round(C.halfStartMs / MIN) : 0;
      let end = Math.ceil(maxT(h) / MIN);
      if (h === 1 && has2 && !half) end = Math.max(end, 45);
      end = Math.max(end, start + 5);
      if (segs.length) x += 3;                       // petit blanc entre les deux mi-temps
      segs.push({ half: h, from: start, to: end, x0: x - start });
      x += end - start;
    });
    const points = [];
    segs.forEach(function (sg) {
      for (let m = sg.from; m <= sg.to; m++) {
        let n = 0, e = 0;
        list.forEach(function (ev) {
          if (ev.half !== sg.half || ev.t >= (m + 1) * MIN || ev.t < (m + 1 - win) * MIN) return;
          if (ev.team === 'N') n += ev.w; else e += ev.w;
        });
        points.push({ x: sg.x0 + m, min: m, half: sg.half, n: n, e: e, v: n - e });
      }
    });
    const goals = events.filter(function (e) { return e.kind === 'shot' && e.res === 'but' && (!half || e.half === half); })
      .map(function (e) {
        const sg = segs.filter(function (s) { return s.half === e.half; })[0];
        return sg ? { team: e.team, min: Math.floor((e.t || 0) / MIN), x: sg.x0 + Math.floor((e.t || 0) / MIN) } : null;
      }).filter(Boolean);
    let pn = null, pe = null, nN = 0, nE = 0, nQ = 0;
    points.forEach(function (p) {
      if (p.v > 0 && (!pn || p.v > pn.v)) pn = p;
      if (p.v < 0 && (!pe || p.v < pe.v)) pe = p;
      if (p.v >= M.neutral) nN++; else if (p.v <= -M.neutral) nE++; else nQ++;
    });
    return { hasClock: true, win: win, segs: segs, points: points, goals: goals, total: x,
      peakN: pn, peakE: pe, minutes: { n: nN, e: nE, eq: nQ } };
  }

  function fmt(v) { return (Math.round(v * 10) / 10).toString().replace('.', ','); }
  // Phrase de synthèse (écran + « Copier le bilan »).
  function summary(d) {
    if (!d.hasClock) return 'Chrono jamais lancé : pas de momentum.';
    const parts = ['Minutes à l\'avantage : Nous ' + d.minutes.n + ' · Eux ' + d.minutes.e + ' · équilibre ' + d.minutes.eq + '.'];
    if (d.peakN) parts.push('Pic Nous : ' + d.peakN.min + '\' (+' + fmt(d.peakN.v) + ').');
    if (d.peakE) parts.push('Pic Eux : ' + d.peakE.min + '\' (+' + fmt(-d.peakE.v) + ').');
    return parts.join(' ');
  }
  return { compute: compute, summary: summary, weightOf: weightOf, fmt: fmt };
})();
