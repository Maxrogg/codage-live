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

## Prochaines étapes (dans l'ordre)
1. Le coach valide la branche ia/radar-jaune-noir (puis fusion + push ; les tests `tests/` demandent Node, pas encore installé sur ce PC).
2. Référence plus longue : 5 à 10 min (≥ 50 actions) enregistrées avec le radar AGRANDI + codées → réglage de `CFG` en suivant la note (avant / après, voir CLAUDE.md).
3. Le live SANS radar (demande du coach, 10 nov.) : en live il n'y a que la caméra Veo (qui suit le jeu) → détecter joueurs (maillots jaunes / noirs) et ballon dans l'image, recaler le terrain image par image, sortir des positions au format radar_brut → jeu.py inchangé. Le radar sert de vérité pour mesurer cette version.
4. Plus tard (sur demande du coach) : CPA.

## Rappels
- Les références ne vont JAMAIS dans ce dépôt public (`ia/references/` est ignoré par git).
- Le coach valide chaque étape avant qu'on la lance.
