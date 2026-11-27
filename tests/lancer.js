// Lance les tests sur n'importe quel PC (Windows compris) sans modifier les fichiers de test :
// les chemins Linux écrits dans les tests (/home/claude/..., /opt/node22/..., /usr/bin/google-chrome) sont remplacés
// à la volée par ceux de cette machine, puis chaque test tourne dans un dossier temporaire.
// Usage : node tests/lancer.js [nom1 nom2 ...]     (sans nom : tous les tests qui n'ont besoin de rien d'autre)
// Réglages (variables d'environnement, facultatives) :
//   PLAYWRIGHT = dossier du module playwright ou playwright-core   (défaut : ../codage-outils/node_modules/playwright-core)
//   CHROME     = chemin de Chrome ou Edge                           (défaut : Chrome puis Edge installés sous Windows)
const fs = require('fs'), path = require('path'), os = require('os'), { spawnSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const fwd = function (p) { return p.replace(/\\/g, '/'); };
const PW = process.env.PLAYWRIGHT || path.resolve(ROOT, '..', 'codage-outils', 'node_modules', 'playwright-core');
const CHROME = process.env.CHROME || ['C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/google-chrome'].filter(function (p) { return fs.existsSync(p); })[0];
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), 'codage-tests-'));
// Ont besoin d'autre chose (serveur sur 8765, vidéo de test, résultat de l'IA) : lancés seulement si on les nomme.
const SPECIAL = ['pwa', 'video', 'ia_import'];
// Captures d'écran seulement (pas de vérification) : lancées seulement si on les nomme.
const SHOTS = ['shots2', 'shots3', 'shotsR'];

function prepare(name) {
  let s = fs.readFileSync(path.join(__dirname, name + '.js'), 'utf8');
  s = s.split('/opt/node22/lib/node_modules/playwright').join(fwd(PW))
    .split('/usr/bin/google-chrome').join(fwd(CHROME))
    .split('file:///home/claude/codage-live/').join('file:///' + fwd(ROOT).replace(/^\//, '') + '/')
    .split('/home/claude/codage-live/').join(fwd(ROOT) + '/')
    .split('/home/claude/test/').join(fwd(OUT) + '/')
    .split('/home/claude/work/').join(fwd(OUT) + '/')
    .split('/tmp/').join(fwd(OUT) + '/');
  const f = path.join(OUT, name + '.js'); fs.writeFileSync(f, s); return f;
}

const all = fs.readdirSync(__dirname).filter(function (f) { return /\.js$/.test(f) && f !== 'lancer.js'; }).map(function (f) { return f.slice(0, -3); });
// -v : affiche aussi la sortie des tests réussis (beaucoup de tests navigateur affichent des chiffres à relire, sans assert).
const VERBOSE = process.argv.indexOf('-v') >= 0;
const asked = process.argv.slice(2).filter(function (a) { return a !== '-v'; }), list = asked.length ? asked : all.filter(function (n) { return SPECIAL.indexOf(n) < 0 && SHOTS.indexOf(n) < 0; });
if (!CHROME) { console.log('Chrome / Edge introuvable : régler CHROME'); process.exit(2); }
if (!fs.existsSync(PW)) { console.log('Playwright introuvable (' + PW + ') : npm install playwright-core, ou régler PLAYWRIGHT'); process.exit(2); }
let bad = 0;
list.forEach(function (n) {
  const r = spawnSync(process.execPath, [prepare(n)], { cwd: OUT, encoding: 'utf8', timeout: 180000 });
  const out = ((r.stdout || '') + (r.stderr || '')).trim(), ok = r.status === 0 && !/AssertionError|Error:|ÉCHEC|FAIL/.test(out);
  if (!ok) bad++;
  const tail = '\n' + out.split('\n').slice(-15).map(function (l) { return '      ' + l; }).join('\n');
  console.log((ok ? 'OK    ' : 'ÉCHEC ') + n + (!ok || (VERBOSE && out) ? tail : ''));
});
console.log(bad ? bad + ' test(s) en échec' : 'TOUT EST OK (' + list.length + ' tests)');
console.log('Sorties (captures) : ' + OUT);
process.exit(bad ? 1 : 0);
