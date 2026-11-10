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
3. Le live SANS radar (demande du coach, 10 nov. ; branche ia/live-sans-radar) : en live il n'y a que la caméra Veo, qui suit le jeu (PAS de vue panoramique d'après le coach) → détecter joueurs et ballon dans l'image, recaler le terrain image par image, sortir le format radar_brut → jeu.py inchangé. Le radar sert de vérité (test.mp4 = enregistrement radar − 13,84 s).
   - Fait : `sans_radar.py` étape 1 = détection. Couleurs seules : trop de faux (maillots « noirs » = bleu marine, proche du synthétique). YOLO (yolo11s, processeur, ~1,8 s / image) : quasiment tous les joueurs à l'image trouvés, jaunes / bleu marine bien séparés, ballon souvent trouvé. Reste : arbitre (maillot pâle) parfois pris pour un noir, spectateurs derrière la clôture.
   - Fait : étape 2 = image → mètres. Calage d'UNE image (ici avec le radar, RANSAC ancré sur le ballon : 11 joueurs à < 2 m, 0,33 m), puis suivi de la caméra par le décor (homographie image → image, ORB). Sur les 32 s : erreur médiane joueurs 1,24 m (0,7-1 m près du calage, 2-3 m aux bouts : dérive), ballon vu 90 %, erreur médiane 1,8 m.
   - Fait : étape 3 (première mesure) : positions « vision » au format radar_brut + noter.py → **20 / 100** (radar : 44). Passes réussies 48, ratées 12, déséquilibres 0. Cause : trop de passes inventées (18 pour 7) à cause des faux ballons (sauts de 27-50 m) et des spectateurs au bord de la touche.
   - Fait : (a) nettoyage `clean_brut` (faux ballons rejetés, spectateurs hors terrain, 11 par équipe max ; lissage testé et abandonné). Passes réussies 48 → 57 (7 trouvées pour 7, 4 au bon moment), passes ratées inventées 16 → 4 ; note globale 20 → 19 (la version brute tombait par hasard sur l'unique passe ratée). Reste : le ballon est donné à Eux vers 34-35 s et 42-43 s alors que Nous l'a (porteur jaune caché ou mal placé). Sur 10 actions, la note bouge trop : il faut la séquence longue.
   - Fait : positions plus justes (mesure sur des milliers de points, plus fiable que la note sur 10 actions). Chaque image reliée DIRECTEMENT à l'image de référence par le décor (100 % des images) + calage commun sur toutes les images (`calibrate_joint`) : erreur médiane joueurs 1,22 → **0,70 m** (validation croisée 0,74 / 0,83 m). Note sur les 10 actions : 16 (bruit : ± 10 points par hasard). Pour le live : garder l'image de référence + son calage pour le terrain du club (Veo à la même place) → plus besoin du radar.
   - À faire, dans l'ordre : (b) corriger la dérive (recaler sur les lignes du terrain de temps en temps) ; (c) calage initial SANS radar pour le live (lignes du terrain, ou 4 clics du coach au coup d'envoi).
4. Plus tard (sur demande du coach) : CPA.

## Rappels
- Les références ne vont JAMAIS dans ce dépôt public (`ia/references/` est ignoré par git).
- Le coach valide chaque étape avant qu'on la lance.
