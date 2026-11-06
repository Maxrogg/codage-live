/* STATS : fonctions pures, une par indicateur. Ajouter un indicateur = ajouter une fonction ici. */
FC.stats = (function () {
  const C = FC.CONFIG, L = C.pitch.L, W = C.pitch.W;
  const DESEQ = C.deseqKinds;

  // Position vue depuis l'équipe : tiers 0 = son camp, 2 = camp adverse ; couloir 0 = gauche, 2 = droit.
  function rel(team, x, y) {
    const nx = team === 'N' ? x : L - x, ny = team === 'N' ? y : W - y;
    return { third: nx < L / 3 ? 0 : nx < 2 * L / 3 ? 1 : 2, lane: ny < W / 3 ? 0 : ny < 2 * W / 3 ? 1 : 2 };
  }
  // Grille des tableaux d'analyse : cols zones dans la longueur (0 = son camp), lanes couloirs (0 = gauche de l'équipe).
  function zone(team, x, y) {
    const Z = C.zones, nx = team === 'N' ? x : L - x, ny = team === 'N' ? y : W - y;
    return { col: Math.min(Z.cols - 1, Math.floor(nx / (L / Z.cols))), lane: Math.min(Z.lanes - 1, Math.floor(ny / (W / Z.lanes))) };
  }
  function isPass(e) { return e.kind === 'pass' || e.kind === 'pass_deseq'; }
  function byResult(e, result) { return result === 'ok' ? !!e.ok : result === 'ko' ? !e.ok : true; }
  function select(events, team, half) {
    return events.filter(function (e) { return (!team || e.team === team) && (!half || e.half === half); });
  }
  function pct(a, b) { return b ? Math.round(100 * a / b) : null; }

  // Une action à deux points ratée (passe, conduite) = perte pour son équipe ET récupération pour l'adversaire,
  // toutes deux à l'endroit d'arrivée.
  // Une récupération codée = perte pour l'adversaire ; une perte codée = récupération pour l'adversaire (même endroit).
  // derived: 'pass' = déduit d'une passe ratée ; 'mirror' = reflet d'une récup / perte codée.
  const OPP = { N: 'E', E: 'N' };
  function derivedOf(e) {
    if (C.kinds[e.kind].two && e.ok === false) {
      const base = { x: e.x2, y: e.y2, half: e.half, t: e.t, derived: 'pass' };
      return [Object.assign({ kind: 'perte', team: e.team }, base), Object.assign({ kind: 'recup', team: OPP[e.team] }, base)];
    }
    if (e.kind === 'recup' || e.kind === 'perte') {
      return [{ kind: e.kind === 'recup' ? 'perte' : 'recup', team: OPP[e.team], x: e.x, y: e.y, half: e.half, t: e.t, derived: 'mirror' }];
    }
    return [];
  }
  function derived(events) {
    const out = [];
    events.forEach(function (e) { derivedOf(e).forEach(function (d) { out.push(d); }); });
    return out;
  }
  function withDerived(events) { return events.concat(derived(events)); }

  // Surface de réparation vue de l'équipe (elle attaque vers x = L).
  function inBox(team, x, y) {
    const nx = team === 'N' ? x : L - x, ny = team === 'N' ? y : W - y;
    return nx >= L - 16.5 && Math.abs(ny - W / 2) <= 20.16;
  }
  // Entrées réussies (passe ou conduite) dans le dernier tiers / la surface, depuis l'extérieur.
  function entries(events, team, half) {
    let tiers = 0, surf = 0;
    select(events, team, half).filter(function (e) { return C.kinds[e.kind].two && e.ok; }).forEach(function (e) {
      if (rel(team, e.x, e.y).third < 2 && rel(team, e.x2, e.y2).third === 2) tiers++;
      if (!inBox(team, e.x, e.y) && inBox(team, e.x2, e.y2)) surf++;
    });
    return { tiers: tiers, surf: surf };
  }

  // Origine des frappes : qu'y avait-il juste avant (fenêtre de temps, ou événements précédents sans chrono) ?
  // 'transition' = récup de l'équipe ou perte adverse ; 'deseq' = déséquilibre réussi de l'équipe ; sinon 'autre'.
  function shotOrigins(events, team, half) {
    const seq = [];
    events.forEach(function (e) { seq.push(e); derivedOf(e).forEach(function (d) { seq.push(d); }); });
    const out = { n: 0, transition: 0, deseq: 0, cpa: 0, autre: 0 };
    seq.forEach(function (s, k) {
      if (s.kind !== 'shot' || s.team !== team || (half && s.half !== half)) return;
      out.n++;
      let found = 'autre';
      for (let j = k - 1; j >= 0; j--) {
        const e = seq[j], timed = (s.t > 0 || e.t > 0);
        if (timed ? (s.t - e.t > C.originMs) : (k - j > C.originEvents)) break;
        if (e.team === team && e.kind === 'cpa') { found = 'cpa'; break; }
        if ((e.team === team && e.kind === 'recup') || (e.team !== team && e.kind === 'perte')) { found = 'transition'; break; }
        if (e.team === team && DESEQ.indexOf(e.kind) >= 0 && e.ok) { found = 'deseq'; break; }
      }
      out[found]++;
    });
    return out;
  }

  // ---- CPA ----
  // Type déduit de la position (repère de l'équipe qui tire le CPA).
  function cpaType(team, x, y) {
    const nx = team === 'N' ? x : L - x;
    if ((nx < 7 || nx > L - 7) && (y < 7 || y > W - 7)) return 'corner';
    if (y < 3 || y > W - 3) return 'touche';
    return 'cf';
  }
  // Liste des CPA d'une équipe, avec leur suite : out = 'but' | 'frappe' | null (frappe de la même équipe juste après).
  function cpaList(events, team, half) {
    const out = [];
    events.forEach(function (e, k) {
      if (e.kind !== 'cpa' || (team && e.team !== team) || (half && e.half !== half)) return;
      const c = Object.assign({}, e, { type: e.cpa || cpaType(e.team, e.x, e.y), out: null });
      for (let j = k + 1; j < events.length; j++) {
        const f = events[j], timed = (f.t > 0 || e.t > 0);
        if (timed ? (f.t - e.t > C.cpaMs) : (j - k > C.cpaEvents)) break;
        if (f.kind === 'cpa') break;
        if (f.kind === 'shot' && f.team === e.team) { c.out = f.res === 'but' ? 'but' : 'frappe'; break; }
      }
      out.push(c);
    });
    return out;
  }
  // ---- xG : probabilité qu'une frappe finisse au fond, selon distance et angle (repère de l'équipe qui tire) ----
  function xg(e) {
    const X = C.xg, nx = e.team === 'N' ? e.x : L - e.x, dx = Math.max(0.5, L - nx), dy = e.y - W / 2;
    let ang = Math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66 * 3.66); if (ang < 0) ang += Math.PI;
    const z = X.b0 + X.a * ang + X.d * Math.hypot(dx, dy);
    return 1 / (1 + Math.exp(-z));
  }
  function r1(v) { return Math.round(v * 10) / 10; }
  function fr1(v) { return String(r1(v)).replace('.', ','); }

  // Duels = récupérations / pertes codées à la main (Z / E), à ne pas confondre avec celles déduites d'une passe ratée.
  // Gagné = récup de Nous (Z), perdu = perte de Nous (E).
  function duels(events, half) {
    const ev = events.filter(function (e) { return !half || e.half === half; });
    return { won: ev.filter(function (e) { return e.kind === 'recup' && e.team === 'N'; }),
             lost: ev.filter(function (e) { return e.kind === 'perte' && e.team === 'N'; }) };
  }

  // Courbe par tranches de 15 min (nécessite le chrono).
  function timeline(events, metric, half) {
    const b = C.timeBuckets.map(function () { return { N: 0, E: 0 }; });
    let list = metric === 'perte' || metric === 'recup' ? withDerived(events) : events;
    list = list.filter(function (e) {
      if (half && e.half !== half) return false;
      if (metric === 'deseq') return DESEQ.indexOf(e.kind) >= 0 && e.ok;
      if (metric === 'shots') return e.kind === 'shot';
      return e.kind === metric;
    });
    list.forEach(function (e) { b[Math.min(b.length - 1, Math.floor((e.t || 0) / 900000))][e.team]++; });
    return { buckets: b, hasClock: events.some(function (e) { return e.t > 0; }) };
  }

  function summary(events, team, half) {
    const ev = select(withDerived(events), team, half);
    const k = function (kind) { return ev.filter(function (e) { return e.kind === kind; }); };
    const passes = ev.filter(isPass), pok = passes.filter(function (e) { return e.ok; }).length;
    const okOf = function (arr) { return arr.filter(function (e) { return e.ok; }).length; };
    const pd = k('pass_deseq'), cd = k('carry_deseq');
    const rec = k('recup'), per = k('perte'), sh = k('shot');
    const thirds = function (arr) {
      const t = [0, 0, 0]; arr.forEach(function (e) { t[rel(e.team, e.x, e.y).third]++; }); return t;
    };
    const rt = thirds(rec), pt = thirds(per);
    const cad = sh.filter(function (e) { return e.res === 'cadre'; }).length;
    const but = sh.filter(function (e) { return e.res === 'but'; }).length;
    return {
      passes: { n: passes.length, ok: pok, ko: passes.length - pok, pct: pct(pok, passes.length) },
      deseq: {
        total: okOf(pd) + okOf(cd),
        passe: { ok: okOf(pd), n: pd.length },
        conduite: { ok: okOf(cd), n: cd.length }
      },
      recup: { n: rec.length, haute: rt[2], milieu: rt[1], basse: rt[0], surRate: rec.filter(function (e) { return e.derived === 'pass'; }).length },
      perte: { n: per.length, ownThird: pt[0], milieu: pt[1], att: pt[2], surRate: per.filter(function (e) { return e.derived === 'pass'; }).length },
      shots: { n: sh.length, cadre: cad, but: but, hors: sh.length - cad - but, pctCadre: pct(cad + but, sh.length),
        surface: sh.filter(function (e) { return inBox(team, e.x, e.y); }).length, eff: pct(but, sh.length),
        xg: r1(sh.reduce(function (t, e) { return t + xg(e); }, 0)) },
      cpa: (function () {
        const l = cpaList(events, team, half), c = function (k, v) { return l.filter(function (x) { return x[k] === v; }).length; };
        return { n: l.length, corner: c('type', 'corner'), cf: c('type', 'cf'), touche: c('type', 'touche'), frappes: l.filter(function (x) { return x.out; }).length, buts: c('out', 'but') };
      })(),
      entrees: entries(events, team, half),
      // duels vus de l'équipe : récup ou perte qui ne vient pas d'une passe ratée (codée Z / E, ou son reflet)
      duels: (function () {
        const w = rec.filter(function (e) { return e.derived !== 'pass'; }).length, l = per.filter(function (e) { return e.derived !== 'pass'; }).length;
        return { won: w, lost: l, n: w + l, pct: pct(w, w + l) };
      })()
    };
  }

  // Matrice zones x couloirs (vue de l'équipe) : m[couloir][zone]
  function matrixOf(list, team, which) {
    const m = [];
    for (let i = 0; i < C.zones.lanes; i++) m.push(new Array(C.zones.cols).fill(0));
    list.forEach(function (e) {
      const p = which === 'to' ? zone(team, e.x2, e.y2) : zone(team, e.x, e.y);
      m[p.lane][p.col]++;
    });
    return { m: m, total: list.length };
  }
  function passList(events, team, half, result) {
    return select(events, team, half).filter(isPass).filter(function (e) { return byResult(e, result || 'all'); });
  }
  function perteList(events, team, half) {
    return select(withDerived(events), team, half).filter(function (e) { return e.kind === 'perte'; });
  }
  function zoneMatrix(events, team, half, which, result) { return matrixOf(passList(events, team, half, result), team, which); }
  function perteMatrix(events, team, half) { return matrixOf(perteList(events, team, half), team, 'from'); }
  // Pertes ÷ passes par zone (null si trop peu de passes dans la zone pour être lisible).
  function ratioMatrix(events, team, half, minPasses) {
    const play = matrixOf(passList(events, team, half), team, 'from').m, lose = perteMatrix(events, team, half).m;
    return play.map(function (row, l) { return row.map(function (v, c) { return v >= (minPasses || 3) ? lose[l][c] / v : null; }); });
  }

  // ---------- BILAN : constats lisibles à partir des données ----------
  function cellName(lane, col) {
    const Z = C.zones;
    return Z.laneLabels[lane] + ', ' + (col === 0 ? 'son camp' : col === Z.cols - 1 ? 'camp adverse' : 'zone ' + (col + 1));
  }
  function topCell(m, min) {
    let best = null;
    m.forEach(function (row, l) { row.forEach(function (v, c) { if (v >= min && (!best || v > best.v)) best = { v: v, lane: l, col: c }; }); });
    return best;
  }
  function sides(list, team, which) {       // répartition gauche / axe / droite (vue de l'équipe), en %
    const s = [0, 0, 0];
    list.forEach(function (e) {
      const p = which === 'to' ? zone(team, e.x2, e.y2) : zone(team, e.x, e.y);
      s[p.lane <= 1 ? 0 : p.lane === 2 ? 1 : 2]++;
    });
    const n = list.length || 1;
    return s.map(function (v) { return Math.round(100 * v / n); });
  }
  function teamInsights(events, t, half) {
    const out = [], name = C.teams[t].label, nous = t === 'N';
    const push = function (tone, text) { out.push({ tone: tone, text: text }); };
    const sum = summary(events, t, half);
    const passes = passList(events, t, half), pertes = perteList(events, t, half);
    const play = matrixOf(passes, t, 'from').m, lose = matrixOf(pertes, t, 'from').m;

    if (passes.length < 10) push('info', 'Peu de passes codées (' + passes.length + ') : lecture du jeu à prendre avec prudence.');
    else {
      const s = sides(passes, t, 'from');
      push('info', 'Passes jouées depuis : gauche ' + s[0] + '% · axe ' + s[1] + '% · droite ' + s[2] + '%.');
      if (Math.abs(s[0] - s[2]) >= 15) push('info', 'Jeu orienté vers la ' + (s[0] > s[2] ? 'gauche' : 'droite') + ' (' + Math.abs(s[0] - s[2]) + ' pts d\'écart).');
      push('info', 'Réussite des passes : ' + sum.passes.pct + '% (' + sum.passes.ok + '/' + sum.passes.n + ').');
    }
    if (pertes.length >= 3) {
      const own = sum.perte.ownThird, pc = Math.round(100 * own / sum.perte.n);
      push(pc >= 35 ? 'warn' : 'info', sum.perte.n + ' pertes, dont ' + own + ' dans son tiers (' + pc + '%).');
    }
    const tp = topCell(play, 3), tl = topCell(lose, 2);
    if (tp && tl) {
      if (tp.lane === tl.lane && tp.col === tl.col) push('warn', (nous ? 'On perd le plus là où on joue le plus : ' : 'Ils perdent le plus là où ils jouent le plus : ') + cellName(tp.lane, tp.col) + '.');
      else push('info', 'Zone la plus jouée : ' + cellName(tp.lane, tp.col) + ' (' + tp.v + ' passes). Zone où ' + (nous ? 'on perd' : 'ils perdent') + ' le plus : ' + cellName(tl.lane, tl.col) + ' (' + tl.v + ' pertes).');
    }
    const ratio = ratioMatrix(events, t, half, 5); let worst = null, safe = null;   // zones d'au moins 5 passes : évite les petits échantillons
    ratio.forEach(function (row, l) {
      row.forEach(function (r, c) {
        if (r == null) return;
        if (lose[l][c] >= 3 && (!worst || r > worst.r)) worst = { r: r, l: l, c: c };
        if (r <= 0.15 && play[l][c] >= 5 && (!safe || play[l][c] > play[safe.l][safe.c])) safe = { l: l, c: c };
      });
    });
    if (worst && worst.r >= 0.35) push('warn', 'Zone à risque : ' + cellName(worst.l, worst.c) + ' (' + lose[worst.l][worst.c] + ' pertes pour ' + play[worst.l][worst.c] + ' passes).');
    if (safe) push('good', 'Zone sûre et très jouée : ' + cellName(safe.l, safe.c) + ' (' + play[safe.l][safe.c] + ' passes, ' + lose[safe.l][safe.c] + ' perte(s)).');

    const rec = sum.recup;
    if (rec.n >= 3) push(rec.haute * 100 >= rec.n * 30 ? 'good' : 'info', rec.n + ' récupérations, dont ' + rec.haute + ' dans le camp adverse.');
    const ds = select(events, t, half).filter(function (e) { return DESEQ.indexOf(e.kind) >= 0 && e.ok; });
    if (ds.length >= 3) { const s = sides(ds, t, 'to'); push('info', ds.length + ' déséquilibres réussis, arrivées : gauche ' + s[0] + '% · axe ' + s[1] + '% · droite ' + s[2] + '%.'); }
    else if (ds.length) push('info', ds.length + ' déséquilibre(s) réussi(s).');
    if (sum.shots.n) {
      push('info', sum.shots.n + ' frappe(s), ' + (sum.shots.cadre + sum.shots.but) + ' cadrée(s), ' + sum.shots.but + ' but(s), ' + sum.shots.surface + ' dans la surface.');
      if (sum.shots.n >= 3 && sum.shots.eff != null) push('info', 'Efficacité (buts ÷ frappes) : ' + sum.shots.eff + '%.');
      const o = shotOrigins(events, t, half);
      if (o.n >= 2) {
        const hi = o.transition / o.n >= 0.4;
        push(hi ? (nous ? 'good' : 'warn') : 'info', nous
          ? 'Origine de nos frappes : au moins ' + o.transition + '/' + o.n + ' après une de nos récups ou une perte adverse (≤ ' + (C.originMs / 1000) + ' s), ' + o.deseq + ' après un déséquilibre' + (o.cpa ? ', ' + o.cpa + ' sur CPA' : '') + '.'
          : 'Origine de leurs frappes : au moins ' + o.transition + '/' + o.n + ' viennent d\'une de nos pertes ou d\'une de leurs récups (≤ ' + (C.originMs / 1000) + ' s), ' + o.deseq + ' après un déséquilibre' + (o.cpa ? ', ' + o.cpa + ' sur CPA' : '') + '.');
      }
    }
    if (sum.entrees.tiers || sum.entrees.surf) push('info', sum.entrees.tiers + ' entrée(s) dans le dernier tiers, ' + sum.entrees.surf + ' dans la surface.');
    if (!nous && out.length === 0) push('info', 'Pas encore de données sur eux.');
    return out;
  }
  function bilan(events, half) {
    const a = summary(events, 'N', half), b = summary(events, 'E', half), duel = [];
    const n = select(events, null, half).length;
    if (n >= 1) {
      const dn = a.deseq.total, de = b.deseq.total;
      duel.push({ tone: dn > de ? 'good' : dn < de ? 'warn' : 'info', text: 'Déséquilibres réussis : Nous ' + dn + ' – ' + de + ' Eux.' });
      duel.push({ tone: a.entrees.surf > b.entrees.surf ? 'good' : a.entrees.surf < b.entrees.surf ? 'warn' : 'info', text: 'Entrées dans la surface : Nous ' + a.entrees.surf + ' – ' + b.entrees.surf + ' Eux (dernier tiers : ' + a.entrees.tiers + ' – ' + b.entrees.tiers + ').' });
      if (a.passes.n >= 5 && b.passes.n >= 5) duel.push({ tone: 'info', text: 'Réussite des passes : Nous ' + a.passes.pct + '% – ' + b.passes.pct + '% Eux.' });
      duel.push({ tone: 'info', text: 'Frappes : Nous ' + a.shots.n + ' (' + (a.shots.cadre + a.shots.but) + ' cadrées) – ' + b.shots.n + ' (' + (b.shots.cadre + b.shots.but) + ' cadrées) Eux.' });
    }
    if (a.shots.n + b.shots.n) {
      const dN = a.shots.but - a.shots.xg, msg = 'xG (qualité des frappes) : Nous ' + fr1(a.shots.xg) + ' – ' + fr1(b.shots.xg) + ' Eux. Buts : ' + a.shots.but + ' – ' + b.shots.but + '.';
      duel.push({ tone: a.shots.xg > b.shots.xg + 0.5 ? 'good' : b.shots.xg > a.shots.xg + 0.5 ? 'warn' : 'info', text: msg +
        (a.shots.n >= 4 && dN <= -1 ? ' On a marqué moins que nos occasions le laissaient attendre.' : a.shots.n >= 4 && dN >= 1 ? ' On a marqué plus que nos occasions le laissaient attendre.' : '') });
    }
    if (a.cpa.n + b.cpa.n) duel.push({ tone: 'info', text: 'CPA : Nous ' + a.cpa.n + ' (' + a.cpa.frappes + ' suivis d\'une frappe, ' + a.cpa.buts + ' but) – Eux ' + b.cpa.n + ' (' + b.cpa.frappes + ' frappe, ' + b.cpa.buts + ' but).' });
    if (a.duels.n >= 4) duel.push({ tone: a.duels.pct > 50 ? 'good' : a.duels.pct < 50 ? 'warn' : 'info',
      text: 'Duels (Z / E) : Nous ' + a.duels.won + ' gagnés sur ' + a.duels.n + ' (' + a.duels.pct + '%).' });
    return { n: n, nous: teamInsights(events, 'N', half), eux: teamInsights(events, 'E', half), duel: duel };
  }

  // Indicateurs d'un match (pour comparer victoires / nuls / défaites).
  function kpis(events) {
    const a = summary(events, 'N', 0), b = summary(events, 'E', 0);
    return {
      deseqN: a.deseq.total, passPctN: a.passes.pct, perteOwnN: a.perte.ownThird, recupHauteN: a.recup.haute,
      shotsN: a.shots.n, cadN: a.shots.cadre + a.shots.but, shotsBoxN: a.shots.surface, entTiersN: a.entrees.tiers, entSurfN: a.entrees.surf,
      shotsE: b.shots.n, cadE: b.shots.cadre + b.shots.but, entSurfE: b.entrees.surf, deseqE: b.deseq.total,
      butsN: a.shots.but, butsE: b.shots.but, xgN: a.shots.xg, xgE: b.shots.xg, cpaShotN: a.cpa.frappes, cpaShotE: b.cpa.frappes
    };
  }

  return { cpaList: cpaList, cpaType: cpaType, xg: xg, fr1: fr1, duels: duels, entries: entries, shotOrigins: shotOrigins, timeline: timeline, kpis: kpis, inBox: inBox, rel: rel, zone: zone, withDerived: withDerived, perteMatrix: perteMatrix, ratioMatrix: ratioMatrix, bilan: bilan, isPass: isPass, byResult: byResult, select: select, summary: summary, zoneMatrix: zoneMatrix, DESEQ: DESEQ };
})();
