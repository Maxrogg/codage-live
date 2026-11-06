/* VIZ : dessin canvas — heatmaps, flux, marqueurs. Aucune logique de saisie ici. */
FC.viz = (function () {
  const C = FC.CONFIG, L = C.pitch.L, W = C.pitch.W, M = 14;
  const P_ = FC.pitch, S_ = FC.stats;

  function css(name, fb) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fb;
  }
  function pal() {
    return { pitch: css('--pitch', '#f3f2ee'), line: css('--pitch-line', '#b4b2a8'), ink: css('--ink', '#0b0b0b'), ink2: css('--ink2', '#52514e'),
      surface: css('--surface', '#ffffff'), stripe: css('--pitch-stripe', 'rgba(0,0,0,0.035)'), N: css('--nous', '#2a78d6'), E: css('--eux', '#eb6834'),
      ND: css('--nous-d', '#12a39a'), ED: css('--eux-d', '#b8439b'), R: css('--perte', '#d22f2f') };
  }
  // Perte de Nous = rouge (= récup adverse) ; perte d'Eux = bleu (= notre récup).
  function perteColor(P, team) { return team === 'N' ? P.R : P.N; }
  function hexToRgb(h) {
    h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join('');
    const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function fit(canvas) {
    const cw = canvas.clientWidth || 600, ch = Math.round((cw - 2 * M) * W / L + 2 * M);
    const dpr = window.devicePixelRatio || 1;
    canvas.style.height = ch + 'px';
    if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) {
      canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
    }
    const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const g = { cw: cw, ch: ch, s: (cw - 2 * M) / L, ox: M, oy: M };
    canvas._g = g; return { ctx: ctx, g: g };
  }

  // ---- densité gaussienne sur une grille ----
  function density(pts) {
    const cell = C.heat.cell, sg = C.heat.sigma, nx = Math.ceil(L / cell), ny = Math.ceil(W / cell);
    const a = new Float32Array(nx * ny), r = Math.ceil(3 * sg / cell);
    pts.forEach(function (p) {
      const cx = Math.floor(p.x / cell), cy = Math.floor(p.y / cell);
      for (let j = Math.max(0, cy - r); j <= Math.min(ny - 1, cy + r); j++) {
        for (let i = Math.max(0, cx - r); i <= Math.min(nx - 1, cx + r); i++) {
          const dx = (i + 0.5) * cell - p.x, dy = (j + 0.5) * cell - p.y;
          a[j * nx + i] += Math.exp(-(dx * dx + dy * dy) / (2 * sg * sg));
        }
      }
    });
    return { a: a, nx: nx, ny: ny };
  }
  function paintGrid(ctx, g, nx, ny, rgbaAt) {
    const off = document.createElement('canvas'); off.width = nx; off.height = ny;
    const octx = off.getContext('2d'), img = octx.createImageData(nx, ny);
    for (let i = 0; i < nx * ny; i++) {
      const c = rgbaAt(i); img.data[4 * i] = c[0]; img.data[4 * i + 1] = c[1]; img.data[4 * i + 2] = c[2]; img.data[4 * i + 3] = c[3];
    }
    octx.putImageData(img, 0, 0);
    ctx.save(); ctx.beginPath(); ctx.rect(g.ox, g.oy, L * g.s, W * g.s); ctx.clip();
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(off, g.ox, g.oy, nx * C.heat.cell * g.s, ny * C.heat.cell * g.s);
    ctx.restore();
  }
  // heatmap une teinte : transparent -> saturé
  function heat(ctx, g, pts, hex) {
    if (!pts.length) return;
    const d = density(pts), rgb = hexToRgb(hex);
    let max = 0; for (let i = 0; i < d.a.length; i++) if (d.a[i] > max) max = d.a[i];
    const ref = Math.max(max, C.heat.minRef);
    paintGrid(ctx, g, d.nx, d.ny, function (i) {
      return [rgb[0], rgb[1], rgb[2], Math.round(Math.pow(Math.min(1, d.a[i] / ref), 0.75) * 215)];
    });
  }
  // Carte divergente pondérée par le volume.
  // COULEUR = taux de perte local comparé à la moyenne de l'équipe : bleu = plus sûr, gris = dans la moyenne, rouge = plus risqué
  // (le taux est tiré vers la moyenne quand il y a peu d'événements, pour ne pas s'emballer sur 2 ballons).
  // OPACITÉ = volume local : 2 passes perdues restent invisibles, une zone à 70 passes ressort toujours, même dans la moyenne.
  function diverging(ctx, g, playPts, losePts, hexPos, hexNeg, hexMid) {
    const A = density(playPts), B = density(losePts), pos = hexToRgb(hexPos), neg = hexToRgb(hexNeg), mid = hexToRgb(hexMid);
    const p0 = losePts.length / (playPts.length + losePts.length), K = C.heat.shrink, len = A.a.length;
    const z = new Float32Array(len), vol = new Float32Array(len);
    let nMax = 0;
    for (let i = 0; i < len; i++) { const n = A.a[i] + B.a[i]; if (n > nMax) nMax = n; }
    for (let i = 0; i < len; i++) {
      const n = A.a[i] + B.a[i];
      if (n < 0.3) continue;
      const ps = (B.a[i] + K * p0) / (n + K);
      z[i] = Math.max(-1.5, Math.min(1.5, Math.log(ps / p0) / Math.LN2)) / 1.5;     // -1 = bien plus sûr, +1 = bien plus risqué
      vol[i] = n / nMax;
    }
    paintGrid(ctx, g, A.nx, A.ny, function (i) {
      if (vol[i] < C.heat.volMin) return [0, 0, 0, 0];
      const t = Math.pow(Math.abs(z[i]), 0.8), end = z[i] > 0 ? neg : pos;
      return [Math.round(mid[0] + (end[0] - mid[0]) * t), Math.round(mid[1] + (end[1] - mid[1]) * t), Math.round(mid[2] + (end[2] - mid[2]) * t),
        Math.round(Math.pow(vol[i], C.heat.volPow) * 225)];
    });
  }

  // ---- marques ----
  function arrow(ctx, g, ev, flip, color, alpha, lw, dash) {
    const a = P_.toScreen(g, ev.x, ev.y, flip), b = P_.toScreen(g, ev.x2, ev.y2, flip);
    ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw;
    ctx.setLineDash(dash || []);
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), h = 5 + lw * 1.5;
    ctx.beginPath(); ctx.moveTo(b[0], b[1]);
    ctx.lineTo(b[0] - h * Math.cos(ang - 0.4), b[1] - h * Math.sin(ang - 0.4));
    ctx.lineTo(b[0] - h * Math.cos(ang + 0.4), b[1] - h * Math.sin(ang + 0.4));
    ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.arc(a[0], a[1], 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  function zigzag(ctx, g, ev, flip, color, alpha, lw, dash) {
    const a = P_.toScreen(g, ev.x, ev.y, flip), b = P_.toScreen(g, ev.x2, ev.y2, flip);
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
    if (len < 2) return;
    const nx = -dy / len, ny = dx / len, n = Math.max(2, Math.round(len / 9)), amp = 4.5;
    ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw;
    ctx.lineJoin = 'round'; ctx.setLineDash(dash || []);
    ctx.beginPath(); ctx.moveTo(a[0], a[1]);
    for (let i = 1; i < n; i++) {
      const t = i / n, s = i % 2 ? amp : -amp;
      ctx.lineTo(a[0] + dx * t + nx * s, a[1] + dy * t + ny * s);
    }
    ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
    const ang = Math.atan2(dy, dx), h = 6 + lw * 1.5;
    ctx.beginPath(); ctx.moveTo(b[0], b[1]);
    ctx.lineTo(b[0] - h * Math.cos(ang - 0.45), b[1] - h * Math.sin(ang - 0.45));
    ctx.lineTo(b[0] - h * Math.cos(ang + 0.45), b[1] - h * Math.sin(ang + 0.45));
    ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.arc(a[0], a[1], 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  function cross(ctx, x, y, color, alpha) {
    ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x - 5, y - 5); ctx.lineTo(x + 5, y + 5); ctx.moveTo(x + 5, y - 5); ctx.lineTo(x - 5, y + 5); ctx.stroke();
    ctx.restore();
  }
  function colorOf(P, ev) { return S_.DESEQ.indexOf(ev.kind) >= 0 ? P[ev.team + 'D'] : P[ev.team]; }
  function ring(ctx, x, y, r, surf) {   // anneau de séparation 2px
    ctx.beginPath(); ctx.arc(x, y, r + 2, 0, Math.PI * 2); ctx.fillStyle = surf; ctx.fill();
  }
  function marker(ctx, g, ev, flip, color, alpha, P) {
    const p = P_.toScreen(g, ev.x, ev.y, flip), x = p[0], y = p[1];
    if (ev.kind === 'perte') { cross(ctx, x, y, perteColor(P, ev.team), alpha); return; }
    ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.strokeStyle = color; ctx.lineWidth = 2.5;
    if (ev.kind === 'recup') {
      ctx.beginPath(); ctx.moveTo(x, y - 7); ctx.lineTo(x + 6.5, y + 5); ctx.lineTo(x - 6.5, y + 5); ctx.closePath(); ctx.fill();
    } else if (ev.kind === 'shot') {
      if (ev.res === 'hors') { ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.stroke(); }
      else if (ev.res === 'cadre') { ring(ctx, x, y, 6, P.surface); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill(); }
      else {
        ring(ctx, x, y, 9, P.surface); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = P.surface; ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.restore();
  }
  function drawEvent(ctx, g, ev, flip, alpha, P) {
    const color = colorOf(P, ev);
    if (ev.kind === 'carry_deseq') zigzag(ctx, g, ev, flip, color, alpha, 2.6, ev.ok ? null : [5, 4]);
    else if (C.kinds[ev.kind].two) arrow(ctx, g, ev, flip, color, alpha, ev.kind === 'pass' ? 1.6 : 2.8, ev.ok ? null : [5, 4]);
    else { marker(ctx, g, ev, flip, color, alpha, P); return; }
    if (!ev.ok) {                                     // action ratée : croix (rouge = perte Nous, bleue = perte Eux)
      const e = P_.toScreen(g, ev.x2, ev.y2, flip);
      cross(ctx, e[0], e[1], perteColor(P, ev.team), alpha);
    }
  }

  // ---- couches d'analyse (6 cartes) ----
  const LAYERS = {
    jeu: 'Où ça part (départs de passes)',
    arr: 'Où ça arrive (arrivées de passes)',
    pertePasse: 'Pertes sur erreurs techniques',
    duel: 'Duels gagnés / perdus',
    perte: 'Pertes de balle',
    recup: 'Récupérations de balle',
    diff: 'Zones sûres / à risque',
    deseq: 'Déséquilibres',
    shots: 'Frappes'
  };
  // Titre d'une carte (Eux : ses pertes sur passes = nos récupérations sur leurs erreurs).
  function layerTitle(layer, team) {
    if (layer === 'duel') return LAYERS.duel;
    if (layer === 'pertePasse') return team === 'N' ? 'Nos pertes - Sur erreurs techniques' : 'Nos récupérations - Sur erreurs techniques de l\'ADV';
    return (team === 'N' ? 'Nous' : 'Eux') + ' — ' + LAYERS[layer];
  }
  function layerEvents(events, team, half, layer, result) {
    if (layer === 'pertePasse') {
      return S_.select(S_.withDerived(events), team, half).filter(function (e) { return e.kind === 'perte' && e.derived === 'pass'; });
    }
    if (layer === 'perte' || layer === 'recup') {
      return S_.select(S_.withDerived(events), team, half).filter(function (e) { return e.kind === layer; });
    }
    const ev = S_.select(events, team, half);
    if (layer === 'jeu' || layer === 'arr') return ev.filter(S_.isPass).filter(function (e) { return S_.byResult(e, result); });
    if (layer === 'deseq') return ev.filter(function (e) { return S_.DESEQ.indexOf(e.kind) >= 0 && S_.byResult(e, result); });
    if (layer === 'shots') return ev.filter(function (e) { return e.kind === 'shot'; });
    return [];
  }
  function drawAnalysis(canvas, team, events, half, layer, result) {
    const f = fit(canvas), ctx = f.ctx, g = f.g, P = pal();
    P_.bg(ctx, g, P.pitch, P.stripe);
    if (layer === 'diff') {
      const play = layerEvents(events, team, half, 'jeu', 'all'), lose = layerEvents(events, team, half, 'perte', 'all');
      const info = '(' + play.length + ' passes · ' + lose.length + ' pertes)';
      if (play.length < 8 || lose.length < 3) {
        P_.lines(ctx, g, P.line);
        ctx.fillStyle = P.ink2; ctx.font = '13px system-ui, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Pas assez de données', g.cw / 2, g.ch / 2 - 8, g.cw - 20);
        ctx.fillText('(au moins 8 passes et 3 pertes)', g.cw / 2, g.ch / 2 + 10, g.cw - 20);
        return info;
      }
      diverging(ctx, g, play.map(function (e) { return { x: e.x, y: e.y }; }), lose.map(function (e) { return { x: e.x, y: e.y }; }), P.N, P.R, P.line);
      P_.lines(ctx, g, P.line);
      return info;
    }
    if (layer === 'duel') {
      const d = S_.duels(events, half), n = d.won.length + d.lost.length;
      const info = '(' + n + ' duels' + (n ? ' · ' + Math.round(100 * d.won.length / n) + ' % gagnés' : '') + ')';
      if (n < 6 || !d.won.length || !d.lost.length) {
        P_.lines(ctx, g, P.line);
        ctx.fillStyle = P.ink2; ctx.font = '13px system-ui, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Pas assez de duels codés', g.cw / 2, g.ch / 2 - 8, g.cw - 20);
        ctx.fillText('(au moins 6, dont des Z et des E)', g.cw / 2, g.ch / 2 + 10, g.cw - 20);
        return info;
      }
      const xy = function (e) { return { x: e.x, y: e.y }; };
      diverging(ctx, g, d.won.map(xy), d.lost.map(xy), P.N, P.R, P.line);
      P_.lines(ctx, g, P.line);
      d.won.concat(d.lost).forEach(function (e) {           // chaque duel = un petit point (bleu gagné, rouge perdu)
        const p = P_.toScreen(g, e.x, e.y, false), win = e.kind === 'recup';
        ctx.beginPath(); ctx.arc(p[0], p[1], 5, 0, Math.PI * 2); ctx.fillStyle = P.surface; ctx.fill();
        ctx.beginPath(); ctx.arc(p[0], p[1], 3.2, 0, Math.PI * 2); ctx.fillStyle = win ? P.N : P.R; ctx.fill();
      });
      return info;
    }
    const list = layerEvents(events, team, half, layer, result);
    const isHeat = layer === 'jeu' || layer === 'arr' || layer === 'perte' || layer === 'recup' || layer === 'pertePasse';
    if (isHeat) {
      const hex = layer === 'perte' || layer === 'pertePasse' ? perteColor(P, team) : P[team];
      heat(ctx, g, list.map(function (e) { return layer === 'arr' ? { x: e.x2, y: e.y2 } : { x: e.x, y: e.y }; }), hex);
    }
    P_.lines(ctx, g, P.line);
    if (!isHeat) list.forEach(function (e) { drawEvent(ctx, g, e, false, 0.78, P); });
    return '(' + list.length + ')';
  }

  // ---- vue live ----
  function drawLive(canvas, st) {
    const f = fit(canvas), ctx = f.ctx, g = f.g, P = pal();
    P_.bg(ctx, g, P.pitch, P.stripe); P_.lines(ctx, g, P.line);
    const recent = st.events.slice(-C.recentShown).concat(st.prov ? [st.prov.ev] : []);
    recent.forEach(function (e, i) {
      const age = recent.length - 1 - i;
      drawEvent(ctx, g, e, st.flip, Math.max(0.18, 1 - age * 0.07), P);
    });
    const pend = st.pending;
    if (pend) {
      const a = P_.toScreen(g, pend.x, pend.y, st.flip), col = P[pend.team];
      ctx.save(); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 2.5;
      if (st.mouse) {
        const b = P_.toScreen(g, st.mouse[0], st.mouse[1], st.flip);
        ctx.setLineDash([6, 5]); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.beginPath(); ctx.arc(a[0], a[1], 8, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(a[0], a[1], 2.5, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
  }

  return { fit: fit, drawAnalysis: drawAnalysis, drawLive: drawLive, layerEvents: layerEvents, layerTitle: layerTitle, LAYERS: LAYERS, pal: pal, perteColor: perteColor, hexToRgb: hexToRgb };
})();
