/* CONFIG : tout ce que le coach peut vouloir changer (touches, couleurs, types). */
window.FC = window.FC || {};
FC.CONFIG = {
  pitch: { L: 105, W: 68 },               // mètres
  teams: {
    N: { label: 'Nous' },
    E: { label: 'Eux' }
  },
  keys: {
    eux: 'a',                              // tenue pendant Espace = action de l'adversaire (sinon Nous)
    recup: 'z',                            // 1 appui = récupération de Nous (compte aussi comme perte d'Eux), au curseur
    perte: 'e',                            // 1 appui = perte de Nous (compte aussi comme récupération d'Eux), au curseur
    frappe: 'r',                           // tenue + Espace : 1 appui = non cadrée, 2 appuis = cadrée
    but: 'c',                              // appuyer juste après une frappe = c'est un but
    annuler: 'escape'                      // Échap : annule le geste en cours (Espace = poser le point)
  },
  modifiers: {                             // tenus pendant le clic d'arrivée
    ctrl: 'pass_deseq',
    shift: 'carry_deseq'
  },
  holdMs: 350,                             // Espace maintenu plus longtemps = action de l'adversaire
  dblMs: 320,                              // fenêtre du double-clic (passe ratée / frappe cadrée)
  dblDist: 4,                              // m : 2e clic proche du 1er = double-clic
  minLen: 1.5,                             // m : ignore un clic d'arrivée collé au départ
  kinds: {
    pass:        { label: 'Passe',                    two: true },
    pass_deseq:  { label: 'Passe de déséquilibre',    two: true },
    carry_deseq: { label: 'Conduite de déséquilibre', two: true },
    recup:       { label: 'Récupération',             two: false },
    perte:       { label: 'Perte de balle',           two: false },
    shot:        { label: 'Frappe',                   two: false }
  },
  deseqKinds: ['pass_deseq', 'carry_deseq'],
  shotResults: { cadre: 'Cadrée', hors: 'Non cadrée', but: 'But' },
  halfStartMs: 45 * 60000,                 // chrono au début de la 2e mi-temps
  zones: { cols: 4, lanes: 5, laneLabels: ['ext. gauche', 'int. gauche', 'axe', 'int. droit', 'ext. droit'] },
  heat: { cell: 2, sigma: 5, minRef: 2.5, shrink: 5, volPow: 0.7, volMin: 0.08 },
  originMs: 15000,                         // fenêtre « origine d'une frappe » (avec chrono)
  originEvents: 3,                         // sans chrono : nb d'événements précédents regardés
  timeBuckets: ['0–15', '15–30', '30–45', '45–60', '60–75', '75–90', '90+'],
  recentShown: 16                          // nb d'événements gardés visibles en direct
};
