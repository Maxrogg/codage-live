# Tests (pour Claude)

## Sous Windows (ou tout PC) : `node tests/lancer.js`
Lance les tests sans toucher aux fichiers : les chemins Linux sont remplacés à la volée. Il faut une fois
`npm install playwright-core` dans `../codage-outils` (à côté du dépôt) ; Chrome ou Edge installé est utilisé.
- `node tests/lancer.js` : tous les tests courants · `node tests/lancer.js -v keys zero` : ceux-là, avec leur sortie à relire
  (beaucoup de tests navigateur affichent des chiffres sans vérifier eux-mêmes : « OK » = pas d'erreur).
- `video` : `VID=<chemin>/test.mp4 node tests/lancer.js video` (vidéo à fabriquer avec la commande ffmpeg en tête de `video.js`).
- `saisie2.js` : Rétablir, mi-temps (côté, retour en 1re, 40 / 45 min, tranches), ⇄ / ✕, notes (N), onglet Vidéo.

Scripts Node / Playwright. Ils lisent l'application dans `/home/claude/codage-live` : copier d'abord le dépôt à cet endroit
(`cp -r . /home/claude/codage-live`) ou changer le chemin en tête de fichier.

- `t3.js` stats · `mom.js` momentum (sans navigateur, `node tests/mom.js`)
- `ana.js` analyse · `keys.js` saisie clavier · `zero.js` remise à zéro · `bk.js` points de sauvegarde · `ui5.js` matchs · `sync.js` cloud simulé
- `cpa.js` xG et CPA (sans navigateur) · `cpa2.js` touche F + Espace et carte CPA
- `reload.js` rechargement en plein match (chrono), anciens types d'événement, date locale
- `pwa.js` hors ligne : servir le dépôt sur le port 8765 (`python3 -m http.server 8765`) avant
- `video.js` onglet Vidéo (calage, saut aux actions, export, CSV) : vidéo de test à fabriquer avec ffmpeg (commande en tête du fichier)
- `ia_import.js` import dans l'appli du fichier produit par `ia/analyser.py`
- `../ia/test_ia.py` analyse automatique (Python, sans navigateur) : `cd ia && python3 test_ia.py`
- `shots*.js` captures d'écran clair / sombre · `perf.js` 900 événements

Playwright : `/opt/node22/lib/node_modules/playwright`, Chrome : `/usr/bin/google-chrome` (adapter si besoin).
