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
  return { bars: bars };
})();
