# IA vidéo — où on en est (passage de claude.ai à Claude Code, 10 nov. 2026)

## Fait
- Lecture du radar 2D Veo sur un enregistrement d'écran (`radar.py`) : positions des marques + ballon, sans carte graphique.
- Détection des actions du codage manuel (`jeu.py`) : passes réussies / ratées (à partir des déplacements du ballon), passes et conduites de déséquilibre (adversaires éliminés), duels Z / E, frappes. Réglages : `CFG`.
- `analyser.py` (+ `analyser.bat`) : vidéo ou `radar_brut.json` → `match_ia.json` importable dans l'appli, `rapport.png`, `resume.json`.
- `comparer.py` (+ `.bat`) : IA vs codage manuel du même match. `noter.py` : note sur le jeu de référence + historique.
- Onglet Vidéo dans l'appli (en ligne) : calage du codage sur la vidéo, export « actions + vidéo ».

## Nouveau radar Veo (10 nov. 2026, branche ia/radar-jaune-noir)
- Veo a changé son radar : panneau transparent, ronds JAUNES numérotés / triangles NOIRS numérotés, croix ORANGE = ballon, panneau déplaçable et redimensionnable. `radar.py` le lit (`find_radar2` / `read_frame2`, clés `jaune` / `noir`), l'ancien reste géré. Radar trop petit (< 300 px de large) = illisible : l'agrandir dans Veo avant d'enregistrer.
- `jeu.py` : l'adversaire = l'autre couleur présente (`other`). `--nous jaune` dans analyser.py / ref.json.
- Nous = JAUNES (maillots jaunes), U14.

## Jeu de référence (ia/references/, hors dépôt)
- `off_placee` (32 s de jeu, Nous jaune, attaque vers la gauche du radar) : codage = match 1 de « Codage OFF TEST.json » (chrono lancé au début de test.mp4), recalé sur l'enregistrement radar (test.mp4 commence à 13,84 s, trouvé par comparaison d'images).
- Notes : avant (ancien radar.py) = 0, radar introuvable → après = **44 / 100** (passes réussies 77, déséquilibres 100, passes ratées 0, frappe 0 : la frappe codée tombe à la fin de l'enregistrement).
- Remarque : dans ce codage, les coordonnées semblent en vue caméra (frappe à x = 3) : « ⇄ Sens » pas utilisé. Sans effet sur la note (appariement par temps et type).

## Feuille de route vers une IA autonome : voir `PISTES.md` (17 nov. 2026)

## Journal de bord (17 nov., travail en autonomie) : hypothèse → mesure → décision
Banc : `py banc.py` (references/banc.json : off_placee = test.mp4 avec radar + codage ; cascol_10 / _30 / _100 =
2 min du match complet vs Cascol à la 10e, 30e et 100e minute, sans vérité). Historique : references/banc_historique.csv.
- Carte graphique : torch 2.11 + cu128 installé depuis les fichiers téléchargés. YOLO yolo11s / 2880 : 0,55 → 5,9 images/s
  (FP16). Décor (ORB 3000 points, pleine image) : 14 images/s mesuré sur 52 images de off_placee (le « 1,1 image/s » de
  vitesse.py sur 15 images était FAUX, sans doute le démarrage d'OpenCV) → ce n'est pas le goulot. Image réduite de moitié :
  41 images/s mais 2 images sur 52 non reliées et 0,56 m au lieu de 0,50 → pleine image gardée.
- Mesures sans vérité (`autocontrole.py`) : lignes blanches seules (lignes bleues du foot à 8 écartées, pelouse = grande zone
  verte reliée au bas de l'image). Vérifié : un calage décalé fait baisser la mesure ; MAIS lignes parallèles → faux maximums
  (décaler de 4 m peut redonner presque la même note). Bon pour noter un calage, pas suffisant seul pour le chercher.
- Point de départ (calage radar) : off_placee lignes 0,32, joueurs 0,51 m, équipes justes 98 %, note 26 ; Cascol lignes
  0,19 / 0,31 / 0,10, ballon vu 60 / 78 / 49 %. Lignes basses = le calage radar est faux loin des joueurs (vu sur les images).
- 50e minute du match = mi-temps (joueurs regroupés) → séquence remplacée par la 30e minute.
- Liens du décor faux mais acceptés (lignes dessinées n'importe où sur une image) → contrôle de vraisemblance
  (`sans_radar.plausible` : quadrilatère convexe, zoom entre 1/4 et 4) + 30 points d'accord au lieu de 15. Mesures inchangées
  ailleurs (pas de perte).
- Équipes par regroupement des maillots (`equipes.py`, sans couleur écrite en dur) : 1re règle (« les 2 plus gros groupes »)
  86 % justes, note 20 → mauvaise (le plus gros groupe mélangeait spectateurs / gens hors terrain). 2e règle (« Nous » = groupe
  le plus proche de la couleur annoncée, adversaire = plus gros des autres, 4 groupes) : 97,7 % justes = couleurs fixes
  (97,6 %) MAIS moins de jaunes trouvés (médiane 5 au lieu de 8 : soleil et ombre dans 2 groupes), note 21 au lieu de 26.
  Fusionner les groupes proches ajoute des joueurs mais fait des erreurs (94-96 %). DÉCISION : couleurs fixes par défaut pour
  le club, regroupement en option (`banc.py --equipes auto`) pour des maillots inconnus. À reprendre : fusion ombre / soleil
  par la teinte seule.
- Ballon, modèle plus gros (yolo11m) : vu 81 → 76 %, sauts 6 → 10 %, erreur 1,37 → 1,23 m, note 26 → 25 → pas mieux,
  yolo11s gardé. Ré-entraîner YOLO avec le radar comme professeur : pas fait, 165 images d'UNE séquence = apprentissage
  par cœur et pas de mesure honnête. Il faut d'abord d'autres enregistrements radar (autres matchs).
- CALAGE AUTOMATIQUE (`calage_auto.py` : caméra physique + dimensions, recherche par entropie croisée sur 16 vues, puis
  affinage ICP sur 174 vues, ~13 min) : ÉCHEC pour l'instant, NE PAS UTILISER.
  * Essai 1 : mesure « lignes » 0,87 (!) mais terrain entier tassé dans la bande du fond (clôture, buts) : erreur 2,0 m,
    équipes 13 %, note 0. LEÇON : la mesure des lignes seule se laisse tromper → garde-fou ajouté au banc et au calage :
    « dans_terrain » = part des pieds de joueurs qui tombent dans le terrain (calage radar 0,61-0,97 ; faux calage 0,37).
  * Essai 2 (garde-fou + caméra réaliste : mât 4-15 m, recul ≤ 15 m) : pieds dans le terrain 0,92-0,99, lignes 0,45, mais
    lignes dessinées visiblement fausses, erreur 2,1 m, équipes 52 % (hasard), hauteur collée à la borne (4 m) → le modèle
    ne trouve pas. Causes probables : départ au hasard dans un espace trop grand, masque des lignes bruité au fond (clôture,
    buts), terrain symétrique. Pistes : partir de la structure (points de fuite des lignes, ou modèle de points-clés
    pré-entraîné), ou d'un calage approché (clics).
  * DÉCISION : pour le terrain du club, calage par clics (`caler.py`, ~10 repères, simulé à 0,6 m) = le chemin sûr ;
    le calage sans aide reste une piste de recherche.
- Note des actions depuis un codage SANS radar (banc : clé "codage" d'une séquence) : vérifié sur off_placee, même note (26)
  qu'avec le radar. Prêt pour le codage du match Cascol par le coach.

## Journal de bord (19 nov.) : suivi d'un match entier (demande du coach : « suivi radar du ballon et des joueurs, quadrille le terrain »)
- Match Cascol (Desktop, 2 h 03) : Nous = jaune, Eux = noir. 1re mi-temps = 6:55 → 49:10 de la vidéo (coup d'envoi et fin
  repérés sur des planches d'images). Stats Veo de la 1re période (capture du coach) dans `references/cascol/veo_mt1.json` :
  possession 54 / 46, passes 233 (172 réussies) / 191 (125), tentatives 5 / 4. Elles servent de CONTRÔLE, pas de cible de réglage.
- BLOQUANT trouvé : le calage du club (fait sur test.mp4) est faux sur Cascol (touche dans les arbres). Une seule image de
  référence au centre : 62 % des images s'y relient. Avec 4 ancres (côtés, buts) : 100 %.
- Calage unique sur 16 repères lus à la main (zoom) : 1,2 m d'erreur moyenne, ligne médiane décalée. CAUSE MESURÉE : la même
  image de but reliée à la référence par 2 chemins → 10 à 110 px d'écart (l'homographie extrapole loin hors de l'image de
  référence). L'affinage automatique sur les lignes blanches (ICP) dérive de 1 à 6 m (terrains voisins visibles au fond) → écarté.
- SOLUTION : calage PAR VUE (`caler_vues.py`) : 4 vues (centre, demi-terrain gauche, but gauche, but droit) + 1 vue reliée,
  chacune calée sur ses propres repères, dimensions communes trouvées en même temps : **98,0 x 60,4 m**, écart médian
  0,12 m (62 observations). Contrôle : retirer une vue ne bouge pas la largeur (60,7) ; la LONGUEUR ne tient qu'à la vue de la
  27e minute (seule à montrer surface + rond) → à confirmer par le coach. Lignes dessinées justes sur 8 vues sur 9 ; à 48:00,
  ligne médiane décalée de quelques mètres près de la caméra (limite connue).
  Chaque image se relie à la vue qui lui ressemble le plus (`suivi.relier`) : 125 / 125 images testées.
- `suivi.py` : détection de toute la mi-temps (reprise possible), PISTES des joueurs en mètres (équipe = majorité de la piste),
  chemin du ballon, stats (possession au temps, actions jeu.py, quadrillage 3 tiers x 3 couloirs, cartes de chaleur, rapport HTML).
  Mesure off_placee (banc `--suivi`) : erreur joueurs 0,51 → 0,52 m, équipes 0,98 = 0,98, jaunes vus 8 → 9, note 26 → 52.
  ATTENTION : +26 points = 2 actions de plus sur 10 (1 passe, 1 déséquilibre) → dans le bruit ; réglages des pistes testés :
  note 46 à 52 partout → le suivi ne dégrade rien, gain réel à confirmer sur une référence longue.
- Vitesse : relier chaque image aux 5 vues coûtait 0,5 s / image → la vue de l'image précédente est essayée d'abord : 0,15 s.
- BUG trouvé en regardant une image (8:00) : YOLO voyait les joueurs mais le filtre « pieds sur le gazon » écartait tous ceux
  AU SOLEIL (gazon de Cascol au soleil : saturation 127-176 > 125, teinte 37-42 < 40) → 2 joueurs par équipe et par image,
  possession 16 / 84 sur 2 min (absurde). GRASS élargi (h ≥ 34, s ≤ 200). Banc, MÊME terrain avant / après :
  off_placee identique (note 26, 0,51 m, équipes 0,98 → 0,97) ; Cascol : jaunes vus 5 → 8, noirs 3 → 5 (10e min), lignes
  0,49 → 0,65 ; BAISSE « dans_terrain » 0,97 → 0,82 (spectateurs au soleil maintenant gardés, écartés ensuite par la marge
  du suivi) → gardé. Le banc ne refaisait pas son cache quand une COULEUR changeait : corrigé (réglages dans la version).
- 1re mi-temps Cascol analysée (12 663 images, 5 / s, 3 morceaux en parallèle ≈ 3,7 images / s) : but de Cascol à 13:21
  RETROUVÉ (ballon le long de la touche droite, centré devant le but de droite à 800,4 s) ; ballon vu 96 %, joueurs vus
  par image 10 jaunes / 8 noirs. Possession IA 60 % (Veo 54). PASSES TROP NOMBREUSES : réussies 382 / 221 (Veo 172 / 125),
  ratées 199 / 196 (Veo 61 / 66), frappes Nous 21 (Veo 5).
- Sans codage, vérité « à l'œil » (`verifier.py` : planches de 8 images recadrées autour d'actions tirées au hasard) :
  jugement possible mais lent et souvent ambigu ; constat net : le ballon de l'IA saute sur de faux ballons / des endroits
  vides (drapeau de l'arbitre assistant pris pour le ballon).
- Ballon lissé (Savitzky-Golay 5) : réussies Nous 382 → 290, ratées 199 → 156 → utile mais insuffisant.
- `passes.py` (essai, NON branché) : possession JOUEUR par joueur (Vidal-Codina et al. 2022, arXiv 2202.00804) sur les
  pistes. off_placee : passes réussies trouvées 6/7 (jeu.py, 11 proposées) → 4/7 (5 proposées) ; ratées 9 proposées pour 1
  dans les deux cas ; Cascol : ratées toujours ~2 x trop. CONCLUSION : le défaut vient des ENTRÉES (faux ballons, équipes),
  pas des règles → prochain levier = meilleur détecteur de ballon (modèles football de roboflow/sports, à télécharger avec
  l'accord du coach), pas de réglage de jeu.CFG.
- Banc : séquences Cascol sur `terrain_cascol` (calage par vue). Lignes 0,19 / 0,31 / 0,10 → 0,49 / 0,64 / 0,46 (calage du club → par vue).

## Prochaines étapes (dans l'ordre)
1. Le coach valide la branche ia/radar-jaune-noir (puis fusion + push ; les tests `tests/` demandent Node, pas encore installé sur ce PC).
2. Référence plus longue : 5 à 10 min (≥ 50 actions) enregistrées avec le radar AGRANDI + codées → réglage de `CFG` en suivant la note (avant / après, voir CLAUDE.md).
3. Le live SANS radar (demande du coach, 10 nov. ; branche ia/live-sans-radar) : en live il n'y a que la caméra Veo, qui suit le jeu (PAS de vue panoramique d'après le coach) → détecter joueurs et ballon dans l'image, recaler le terrain image par image, sortir le format radar_brut → jeu.py inchangé. Le radar sert de vérité (test.mp4 = enregistrement radar − 13,84 s).
   - Fait : `sans_radar.py` étape 1 = détection. Couleurs seules : trop de faux (maillots « noirs » = bleu marine, proche du synthétique). YOLO (yolo11s, processeur, ~1,8 s / image) : quasiment tous les joueurs à l'image trouvés, jaunes / bleu marine bien séparés, ballon souvent trouvé. Reste : arbitre (maillot pâle) parfois pris pour un noir, spectateurs derrière la clôture.
   - Fait : étape 2 = image → mètres. Calage d'UNE image (ici avec le radar, RANSAC ancré sur le ballon : 11 joueurs à < 2 m, 0,33 m), puis suivi de la caméra par le décor (homographie image → image, ORB). Sur les 32 s : erreur médiane joueurs 1,24 m (0,7-1 m près du calage, 2-3 m aux bouts : dérive), ballon vu 90 %, erreur médiane 1,8 m.
   - Fait : étape 3 (première mesure) : positions « vision » au format radar_brut + noter.py → **20 / 100** (radar : 44). Passes réussies 48, ratées 12, déséquilibres 0. Cause : trop de passes inventées (18 pour 7) à cause des faux ballons (sauts de 27-50 m) et des spectateurs au bord de la touche.
   - Fait : (a) nettoyage `clean_brut` (faux ballons rejetés, spectateurs hors terrain, 11 par équipe max ; lissage testé et abandonné). Passes réussies 48 → 57 (7 trouvées pour 7, 4 au bon moment), passes ratées inventées 16 → 4 ; note globale 20 → 19 (la version brute tombait par hasard sur l'unique passe ratée). Reste : le ballon est donné à Eux vers 34-35 s et 42-43 s alors que Nous l'a (porteur jaune caché ou mal placé). Sur 10 actions, la note bouge trop : il faut la séquence longue.
   - Fait : positions plus justes (mesure sur des milliers de points, plus fiable que la note sur 10 actions). Chaque image reliée DIRECTEMENT à l'image de référence par le décor (100 % des images) + calage commun sur toutes les images (`calibrate_joint`) : erreur médiane joueurs 1,22 → **0,70 m** (validation croisée 0,74 / 0,83 m). Note sur les 10 actions : 16 (bruit : ± 10 points par hasard). Pour le live : garder l'image de référence + son calage pour le terrain du club (Veo à la même place) → plus besoin du radar.
   - Fait : le vrai ballon parmi les faux (`ball_path`, chemin le plus cohérent sur la séquence ; YOLO voit 2 « ballons » ou plus sur 116 images sur 161). Faux ballons à plus de 10 m 20 % → 13 %, vu 83 %. Note vision : 16 → **28 / 100** (passes réussies 59, passes ratées 25, déséquilibres 0). Le radar fait 44.
   - En attente : vitesse. Processeur ≈ 1,8 s / image (yolo11s, imgsz 2880) ; le live demande ≥ 5 images / s → carte graphique (RTX 4050 6 Go, pilote CUDA 13.1). Installer torch CUDA (`py -m pip install --upgrade --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu128`, ~2,5 Go) quand le coach aura une bonne connexion ; script de mesure prêt (images / s par modèle et résolution).
   - Fait (17 nov.) : `mesure_vision.py` = mesure reproductible (YOLO + décor mis en cache dans `references/off_placee/vision_cache.json`, hors dépôt ; ensuite quelques secondes par essai). Image de référence = celle du milieu (t = 29,83 s radar). Calage commun : erreur médiane joueurs **0,51 m** (validation croisée 0,51 / 0,59 m), ballon vu 79 %, erreur 1,4 m, > 10 m 16 % ; note vision **25 / 100** (28 le 10 nov. : même niveau, ± 10 points de bruit sur 10 actions). Calage sur une seule image : 1,47 m, note 19.
   - (b) Dérive : par tranches de 4 s, 0,58 → 0,37 (près de la référence) → 0,79 m à la fin. Faible sur 32 s (chaque image reliée directement à la référence, pas d'accumulation) → rien de mesurable à corriger sur cette séquence. À revoir sur une séquence longue (référence de 5-10 min).
   - (c) Calage par clics du coach, SIMULÉ (`--clics`) : sur une seule image on ne voit que 5 repères dont 4 sur la ligne médiane (alignés → calage impossible). En cliquant chaque repère sur l'image où il est visible (la caméra balaie le terrain), 12 repères sur 32 s, ramenés à l'image de référence par le décor : clics à 3 px près → 0,5-0,7 m, 5 px → 0,6-1,0 m, 8 px → 0,7-1,4 m, 15 px → 0,9-2,3 m. Donc des clics précis (zoom) sur 10-12 repères valent le calage par radar. Attention : les repères supposent les marquages d'un terrain 105 x 68 (repère du radar) ; il faut les VRAIES dimensions du terrain du club (U14) et de ses surfaces.
   - Vitesse : `vitesse.py` prêt (images / s par modèle, taille, processeur / carte FP32 / FP16). Torch CUDA pas encore installé (téléchargement coupé par la connexion).
   - Fait (17 nov.) : outil de clics `caler.py` (+ `caler.bat`, glisser une vidéo de la caméra) : 23 repères proposés un par un (centre, ligne médiane, rond, coins des surfaces, points de penalty, surfaces de but, corners), clic → loupe ×5 → clic précis, sur n'importe quelle image ; lignes du terrain calculées superposées (touche L) pour vérifier ; enregistré dans `ia/terrains/<nom>/` (terrain.json + reference.jpg, hors dépôt). Dimensions réelles du terrain demandées. `mesure_vision.py --terrain terrain.json` mesure ce calage contre le radar.
   - Essai simulé (clics à 3 px près, faits par programme dans la fenêtre avec la loupe, 14 repères visibles sur 32 s) : joueurs 0,61 m, note 27 (calage radar : 0,51 m, 25).
   - ATTENTION, vu sur l'image : les lignes d'un terrain 105 x 68 calculées avec le calage RADAR ne tombent pas sur les vraies lignes (ligne médiane décalée, touche loin dans les arbres). Le calage radar est ajusté sur les joueurs, presque tous au milieu-gauche : loin d'eux, il extrapole mal ; et le terrain U14 n'est pas un 105 x 68. Un vrai calage par clics (vraies lignes, vraies dimensions) peut donc être plus juste que le radar, mais l'écart avec le radar ne le montrera pas parfaitement.
   - Prochaine étape : le coach fait le calage sur test.mp4 avec les vraies dimensions du terrain, puis `py mesure_vision.py --video test.mp4 --terrain terrains/<nom>/terrain.json`. Ensuite : brancher le calage enregistré dans la chaîne live (image de référence du club → chaque image). Puis (b) sur une séquence longue.
4. Plus tard (sur demande du coach) : CPA.

## Rappels
- Les références ne vont JAMAIS dans ce dépôt public (`ia/references/` est ignoré par git).
- Le coach valide chaque étape avant qu'on la lance.
