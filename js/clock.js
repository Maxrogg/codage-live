/* CLOCK : chrono de match. */
FC.clock = (function () {
  let running = false, base = 0, startedAt = 0;
  function now() { return base + (running ? Date.now() - startedAt : 0); }
  return {
    now: now,
    isRunning: function () { return running; },
    set: function (ms) { base = ms; startedAt = Date.now(); },
    start: function () { if (!running) { running = true; startedAt = Date.now(); } },
    pause: function () { if (running) { base = now(); running = false; } },
    toggle: function () { if (running) this.pause(); else this.start(); return running; },
    fmt: function (ms) {
      const s = Math.floor(ms / 1000), m = Math.floor(s / 60);
      return String(m).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
    }
  };
})();
