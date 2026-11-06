const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1360, height: 900 } });
  const errs=[]; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///home/claude/codage-live/index.html');
  const r = await p.evaluate(() => {
    const ev=[]; for (let i=0;i<900;i++){ const k=['pass','pass','pass','pass_deseq','recup','perte','shot'][i%7];
      ev.push({id:i+1,kind:k,team:i%3?'N':'E',x:10+(i*37)%90,y:5+(i*13)%58,x2:12+(i*29)%90,y2:4+(i*17)%60,ok:i%4!==0,res:k==='shot'?'cadre':undefined,half:i<450?1:2,t:(i%450)*6000+(i<450?0:2700000)});}
    const m=FC.store.current(); m.events=ev; m.seq=900;
    let t=performance.now(); FC.store.add({kind:'recup',team:'N',x:50,y:30}); const add=performance.now()-t;
    t=performance.now(); for(let i=0;i<5;i++) FC.store.add({kind:'recup',team:'N',x:50,y:30}); const add5=(performance.now()-t)/5;
    return {add, add5, size: JSON.stringify(m).length};
  });
  for (const t of ['analysis','bilan']) { const t0=Date.now(); await p.click('#tab-'+t); await p.waitForTimeout(50); console.log(t, Date.now()-t0,'ms'); }
  // ancien type inconnu


  console.log(JSON.stringify(r), 'errs:', errs.slice(0,3));
  await b.close();
})();
