const fs=require('fs'),vm=require('vm'),assert=require('assert');
global.window=global; global.document={}; global.localStorage={};
for(const f of ['config','stats','momentum']) vm.runInThisContext(fs.readFileSync('/home/claude/codage-live/js/'+f+'.js','utf8'));
const S=FC.stats, X=e=>Math.round(S.xg(e)*100)/100;
// xG : repères
const pen=X({kind:'shot',team:'N',x:94,y:34}), six=X({kind:'shot',team:'N',x:99.5,y:34}), far=X({kind:'shot',team:'N',x:80,y:34}), wide=X({kind:'shot',team:'N',x:103,y:5});
console.log('xG penalty',pen,'| 6 m',six,'| 25 m',far,'| angle fermé',wide);
assert(pen>0.15&&pen<0.3); assert(six>0.4); assert(far<0.06); assert(wide<pen);
assert.strictEqual(X({kind:'shot',team:'E',x:11,y:34}),pen);                      // Eux : symétrique
// CPA : type selon position
assert.strictEqual(S.cpaType('N',104,1),'corner'); assert.strictEqual(S.cpaType('E',1,67),'corner');
assert.strictEqual(S.cpaType('N',50,0.5),'touche'); assert.strictEqual(S.cpaType('N',80,30),'cf');
// suite d'un CPA
const ev=[{kind:'cpa',team:'N',x:104,y:1,half:1,t:60000},{kind:'pass',team:'N',x:100,y:5,x2:96,y2:34,ok:true,half:1,t:63000},{kind:'shot',team:'N',x:96,y:34,res:'but',half:1,t:64000},
 {kind:'cpa',team:'N',x:80,y:30,half:1,t:200000},{kind:'shot',team:'N',x:96,y:34,res:'hors',half:1,t:230000},
 {kind:'cpa',team:'E',x:2,y:67,half:1,t:300000},{kind:'shot',team:'E',x:8,y:34,res:'cadre',half:1,t:305000}];
const s=S.summary(ev,'N',0), e=S.summary(ev,'E',0);
console.log('CPA Nous',JSON.stringify(s.cpa),'| Eux',JSON.stringify(e.cpa),'| xG',s.shots.xg,e.shots.xg);
assert.deepStrictEqual([s.cpa.n,s.cpa.corner,s.cpa.cf,s.cpa.frappes,s.cpa.buts],[2,1,1,1,1]);   // 2e CPA : frappe 30 s après = hors délai
assert.deepStrictEqual([e.cpa.n,e.cpa.frappes],[1,1]);
assert.strictEqual(S.shotOrigins(ev,'N',0).cpa,1);
assert(S.bilan(ev,0).duel.some(x=>/CPA/.test(x.text)) && S.bilan(ev,0).duel.some(x=>/xG/.test(x.text)));
assert.strictEqual(FC.momentum.weightOf(ev[0]),0);
console.log('cpa/xg OK');
