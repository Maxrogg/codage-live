const fs=require('fs'),vm=require('vm'),assert=require('assert');
global.window=global; global.document={}; global.localStorage={};
for(const f of ['config','stats']) vm.runInThisContext(fs.readFileSync('/home/claude/codage-live/js/'+f+'.js','utf8'));
const S=FC.stats;
// --- entrées : Nous attaque vers x=105. dernier tiers = x>=70 ; surface = x>=88.5, |y-34|<=20.16
const ev=[
 {kind:'pass',team:'N',x:60,y:34,x2:75,y2:34,ok:true,half:1,t:1000},       // entrée dernier tiers
 {kind:'pass',team:'N',x:75,y:34,x2:80,y2:34,ok:true,half:1,t:2000},       // déjà dedans : pas d'entrée
 {kind:'pass_deseq',team:'N',x:80,y:20,x2:95,y2:30,ok:true,half:1,t:3000}, // entrée surface (le tiers: déjà dans le tiers)
 {kind:'carry_deseq',team:'N',x:60,y:10,x2:90,y2:34,ok:true,half:1,t:4000},// entrée tiers + surface
 {kind:'pass',team:'N',x:60,y:34,x2:92,y2:34,ok:false,half:1,t:5000},      // ratée : pas d'entrée
 // Eux attaquent vers x=0 : surface = x<=16.5
 {kind:'pass',team:'E',x:40,y:34,x2:10,y2:34,ok:true,half:1,t:6000}];     // entrée tiers (x2<=35) + surface
let a=S.entries(ev,'N',0), b=S.entries(ev,'E',0);
assert.deepStrictEqual(a,{tiers:2,surf:2}); assert.deepStrictEqual(b,{tiers:1,surf:1});
assert(S.inBox('N',100,34)&&!S.inBox('N',80,34)&&S.inBox('E',5,34)&&!S.inBox('N',100,2));
// --- origine des frappes (chrono)
const o=[
 {kind:'recup',team:'N',x:60,y:34,half:1,t:10000},
 {kind:'shot',team:'N',x:95,y:34,res:'hors',half:1,t:18000},               // transition (8 s)
 {kind:'pass_deseq',team:'N',x:50,y:34,x2:80,y2:34,ok:true,half:1,t:60000},
 {kind:'shot',team:'N',x:95,y:34,res:'cadre',half:1,t:66000},               // déséquilibre
 {kind:'shot',team:'N',x:95,y:34,res:'hors',half:1,t:200000},               // autre
 {kind:'perte',team:'N',x:30,y:34,half:1,t:300000},
 {kind:'shot',team:'E',x:10,y:34,res:'hors',half:1,t:310000},               // Eux après NOTRE perte = transition
 {kind:'pass',team:'N',x:20,y:20,x2:60,y2:34,ok:false,half:1,t:400000},      // ratée -> perte N + récup E (dérivées)
 {kind:'shot',team:'E',x:20,y:34,res:'but',half:1,t:405000}];               // transition
let so=S.shotOrigins(o,'N',0), se=S.shotOrigins(o,'E',0);
assert.deepStrictEqual(so,{n:3,transition:1,deseq:1,cpa:0,autre:1}); assert.deepStrictEqual(se,{n:2,transition:2,deseq:0,cpa:0,autre:0});
// --- sans chrono (t=0) : fenêtre = 3 événements précédents
const z=[{kind:'recup',team:'N',x:60,y:34,half:1,t:0},{kind:'pass',team:'N',x:1,y:1,x2:2,y2:2,ok:true,half:1,t:0},
 {kind:'pass',team:'N',x:1,y:1,x2:2,y2:2,ok:true,half:1,t:0},{kind:'shot',team:'N',x:95,y:34,half:1,t:0},   // recup à 3 positions -> transition
 {kind:'pass',team:'N',x:1,y:1,x2:2,y2:2,ok:true,half:1,t:0},{kind:'pass',team:'N',x:1,y:1,x2:2,y2:2,ok:true,half:1,t:0},
 {kind:'pass',team:'N',x:1,y:1,x2:2,y2:2,ok:true,half:1,t:0},{kind:'shot',team:'N',x:95,y:34,half:1,t:0}];  // trop loin -> autre
assert.deepStrictEqual(S.shotOrigins(z,'N',0),{n:2,transition:1,deseq:0,autre:1});
// --- timeline
const tl=S.timeline(o,'shots',0); assert.strictEqual(tl.hasClock,true);
assert.strictEqual(tl.buckets[0].N,3); assert.strictEqual(tl.buckets[0].E,2);        // 18 s, 66 s, 200 s -> tranche 0-15 ; Eux 310 s et 405 s aussi
assert.strictEqual(S.timeline(z,'shots',0).hasClock,false);
console.log('timeline b0', JSON.stringify(tl.buckets[0]));
// --- summary + kpis + bilan
const sm=S.summary(o,'N',0); assert.strictEqual(sm.shots.n,3); assert.strictEqual(sm.shots.surface,3); assert.strictEqual(sm.shots.eff,0);
const k=S.kpis(o); assert.strictEqual(k.shotsN,3); assert.strictEqual(k.butsE,1);
const bi=S.bilan(o.concat(ev),0);
assert(!bi.duel.some(d=>/Solde de ballons/.test(d.text)),'solde de ballons retiré');
console.log(bi.nous.map(i=>i.text).join('\n')); console.log(bi.duel.map(i=>i.text).join('\n'));
console.log('OK');
