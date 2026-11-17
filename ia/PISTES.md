# IA vidéo autonome : pistes et feuille de route (17 nov. 2026)

But du coach : une IA qui **se débrouille seule** sur une vidéo Veo (on peut lui donner les dimensions du terrain, sans que ce soit obligatoire), testée **automatiquement et régulièrement**.
Voir aussi `ETAT.md` pour ce qui est fait.

## Ce qu'on a, et ce qui casse sur un autre match

Ce qui marche aujourd'hui (`sans_radar.py`, `jeu.py`) :
- YOLO détecte joueurs et ballon ;
- le décor (ORB) relie chaque image à une image de référence (100 % des images sur test.mp4) ;
- le terrain est calé par le radar ou par clics ;
- les actions sont tirées des positions par des règles.

Ce qui est écrit « en dur » et cassera ailleurs :
- les couleurs des maillots (`YEL`, `DARK`, `LIME`) et de la pelouse (`GRASS`) ;
- la zone du logo Veo ;
- le terrain 105 x 68 ;
- le calage qui dépend du radar ou du coach.

Vu sur les images :
- le terrain a aussi des **lignes bleues** (foot à 8), qui ne doivent pas être prises pour les vraies ;
- le calage radar met la touche du fond dans les arbres : le radar n'est pas une vérité parfaite loin des joueurs.

## Données disponibles (Bureau du coach, jamais dans le dépôt)

| Fichier | Contenu |
|---|---|
| `vs-cascol-2026-11-08.mp4` | Match complet, caméra Veo, 2 h 03, 1920 x 1080, 30 images/s. Même stade que test.mp4. **Pas encore de codage** (le coach peut le faire) |
| `Veo _ VS CASCOL - Google Chrome ….mp4` | Enregistrement d'écran du radar Veo (50 Mo, durée à vérifier) |
| `test.mp4` + `references/off_placee` | 32 s, radar + codage (10 actions) |

## Les pistes

Chaque piste donne : ce qu'elle remplace, ce qu'elle coûte, comment on la teste, et les données qu'il lui faut. Elles sont **classées par l'essai le moins cher qui confirme ou abandonne une grosse branche.**

### 1. Des mesures sans vérité (auto-contrôle) : la base de tout
- **Remplace :** rien. Elle s'ajoute à `mesure_vision.py`. Sans elle, on ne peut tester qu'avec le radar ou le codage.
- **Idée :** l'IA se note elle-même sur n'importe quel match, avec quatre mesures.
  - **Recouvrement des lignes :** on dessine le terrain calé sur l'image, et on compte la part des lignes qui tombent sur du blanc (le bleu est exclu).
  - **Part des images reliées** à la référence.
  - **Joueurs par équipe** sur le terrain (11 attendus).
  - **Sauts du ballon.**
- **Coût :** faible, c'est du traitement d'image simple.
- **Test :** sur test.mp4, le recouvrement des lignes doit baisser quand on fausse le calage. Il doit aussi départager le calage radar et un calage par clics.
- **Données :** aucune.

### 2. Calage AUTOMATIQUE du terrain, une fois par stade
- **Remplace :** `calibrate_on_radar` et les clics (`caler.py` devient l'outil de vérification).
- **Idée :** la Veo ne bouge pas.
  1. Par le décor, on assemble une **mosaïque** de tout le terrain à partir du match (la caméra balaie le terrain).
  2. Sur cette mosaïque, on cherche à la fois **le calage et les dimensions** (longueur, largeur, surfaces) qui maximisent le recouvrement des lignes blanches (piste 1).
  3. On fait ça une fois par stade, avec beaucoup d'images, donc c'est robuste.
- **Deux moyens d'accélérer le départ, à essayer d'abord parce que c'est rapide :**
  - les modèles déjà entraînés qui trouvent les **points-clés du terrain**, comme le modèle à 32 points de Roboflow (YOLOv8-pose) ou PnLCalib / NBJW (HRNet, entraînés sur SoccerNet) ;
  - une recherche de lignes classique (masque blanc, Hough).
- **Risque :** ces modèles sont entraînés sur des matchs pros télévisés. Ici on a un synthétique amateur avec des lignes bleues.
- **Coût :** moyen. Les modèles pré-entraînés sont un essai d'une demi-journée. Vérifier les licences avant d'en copier.
- **Test :** comparer à l'œil (lignes dessinées) et avec la mesure 1, à un calage par clics du coach (la seule vraie référence sans radar), et au radar.
- **Données :** test.mp4, puis le match Cascol.

### 3. Les équipes trouvées seules, à chaque match
- **Remplace :** les couleurs écrites en dur.
- **Idée :** on regroupe les maillots du match en groupes (histogrammes de couleur, ou empreintes d'image type SigLIP comme Roboflow, puis KMeans) : 2 équipes, l'arbitre, les gardiens. Le coach dit seulement quelle équipe est « Nous », ou l'IA le devine (même couleur que la semaine d'avant).
- **Coût :** faible à moyen.
- **Test :** part des joueurs bien classés, mesurée contre le radar sur test.mp4.
- **Données :** test.mp4, Cascol.

### 4. Suivre les joueurs dans le temps (ByteTrack)
- **Remplace :** la détection image par image.
- **Idée :** `model.track` d'ultralytics (ByteTrack, déjà inclus) donne un numéro à chaque joueur. Le porteur du ballon devient plus stable, ce qui donne moins de passes inventées.
- **Coût :** faible.
- **Test :** la note de `noter.py` et le nombre de « changements de porteur » parasites.

### 5. Le ballon (le point faible : 16 % de faux à plus de 10 m)
- **Idées :**
  1. Découper l'image en morceaux à haute résolution (tuilage, façon SAHI).
  2. Utiliser plusieurs images à la suite (façon TrackNet).
  3. Surtout, **ré-entraîner YOLO sur nos propres vidéos**. Les étiquettes se font toutes seules : le radar donne la position du ballon, qu'on reporte dans l'image (le ballon du radar est fiable).
- **Coût :** il faut la carte graphique.
- **Test :** ballon vu, erreur, faux ballons (mesure 1 + radar).
- **Données :** les enregistrements radar existants.

### 6. Une vraie référence d'actions : le match Cascol codé par le coach
- **Idée :** le coach code le match Cascol dans l'onglet Vidéo de l'appli (calé sur la vidéo). Ça donne des centaines d'actions de référence au lieu de 10, de quoi voir si une modification aide vraiment.
- **Plus économe :** coder 2 ou 3 morceaux de 10 minutes plutôt que tout le match.
- **Option :** si un codage n'est pas calé sur la vidéo, on trouve le décalage tout seul, en faisant glisser les actions de l'IA sur celles du coach jusqu'à ce qu'elles collent le mieux. Test : sur off_placee, on doit retrouver le 13,84 s.

### 7. Régler `jeu.py` automatiquement
- **Remplace :** les réglages `CFG` faits à la main.
- **Idée :** recherche automatique des réglages qui maximisent la note, en **validation croisée** (réglé sur une moitié, noté sur l'autre) pour ne pas tricher. Plus tard, un petit classifieur appris sur les codages du coach (la littérature : règles 0,83-0,91 de F-score, apprentissage un peu mieux).
- **Données :** au moins 50 actions codées et calées (piste 6).

### 8. Plus tard
- La chaîne complète SoccerNet « Game State Reconstruction » (sn-gamestate).
- La détection d'actions directement dans la vidéo (SoccerNet Ball Action Spotting, FOOTPASS : pass, drive, tir, etc.).
- Raison : c'est lourd, entraîné sur la télé pro, et il faut une grosse carte graphique.

## Le banc de test automatique (`banc.py`, à faire)
- **Une commande** qui passe toutes les séquences de référence et les morceaux du match Cascol.
- **Ce qu'il mesure :**
  - avec la vérité quand elle existe (radar, codage) : positions, ballon, note ;
  - sans vérité, toujours (piste 1) ;
  - la vitesse.
- **Cache par étape** (détections, décor), selon le modèle et la version du code, rangé dans `references/` (hors dépôt, mineurs) : un essai prend quelques secondes.
- **Historique CSV** avec la version git. Une alerte si une mesure baisse ; une modification qui baisse n'est pas gardée sans l'accord du coach.
- **Lancement :** à chaque modification, et une fois par nuit (tâche planifiée) sur un plus gros morceau.
- **Temps de calcul :** le match complet à 5 images/s fait environ 37 000 images, soit environ 18 h sur le processeur. On travaille donc sur des morceaux de 2 minutes, ou à 1 image/s, tant que la carte graphique n'est pas en place.

## Ordre proposé
1. Mesures sans vérité (piste 1) et `banc.py`, sur test.mp4 + 2-3 morceaux de 2 min du match Cascol.
2. Essai des modèles de points-clés déjà entraînés, puis mosaïque et calage automatique avec recherche des dimensions (piste 2).
3. Équipes par regroupement (3) et ByteTrack (4).
4. Codage Cascol par le coach (6), puis réglage automatique de `jeu.py` (7).
5. Ballon ré-entraîné (5), dès que la carte graphique marche.

## Sources
- SoccerNet Game State Reconstruction (minimap depuis une caméra) : https://arxiv.org/abs/2404.11335, code https://github.com/SoccerNet/sn-gamestate
- PnLCalib / NBJW (calage par points et lignes du terrain) : https://arxiv.org/abs/2404.08401, https://github.com/mguti97/PnLCalib
- Roboflow sports (32 points-clés du terrain, équipes SigLIP + UMAP + KMeans, vue radar) : https://github.com/roboflow/sports
- SoccerNet Ball Action Spotting, résultats 2024 / 2025 : https://arxiv.org/abs/2409.10587, https://arxiv.org/abs/2508.19182
- FOOTPASS (actions joueur par joueur) : https://arxiv.org/abs/2511.16183
- Ballon petit et rapide : TrackNet https://arxiv.org/abs/1907.03698, FootAndBall https://www.scitepress.org/Papers/2020/89160/pdf/index.html
- Passes depuis les positions (règles vs apprentissage, limites de la validation) : https://pmc.ncbi.nlm.nih.gov/articles/PMC11025972/
- Caméra fixe amateur (futsal, YOLO + ByteTrack + homographie) : https://ddd.uab.cat/pub/tfg/2025/336952/breaking_the_data_deadlock.pdf
