# Analyse automatique des vidéos Veo

Ce programme lit le **radar 2D de Veo** (la mini-carte en haut à droite du lecteur Veo Analytics) dans une
vidéo enregistrée depuis l'écran. Veo a déjà calculé la position des joueurs : on la récupère, puis on en tire :

- le **bloc des deux équipes** : hauteur, ligne défensive, largeur, longueur, surface occupée ;
- la **possession** et les **zones du ballon** (notre tiers, milieu, tiers adverse) ;
- des **actions** (récupérations, passes) importables dans l'appli de codage, avec leur seconde dans la vidéo.

Pas besoin de carte graphique : un PC normal suffit (environ 5 s pour 30 s de vidéo).

## Installation (une seule fois, Windows)

1. Installer Python 3 depuis python.org (cocher « Add Python to PATH »).
2. Dans le dossier `ia`, ouvrir un terminal et taper :
   `pip install opencv-python numpy matplotlib`

## Enregistrer la vidéo

1. Ouvrir le match sur app.veo.co, afficher le **radar 2D** (en haut à droite).
2. Lancer l'enregistrement de l'écran : `Windows + Alt + R` (Xbox Game Bar) ou OBS.
3. Lancer la lecture. Garder la fenêtre en plein écran, sans la redimensionner pendant l'enregistrement.

## Lancer l'analyse

    python analyser.py "C:\Users\...\match.mp4" --nous noir

- `--nous noir` : Nous = les **ronds noirs** du radar ; `--nous rouge` : les triangles rouges.
  (Ce sont les marques de Veo, pas la couleur des maillots. Regarder le radar pour savoir lesquelles sont Nous.)
- `--sens droite` ou `--sens gauche` : sens d'attaque de Nous sur le radar, si le sens automatique se trompe.
- `--k1 12.5` : seconde de la vidéo où le chrono de l'appli vaut 00:00 (pour que les actions tombent au bon moment).
- `--mi-temps 2` : si la vidéo est la 2e mi-temps.

Résultats dans le dossier `resultats_<nom de la vidéo>` :

| Fichier | Contenu |
|---|---|
| `rapport.png` | image de synthèse (présence des joueurs, trajet du ballon, possession, chiffres) |
| `resume.json` | les chiffres |
| `match_ia.json` | à importer dans l'appli : Codage > Données et sauvegardes > Importer une sauvegarde |
| `positions.json` | positions image par image (pour aller plus loin) |

## Limites connues

- Les positions sont celles de Veo : quelques marques manquent ou se superposent quand les joueurs sont proches.
- Le gardien est affiché dans la couleur de son maillot : il peut apparaître dans la couleur de l'autre équipe
  (le programme le corrige quand il est seul dans sa surface).
- La croix jaune est prise pour le ballon. Les passes et récupérations sont déduites de « qui est le plus proche
  du ballon » : c'est un pré-codage à vérifier dans l'onglet Vidéo de l'appli, pas une vérité.
- Le radar n'existe que sur les matchs traités par Veo Analytics (pas en direct).

## Tests

    python test_ia.py
