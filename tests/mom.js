const fs=require('fs'),vm=require('vm'),assert=require('assert');
global.window=global; global.document={}; global.localStorage={};
for(const f of ['config','stats','momentum']) vm.runInThisContext(fs.readFileSync('/home/claude/codage-live/js/'+f+'.js','utf8'));
const M=FC.momentum, MIN=60000;
// poids
assert.strictEqual(M.weightOf({kind:'pass',team:'N',x:60,y:34,x2:92,y2:34,ok:true}),3);          // entrée surface (remplace tiers)
assert.strictEqual(M.weightOf({kind:'pass',team:'N',x:60,y:34,x2:75,y2:34,ok:true}),1);          // entrée dernier tiers
assert.strictEqual(M.weightOf({kind:'pass_deseq',team:'N',x:60,y:34,x2:75,y2:34,ok:true}),5.5);  // + déséquilibre axial (3 x 1,5)
assert.strictEqual(M.weightOf({kind:'pass_deseq',team:'N',x:60,y:5,x2:75,y2:5,ok:true}),4);   // déséquilibre ext. (3 x 1) + tiers
assert.strictEqual(M.weightOf({kind:'pass_deseq',team:'N',x:60,y:20,x2:75,y2:20,ok:true}),4.75);  // int. (3 x 1,25)
assert.strictEqual(M.weightOf({kind:'carry_deseq',team:'E',x:50,y:34,x2:30,y2:34,ok:true}),5.5);  // Eux : axe aussi
assert.strictEqual(M.weightOf({kind:'pass',team:'N',x:60,y:34,x2:92,y2:34,ok:false}),0);         // ratée
assert.strictEqual(M.weightOf({kind:'shot',team:'N',x:95,y:34,res:'hors'}),3);     // dernier quart : 2 x 1,5
assert.strictEqual(M.weightOf({kind:'shot',team:'N',x:95,y:34,res:'cadre'}),4.5); // (2+1) x 1,5
assert.strictEqual(M.weightOf({kind:'shot',team:'N',x:95,y:34,res:'but'}),6.5);  // 4,5 + but 2
assert.strictEqual(M.weightOf({kind:'shot',team:'N',x:60,y:34,res:'hors'}),2);    // ailleurs : pas de bonus
assert.strictEqual(M.weightOf({kind:'shot',team:'N',x:60,y:34,res:'cadre'}),3);
assert.strictEqual(M.weightOf({kind:'shot',team:'E',x:10,y:34,res:'cadre'}),4.5); // Eux : dernier quart = x faible
assert.strictEqual(M.weightOf({kind:'recup',team:'N',x:80,y:34}),1.5);                           // récup haute
assert.strictEqual(M.weightOf({kind:'recup',team:'N',x:20,y:34}),0);                             // récup basse
assert.strictEqual(M.weightOf({kind:'recup',team:'E',x:20,y:34}),1.5);                           // Eux : haute = côté x faible
// sans chrono
assert.strictEqual(M.compute([{kind:'shot',team:'N',x:95,y:34,res:'hors',half:1,t:0}],0).hasClock,false);
// match : N tir à 2'10 ; E tir à 20' ; but N à 50' (2e mi-temps)
const ev=[
 {kind:'shot',team:'N',x:95,y:34,res:'hors',half:1,t:2*MIN+10000},
 {kind:'shot',team:'E',x:10,y:34,res:'hors',half:1,t:20*MIN},
 {kind:'shot',team:'N',x:95,y:34,res:'but',half:2,t:50*MIN}];
let d=M.compute(ev,0,5);
assert.strictEqual(d.segs.length,2); assert.strictEqual(d.segs[0].to,45); assert.strictEqual(d.segs[1].from,45);
const at=(m,h)=>d.points.find(p=>p.min===m&&p.half===h);
assert.strictEqual(at(2,1).v,3); assert.strictEqual(at(6,1).v,3);   // dans la fenêtre 5' jusqu'à la minute 6
assert.strictEqual(at(7,1).v,0);                                     // hors fenêtre
assert.strictEqual(at(20,1).v,-3); assert.strictEqual(at(50,2).v,6.5);
assert.strictEqual(d.goals.length,1); assert.strictEqual(d.goals[0].min,50);
assert(d.segs[1].x0+45>d.segs[0].to);                                // pas de chevauchement des 2 mi-temps
assert.strictEqual(d.peakN.v,6.5); assert.strictEqual(d.peakE.v,-3);
// 1re mi-temps longue (48') : la 2e démarre après
const ev2=ev.concat([{kind:'shot',team:'N',x:95,y:34,res:'hors',half:1,t:48*MIN}]);
d=M.compute(ev2,0,5); assert.strictEqual(d.segs[0].to,48); assert(d.segs[1].x0+45>=d.segs[0].to+3);
// filtre mi-temps
d=M.compute(ev,2,5); assert.strictEqual(d.segs.length,1); assert.strictEqual(d.segs[0].half,2);
assert(/Pic Nous : 50'/.test(M.summary(M.compute(ev,0,5))));
console.log('momentum OK');
