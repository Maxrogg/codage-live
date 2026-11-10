# Codage live — consignes pour Claude

Outil de codage de match en direct pour un entraîneur de football (Chambéry Savoie Football). L'utilisateur parle français et veut des réponses courtes. Interface et messages en français.

## Structure (aucune compilation, scripts simples sur l'espace de noms global `FC`)
- `index.html`, `css/style.css`, `js/*.js` : config (touches, seuils), clock, events (matchs + stockage local), backup (points de sauvegarde), pitch, stats (calculs), viz (cartes), chart (courbe), input (clavier), video (onglet Vidéo : calage codage ↔ film, meta.video = {name, k1, k2}), sync (cloud Claude, sans effet hors Claude), ui (écrans), pwa.
- `ia/` : analyse automatique en Python (lecture du radar 2D Veo → actions au format de l'appli). Hors de l'application installée (exclu de sw.js). Voir `ia/README.md`.
- `manifest.webmanifest`, `sw.js`, `icons/` : application installable hors ligne.

## Règles
- Après TOUTE modification de fichier : `python3 tools/update_sw.py` (sinon l'application installée sert l'ancien code en cache), puis commit + push.
- Vérifier la syntaxe : `node --check js/<fichier>.js`.
- Ne jamais perdre de données de match : toute action destructive doit prendre un point de sauvegarde avant (`FC.backup.snap`).
- Pas de `confirm()` / `alert()` : utiliser les boutons à confirmation en 2 clics.
- Coordonnées en mètres dans un repère où Nous attaque toujours vers la droite (105 x 68).
- Règles de saisie et de calcul : voir README.md et le récap du projet Claude « Application de code pour match de football ».

## IA vidéo (dossier ia/) — règles
- L'IA ne détecte QUE ce que le coach code à la main : passes réussies / ratées, passes et conduites de déséquilibre, duels gagnés (Z) / perdus (E), frappes (CPA plus tard). Aucune nouvelle donnée (blocs, largeur, possession affichée…) sans demande du coach.
- Toute modification de `ia/jeu.py` ou `ia/radar.py` : mesurer AVANT et APRÈS avec `python3 ia/noter.py` sur le jeu de référence, et donner les deux notes au coach. Une modification qui baisse la note n'est pas gardée sans son accord.
- Jeu de référence = séquences codées par le coach (`radar_brut.json` + `codage.json` + `ref.json`), rangées HORS du dépôt public (dépôt privé de données ou dossier `ia/references/`, ignoré par git). Jamais de vidéo, de capture de match ni de données de joueurs (mineurs) dans ce dépôt public.
- Le radar Veo place les joueurs à quelques mètres près ; le ballon est plus fiable : partir du ballon.
- Tests : `cd ia && python3 test_ia.py` (doit afficher TOUT EST OK) en plus de `tests/`.
- Le coach valide chaque nouvelle étape : proposer, puis attendre son accord.

## Carte du code (Graphify)
- `graphify-out/` : graphe du code (graph.json, GRAPH_REPORT.md, graph.html), hors de l'application installée.
- Début de conversation : `pip install --break-system-packages graphifyy` (deux y : paquet officiel), puis `graphify update .` (sans IA, gratuit) et lire `graphify-out/GRAPH_REPORT.md` avant d'explorer les fichiers. Pour une question de structure : `graphify explain "<nom>"`, `graphify path "<A>" "<B>"`.
- Après une modification du code : `graphify update .` puis commit avec le reste.

## Autres assistants
- `AGENTS.md` = copie de ce fichier pour les autres assistants de code (le coach peut basculer sur un autre modèle via FreeLLMAPI). Garder les deux identiques.

## Outils et tests (dans ce dépôt)
- `tools/build_app.py` : fabrique l'application (icônes, manifest, sw.js, zip) à partir de `/home/claude/codage-live`.
- `tests/` : voir `tests/README.md`. Tous doivent passer avant un push.
- Une nouvelle conversation part de ce dépôt : le cloner, le copier dans `/home/claude/codage-live`, lancer les tests.
