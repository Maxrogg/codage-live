/* DESSIN : flèches, traits et cercles par-dessus la vidéo en pause, pour montrer un placement aux joueurs.
   Rien n'est enregistré : les dessins appartiennent à l'image affichée et s'effacent dès que la vidéo repart.
   Formes en coordonnées 0..1 du cadre vidéo : elles suivent un changement de taille (plein écran). */
FC.dessin = (function () {
  const $ = function (id) { return document.getElementById(id); };
  const COLORS = { jaune: '#ffd21f', rouge: '#ff3b3b', bleu: '#3d8ce8', blanc: '#ffffff' };
  let on = false, tool = 'arrow', color = 'jaune', shapes = [], cur = null, cv = null, vid = null;

  function size() {
    const r = vid.getBoundingClientRect(), st = vid.parentNode.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.style.left = (r.left - st.left) + 'px'; cv.style.top = (r.top - st.top) + 'px';   // la vidéo peut être centrée (plein écran)
    cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px';
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    return { w: r.width, h: r.height, dpr: dpr };
  }
  function draw() {
    if (!cv) return;
    const s = size(), ctx = cv.getContext('2d');
    ctx.setTransform(s.dpr, 0, 0, s.dpr, 0, 0); ctx.clearRect(0, 0, s.w, s.h);
    shapes.concat(cur ? [cur] : []).forEach(function (sh) {
      const a = [sh.a[0] * s.w, sh.a[1] * s.h], b = [sh.b[0] * s.w, sh.b[1] * s.h], lw = Math.max(3, s.w / 220);
      ctx.save(); ctx.strokeStyle = ctx.fillStyle = COLORS[sh.c]; ctx.lineWidth = lw; ctx.lineCap = 'round';
      ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 4;
      ctx.beginPath();
      if (sh.t === 'circle') {                          // ellipse tracée dans le rectangle glissé (joueur, zone)
        ctx.ellipse((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.abs(b[0] - a[0]) / 2 + 1, Math.abs(b[1] - a[1]) / 2 + 1, 0, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        if (sh.t === 'dash') ctx.setLineDash([lw * 3, lw * 2.2]);
        ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
        if (sh.t === 'arrow' || sh.t === 'dash') {
          const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), h = lw * 4.5;
          ctx.beginPath(); ctx.moveTo(b[0], b[1]);
          ctx.lineTo(b[0] - h * Math.cos(ang - 0.45), b[1] - h * Math.sin(ang - 0.45));
          ctx.lineTo(b[0] - h * Math.cos(ang + 0.45), b[1] - h * Math.sin(ang + 0.45));
          ctx.closePath(); ctx.fill();
        }
      }
      ctx.restore();
    });
  }
  function pos(e) { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]; }

  function setOn(v) {
    on = v; if (on) vid.pause();
    $('vd-stage').classList.toggle('drawing', on); $('dr-bar').hidden = !on;
    $('dr-toggle').textContent = on ? '✓ Fin du dessin' : '✎ Dessiner'; $('dr-toggle').classList.toggle('pri', on);
    draw();
  }
  function clear() { shapes = []; cur = null; draw(); }
  function renderBar() {
    Array.prototype.forEach.call($('dr-bar').querySelectorAll('[data-tool]'), function (b) { b.classList.toggle('on', b.dataset.tool === tool); });
    Array.prototype.forEach.call($('dr-bar').querySelectorAll('[data-color]'), function (b) { b.classList.toggle('on', b.dataset.color === color); });
  }

  function init() {
    cv = $('dr-canvas'); vid = $('vd');
    cv.addEventListener('pointerdown', function (e) {
      if (!on) return; e.preventDefault(); cv.setPointerCapture(e.pointerId);
      const p = pos(e); cur = { t: tool, c: color, a: p, b: p }; draw();
    });
    cv.addEventListener('pointermove', function (e) { if (cur) { cur.b = pos(e); draw(); } });
    cv.addEventListener('pointerup', function () {
      if (!cur) return;
      if (Math.hypot(cur.b[0] - cur.a[0], cur.b[1] - cur.a[1]) > 0.01) shapes.push(cur);   // simple clic : rien
      cur = null; draw();
    });
    vid.addEventListener('play', function () { if (on) setOn(false); clear(); });   // la vidéo repart : l'image a changé
    vid.addEventListener('seeked', function () { if (!on) clear(); });
    $('dr-toggle').onclick = function () { if (!vid.src) { FC.ui.flash('Ouvre d\'abord le fichier vidéo'); return; } setOn(!on); };
    $('dr-bar').onclick = function (e) {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.tool) tool = b.dataset.tool;
      else if (b.dataset.color) color = b.dataset.color;
      else if (b.dataset.act === 'undo') { shapes.pop(); draw(); }
      else if (b.dataset.act === 'clear') clear();
      renderBar();
    };
    $('dr-full').onclick = function () {               // plein écran du cadre (vidéo + dessins), pas du lecteur seul
      const st = $('vd-stage');
      if (document.fullscreenElement) document.exitFullscreen();
      else if (st.requestFullscreen) st.requestFullscreen().catch(function () { FC.ui.flash('Plein écran refusé'); });
    };
    document.addEventListener('fullscreenchange', function () { setTimeout(draw, 60); });
    window.addEventListener('resize', draw);
    renderBar();
  }
  return { init: init, clear: clear, isOn: function () { return on; } };
})();
