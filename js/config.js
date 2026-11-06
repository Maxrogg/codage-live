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
    but: 'c',
    cpa: 'f',                              // tenue + Espace = coup de pied arrêté à cet endroit (type déduit de la position)                              // appuyer juste après une frappe = c'est un but
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
    shot:        { label: 'Frappe',                   two: false },
    cpa:         { label: 'CPA',                      two: false }
  },
  deseqKinds: ['pass_deseq', 'carry_deseq'],
  shotResults: { cadre: 'Cadrée', hors: 'Non cadrée', but: 'But' },
  halfStartMs: 45 * 60000,                 // chrono au début de la 2e mi-temps
  zones: { cols: 4, lanes: 5, laneLabels: ['ext. gauche', 'int. gauche', 'axe', 'int. droit', 'ext. droit'] },
  heat: { cell: 2, sigma: 5, minRef: 2.5, shrink: 5, volPow: 0.7, volMin: 0.08 },
  originMs: 15000,                         // fenêtre « origine d'une frappe » (avec chrono)
  originEvents: 3,                         // sans chrono : nb d'événements précédents regardés
  timeBuckets: ['0–15', '15–30', '30–45', '45–60', '60–75', '75–90', '90+'],
  // Momentum = pression offensive de Nous moins celle d'Eux, sur une fenêtre glissante (minutes).
  // Chaque action vaut des points ; une entrée dans la surface remplace l'entrée dans le dernier tiers (pas de double compte).
  momentum: { win: 5, neutral: 1, entSurf: 3, entTiers: 1, shot: 2, shotOn: 1, goal: 2, deseq: 3, recupHaute: 1.5,
    // Multiplicateurs de lieu. Frappe : par quart du terrain (0 = son camp ... 3 = dernier quart), cadrée ou non. But : bonus fixe.
    shotCol: [1, 1, 1, 1.5],
    // Déséquilibre réussi : par couloir d'ARRIVÉE (ext. gauche, int. gauche, axe, int. droit, ext. droit). L'axe vaut plus que la largeur.
    deseqLane: [1, 1.25, 1.5, 1.25, 1] },
  // CPA : une frappe de la même équipe dans les 15 s (sans chrono : 4 événements) = CPA « suivi d'une frappe ».
  cpaMs: 15000, cpaEvents: 4,
  cpaTypes: { corner: 'Corner', cf: 'Coup franc', touche: 'Touche' },
  // xG (qualité d'une frappe, 0 à 1) : modèle simple selon la distance et l'angle de tir vers le but. Estimation, pas une vérité.
  // logit = b0 + angle(rad) x a + distance(m) x d. Repères : penalty ~0,22 · 6 m axe ~0,5 · 18 m axe ~0,08 · 25 m ~0,03.
  xg: { b0: -1.1, a: 1.6, d: -0.11 },
  recentShown: 16                          // nb d'événements gardés visibles en direct
};
