# Tests (pour Claude)

Scripts Node / Playwright. Ils lisent l'application dans `/home/claude/codage-live` : copier d'abord le dépôt à cet endroit
(`cp -r . /home/claude/codage-live`) ou changer le chemin en tête de fichier.

- `t3.js` stats · `mom.js` momentum (sans navigateur, `node tests/mom.js`)
- `ana.js` analyse · `keys.js` saisie clavier · `zero.js` remise à zéro · `bk.js` points de sauvegarde · `ui5.js` matchs · `sync.js` cloud simulé
- `cpa.js` xG et CPA (sans navigateur) · `cpa2.js` touche F + Espace et carte CPA
- `reload.js` rechargement en plein match (chrono), anciens types d'événement, date locale
- `pwa.js` hors ligne : servir le dépôt sur le port 8765 (`python3 -m http.server 8765`) avant
- `shots*.js` captures d'écran clair / sombre · `perf.js` 900 événements

Playwright : `/opt/node22/lib/node_modules/playwright`, Chrome : `/usr/bin/google-chrome` (adapter si besoin).
