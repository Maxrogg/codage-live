# Analyse automatique des vidéos Veo

Le programme lit le **radar 2D de Veo** (la mini-carte en haut à droite du lecteur Veo Analytics) sur une vidéo
enregistrée depuis l'écran. Veo y affiche déjà la position des joueurs et du ballon.

Il en tire **les mêmes actions que ton codage à la main** :
- passes réussies et ratées ;
- passes de déséquilibre ;
- conduites de déséquilibre ;
- duels gagnés (Z) et perdus (E) ;
- frappes.

Le fichier produit s'importe dans l'appli : Analyse, Bilan et Vidéo fonctionnent comme pour un match codé.
C'est un **pré-codage à vérifier** dans l'onglet Vidéo, pas une vérité.

Pas besoin de carte graphique : environ 5 s de calcul pour 30 s de vidéo.

## Installation (une seule fois, Windows)

1. Installer Python 3 depuis python.org, en cochant « Add Python to PATH ».
2. Double-cliquer sur `installer.bat`.

## Enregistrer la vidéo

1. Sur app.veo.co, ouvrir le match et afficher le **radar 2D**.
2. Lancer l'enregistrement de l'écran : `Windows + Alt + R` (Xbox Game Bar), ou OBS.
3. Garder la même taille de fenêtre pendant tout l'enregistrement. L'idéal : une mi-temps entière.

## Analyser

**Glisser la vidéo sur `analyser.bat`.** Trois questions s'affichent :

1. **Nous = noir ou rouge.** Ce sont les marques du radar (ronds noirs ou triangles rouges), pas la couleur des maillots.
2. **La mi-temps.**
3. **Le sens d'attaque**, vu depuis la caméra. Une proposition est faite ; appuyer sur Entrée pour l'accepter.

Le dossier `resultats_<nom de la vidéo>` s'ouvre à la fin. Il contient :

| Fichier | Contenu |
|---|---|
| `match_ia.json` | à importer dans l'appli : Codage > Données et sauvegardes > Importer une sauvegarde |
| `rapport.png` | les actions détectées sur le terrain + les comptes |
| `resume.json` | les comptes |
| `positions.json` | positions image par image (vérifications) |

Pour que les actions tombent au bon moment du chrono : `--k1 <seconde de la vidéo où le chrono vaut 00:00>`.

## Comparer l'IA à ton codage

1. Coder le match en live comme d'habitude.
2. Dans l'onglet Vidéo de l'appli : ouvrir la même vidéo, caler les mi-temps, puis « Exporter actions + vidéo (JSON) ».
3. Sélectionner ce fichier et `match_ia.json`, puis les glisser ensemble sur `comparer.bat`.

Pour chaque type d'action, le résultat donne :
- combien tu en as codé ;
- combien l'IA en a trouvé ;
- combien se correspondent (même action à ±4 s).

Le fichier `comparaison.csv` liste chaque action manquée ou en trop, avec sa seconde dans la vidéo, pour aller vérifier.

## Comment l'IA décide

| Action | Règle |
|---|---|
| Point de départ | le ballon du radar est fiable, les joueurs à quelques mètres près : on suit le ballon |
| Passe | le ballon part vite (8,5 m/s et plus) sur au moins 4 m dans une même direction ; même équipe avant et après = réussie |
| Conduite | le ballon avance d’au moins 10 m au pied de la même équipe, sans passe |
| Déséquilibre | adversaires éliminés : entre le ballon et leur but avant, derrière après. Passe : 3 ou plus. Conduite : 2 ou plus. |
| Passe ratée | après la passe, c’est l’adversaire qui a le ballon, ou le ballon sort du terrain |
| Duel | ballon disputé (les deux équipes au contact), puis une équipe repart avec |
| Frappe | ballon qui part vite vers le but adverse, à moins de 35 m |

Les frappes sont toujours notées « non cadrées » : le radar ne montre pas le cadre, il faut corriger.

Tous les réglages sont en tête de la section « détection des actions » de `jeu.py` (`CFG`).

## Limites connues

- Les positions sont celles de Veo : des marques manquent ou se superposent quand les joueurs sont proches.
- Le gardien est affiché dans la couleur de son maillot, souvent celle de l'autre équipe. Le programme le corrige
  quand il est seul dans sa surface.
- Le sens d'attaque proposé est fiable sur une mi-temps, moins sur un court extrait : il faut le vérifier.
- Les coups de pied arrêtés ne sont pas encore détectés.
- Le radar n'existe que sur les matchs traités par Veo Analytics, donc pas en direct.

## Tests

    python test_ia.py
