/* PITCH : géométrie du terrain (conversion écran <-> mètres) et tracé des lignes. */
FC.pitch = (function () {
  const L = FC.CONFIG.pitch.L, W = FC.CONFIG.pitch.W;

  // flip = terrain tourné de 180° (2e mi-temps : on garde la vue réelle du banc)
  function toScreen(g, x, y, flip) {
    const fx = flip ? L - x : x, fy = flip ? W - y : y;
    return [g.ox + fx * g.s, g.oy + fy * g.s];
  }
  function toField(g, px, py, flip) {
    let x = (px - g.ox) / g.s, y = (py - g.oy) / g.s;
    x = Math.max(0, Math.min(L, x)); y = Math.max(0, Math.min(W, y));
    return flip ? [L - x, W - y] : [x, y];
  }

  function bg(ctx, g, color) {
    ctx.fillStyle = color; ctx.fillRect(0, 0, g.cw, g.ch);
  }

  function lines(ctx, g, color) {
    const s = g.s, X = function (x) { return g.ox + x * s; }, Y = function (y) { return g.oy + y * s; };
    ctx.save();
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash([]);
    const rect = function (x, y, w, h) { ctx.strokeRect(X(x), Y(y), w * s, h * s); };
    rect(0, 0, L, W);
    ctx.beginPath(); ctx.moveTo(X(L / 2), Y(0)); ctx.lineTo(X(L / 2), Y(W)); ctx.stroke();
    ctx.beginPath(); ctx.arc(X(L / 2), Y(W / 2), 9.15 * s, 0, Math.PI * 2); ctx.stroke();
    const pa = 40.32, ga = 18.32;
    rect(0, (W - pa) / 2, 16.5, pa); rect(L - 16.5, (W - pa) / 2, 16.5, pa);
    rect(0, (W - ga) / 2, 5.5, ga); rect(L - 5.5, (W - ga) / 2, 5.5, ga);
    [[11, W / 2], [L - 11, W / 2], [L / 2, W / 2]].forEach(function (p) {
      ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 2, 0, Math.PI * 2); ctx.fill();
    });
    const a = Math.acos((16.5 - 11) / 9.15);
    ctx.beginPath(); ctx.arc(X(11), Y(W / 2), 9.15 * s, -a, a); ctx.stroke();
    ctx.beginPath(); ctx.arc(X(L - 11), Y(W / 2), 9.15 * s, Math.PI - a, Math.PI + a); ctx.stroke();
    ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(X(0), Y(W / 2 - 3.66)); ctx.lineTo(X(0), Y(W / 2 + 3.66)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(X(L), Y(W / 2 - 3.66)); ctx.lineTo(X(L), Y(W / 2 + 3.66)); ctx.stroke();
    ctx.restore();
  }

  return { toScreen: toScreen, toField: toField, bg: bg, lines: lines };
})();
