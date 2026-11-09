# Codage live — consignes pour Claude

Outil de codage de match en direct pour un entraîneur de football (Chambéry Savoie Football). L'utilisateur parle français et veut des réponses courtes. Interface et messages en français.

## Structure (aucune compilation, scripts simples sur l'espace de noms global `FC`)
- `index.html`, `css/style.css`, `js/*.js` : config (touches, seuils), clock, events (matchs + stockage local), backup (points de sauvegarde), pitch, stats (calculs), viz (cartes), chart (courbe), input (clavier), video (onglet Vidéo : calage codage ↔ film, meta.video = {name, k1, k2}), sync (cloud Claude, sans effet hors Claude), ui (écrans), pwa.
- `ia/` : analyse automatique en Python (lecture du radar 2D Veo → blocs, possession, actions au format de l'appli). Hors de l'application installée (exclu de sw.js). Voir `ia/README.md`.
- `manifest.webmanifest`, `sw.js`, `icons/` : application installable hors ligne.

## Règles
- Après TOUTE modification de fichier : `python3 tools/update_sw.py` (sinon l'application installée sert l'ancien code en cache), puis commit + push.
- Vérifier la syntaxe : `node --check js/<fichier>.js`.
- Ne jamais perdre de données de match : toute action destructive doit prendre un point de sauvegarde avant (`FC.backup.snap`).
- Pas de `confirm()` / `alert()` : utiliser les boutons à confirmation en 2 clics.
- Coordonnées en mètres dans un repère où Nous attaque toujours vers la droite (105 x 68).
- Règles de saisie et de calcul : voir README.md et le récap du projet Claude « Application de code pour match de football ».

## Outils et tests (dans ce dépôt)
- `tools/build_app.py` : fabrique l'application (icônes, manifest, sw.js, zip) à partir de `/home/claude/codage-live`.
- `tests/` : voir `tests/README.md`. Tous doivent passer avant un push.
- Une nouvelle conversation part de ce dépôt : le cloner, le copier dans `/home/claude/codage-live`, lancer les tests.
