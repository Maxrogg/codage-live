const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  // faux « claude » : base en mémoire (partagée entre rechargements via window.name n'est pas fiable -> on stocke dans sessionStorage)
  await ctx.addInitScript(() => {
    const K = 'fakedb', rd = () => JSON.parse(sessionStorage.getItem(K) || '{}'), wr = o => sessionStorage.setItem(K, JSON.stringify(o));
    window.__log = [];
    window.claude = { use: async (n) => {
      if (n === 'user') return { id: async () => 'u1' };
      if (n === 'downloads') return { save: async (r) => { window.__log.push('dl:' + r.filename + ':' + r.data.length); return { status: 'saved' }; } };
      if (n === 'db') return { collection: (path) => ({
        get: async () => { const o = rd(); return { docs: Object.keys(o).map(id => ({ id, exists: true, data: () => o[id] })) }; },
        doc: (id) => ({ set: async (d) => { window.__log.push('set:' + id); const o = rd(); o[id] = JSON.parse(JSON.stringify(d)); wr(o); },
                        delete: async () => { window.__log.push('del:' + id); const o = rd(); delete o[id]; wr(o); } }) }) };
      return null; } };
  });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message)); await p.addInitScript(()=>document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('details').forEach(d=>d.open=true)));
  await p.goto('file:///home/claude/codage-live/index.html'); await p.waitForTimeout(400); await p.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
  console.log('statut initial:', await p.textContent('#save-state'));
  await p.evaluate(() => { FC.store.setInfo({ adv: 'Test', sn: 1, se: 0 }); FC.store.add({ kind: 'recup', team: 'N', x: 50, y: 30 }); });
  await p.waitForTimeout(2000);
  console.log('statut après écriture:', await p.textContent('#save-state'), '| log:', await p.evaluate(() => window.__log.join(',')));
  // simule un autre appareil : efface le local, recharge -> doit revenir du « cloud »
  await p.evaluate(() => localStorage.clear()); await p.reload(); await p.waitForTimeout(800);
  console.log('après effacement local + reload : matchs =', await p.evaluate(() => FC.store.matches().length),
    '| adv =', await p.evaluate(() => FC.store.matches().map(m => m.info.adv + ':' + m.events.length).join(';')));
  // téléchargement
  await p.click('#btn-dl-csv'); await p.waitForTimeout(200);
  console.log('download log:', await p.evaluate(() => window.__log.filter(x => x.startsWith('dl')).join(',')));
  // suppression propagée
  await p.click('#tab-matches'); await p.locator('button[data-del]').first().click(); await p.locator('button.danger[data-del]').click(); await p.waitForTimeout(2000);
  console.log('log après suppression:', await p.evaluate(() => window.__log.slice(-3).join(',')), '| statut:', await p.textContent('#save-state'));
  console.log('errors:', errs); await b.close();
})();
