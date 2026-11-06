/* CHART : barres groupées Nous / Eux par tranche de temps (SVG, couleurs via variables CSS). */
FC.chart = (function () {
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  function bars(box, labels, a, b, title) {
    const W = 640, H = 230, L = 30, R = 8, T = 16, B = 28, n = labels.length;
    const max = Math.max(1, Math.max.apply(null, a.concat(b)));
    const top = max <= 4 ? max : Math.ceil(max / 2) * 2;
    const gw = (W - L - R) / n, bw = Math.min(26, (gw - 10) / 2);
    const y = function (v) { return T + (H - T - B) * (1 - v / top); };
    let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="' + esc(title) + '" style="display:block;max-width:760px">';
    [0, top / 2, top].forEach(function (g) {
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(g) + '" y2="' + y(g) + '" style="stroke:var(--rule)"/>' +
        '<text x="' + (L - 6) + '" y="' + (y(g) + 4) + '" text-anchor="end" font-size="11" style="fill:var(--ink2)">' + (Math.round(g * 10) / 10) + '</text>';
    });
    labels.forEach(function (lab, i) {
      const cx = L + gw * (i + 0.5);
      [[a[i], 'var(--nous)', -bw - 1], [b[i], 'var(--eux)', 1]].forEach(function (d) {
        const v = d[0], x = cx + d[2], h = (H - T - B) * v / top;
        if (v > 0) {
          s += '<rect x="' + x + '" y="' + (y(v)) + '" width="' + bw + '" height="' + h + '" rx="2" style="fill:' + d[1] + '"/>' +
            '<text x="' + (x + bw / 2) + '" y="' + (y(v) - 4) + '" text-anchor="middle" font-size="11" font-weight="600" style="fill:var(--ink)">' + v + '</text>';
        }
      });
      s += '<text x="' + cx + '" y="' + (H - 9) + '" text-anchor="middle" font-size="11" style="fill:var(--ink2)">' + esc(lab) + '</text>';
    });
    box.innerHTML = s + '</svg>';
  }
  // Courbe de momentum : aire bleue au-dessus de 0 (avantage Nous), orange en dessous (avantage Eux). d = FC.momentum.compute.
  function momentum(box, d, title) {
    const W = 900, H = 260, L = 40, R = 12, T = 24, B = 30, fmt = FC.momentum.fmt;
    const maxAbs = d.points.reduce(function (m, p) { return Math.max(m, Math.abs(p.v)); }, 0);
    const top = Math.max(6, Math.ceil(maxAbs / 2) * 2);
    const X = function (x) { return L + (W - L - R) * x / d.total; };
    const Y = function (v) { return T + (H - T - B) * (1 - (v + top) / (2 * top)); };
    const y0 = Y(0);
    let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="' + esc(title) + '" style="display:block;max-width:1200px">' +
      '<defs><clipPath id="fcm-up"><rect x="0" y="0" width="' + W + '" height="' + y0 + '"/></clipPath>' +
      '<clipPath id="fcm-dn"><rect x="0" y="' + y0 + '" width="' + W + '" height="' + (H - y0) + '"/></clipPath></defs>';
    [top, 0, -top].forEach(function (g) {
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(g) + '" y2="' + Y(g) + '" style="stroke:var(--rule)' + (g ? ';stroke-dasharray:3 3' : '') + '"/>';
    });
    s += '<text x="' + (L - 6) + '" y="' + (T + 4) + '" text-anchor="end" font-size="11" font-weight="600" style="fill:var(--nous)">Nous</text>' +
      '<text x="' + (L - 6) + '" y="' + (H - B + 2) + '" text-anchor="end" font-size="11" font-weight="600" style="fill:var(--eux)">Eux</text>';
    d.segs.forEach(function (sg, i) {
      const pts = d.points.filter(function (p) { return p.half === sg.half; });
      const line = pts.map(function (p) { return X(p.x) + ',' + Y(p.v); }).join(' ');
      const area = X(pts[0].x) + ',' + y0 + ' ' + line + ' ' + X(pts[pts.length - 1].x) + ',' + y0;
      s += '<polygon points="' + area + '" clip-path="url(#fcm-up)" style="fill:var(--nous);opacity:.85"/>' +
        '<polygon points="' + area + '" clip-path="url(#fcm-dn)" style="fill:var(--eux);opacity:.85"/>' +
        '<polyline points="' + line + '" fill="none" stroke-linejoin="round" style="stroke:var(--ink);stroke-width:1.2"/>';
      for (let m = Math.ceil(sg.from / 15) * 15; m <= sg.to; m += 15) {
        const x = X(sg.x0 + m);
        s += '<line x1="' + x + '" x2="' + x + '" y1="' + (H - B) + '" y2="' + (H - B + 4) + '" style="stroke:var(--ink2)"/>' +
          '<text x="' + x + '" y="' + (H - 10) + '" text-anchor="middle" font-size="11" style="fill:var(--ink2)">' + m + '\'</text>';
      }
      if (i > 0) {
        const xm = X(sg.x0 + sg.from) - (W - L - R) * 1.5 / d.total;
        s += '<line x1="' + xm + '" x2="' + xm + '" y1="' + T + '" y2="' + (H - B) + '" style="stroke:var(--ink2);stroke-dasharray:2 4"/>';
      }
    });
    d.goals.forEach(function (g) {
      const x = X(g.x), up = g.team === 'N', cy = up ? T - 9 : H - B + 9;
      s += '<line x1="' + x + '" x2="' + x + '" y1="' + T + '" y2="' + (H - B) + '" style="stroke:var(' + (up ? '--nous' : '--eux') + ');stroke-width:1;opacity:.6"/>' +
        '<circle cx="' + x + '" cy="' + (up ? T - 8 : H - B + 14) + '" r="5" style="fill:var(--surface);stroke:var(' + (up ? '--nous' : '--eux') + ');stroke-width:2"><title>But ' +
        (up ? 'de Nous' : 'd\'Eux') + ' à ' + g.min + '\'</title></circle>';
    });
    const bw = (W - L - R) / d.total;
    d.points.forEach(function (p) {
      s += '<rect x="' + (X(p.x) - bw / 2) + '" y="' + T + '" width="' + bw + '" height="' + (H - T - B) + '" fill="transparent"><title>' + p.min + '\' : ' +
        (p.v > 0 ? 'avantage Nous +' + fmt(p.v) : p.v < 0 ? 'avantage Eux +' + fmt(-p.v) : 'équilibre') + ' (Nous ' + fmt(p.n) + ' · Eux ' + fmt(p.e) + ')</title></rect>';
    });
    box.innerHTML = s + '</svg>';
  }
  return { bars: bars, momentum: momentum };
})();
