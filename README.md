# Codage live — application de match

Outil pour coder un match en direct au banc (pad + barre Espace), puis lire les cartes (déséquilibres, zones sûres / à risque, récups et pertes, où ça passe), le Bilan et la comparaison des matchs.

## Utiliser
- **Hors ligne, sans rien installer** : ouvrir `index.html` dans Chrome ou Edge. Tout marche, les matchs restent dans ce navigateur.
- **Application installable** : une fois le dossier publié sur GitHub Pages (voir plus bas), ouvrir l'adresse dans Chrome ou Edge, cliquer « Installer l'application » (ou l'icône d'installation dans la barre d'adresse). Après la première ouverture, elle marche sans internet.

## Publier sur GitHub Pages
1. Créer un dépôt GitHub (vide) et y mettre ces fichiers à la racine.
2. Dépôt > Settings > Pages > Source : branche `main`, dossier `/ (root)` > Save.
3. L'adresse est `https://<compte>.github.io/<dépôt>/`.

## Données
- Les matchs sont enregistrés dans le navigateur (localStorage) à chaque événement. Chaque adresse a ses propres données : l'application installée et l'ancienne page ne partagent rien.
- Pour passer d'un endroit à l'autre : « Sauvegarde complète (JSON) » puis « Importer une sauvegarde ». Le plus récent gagne si un match existe des deux côtés.
- Faire une sauvegarde complète après chaque match.

## Modifier le code (avec Claude)
Le code est en petits fichiers sans outil de compilation :
`js/config.js` (touches, seuils, couleurs) · `js/input.js` (saisie) · `js/stats.js` (calculs) · `js/viz.js` (cartes) · `js/ui.js` (écrans) · `js/events.js` (matchs, stockage) · `js/sync.js` (cloud Claude, sans effet ici) · `js/chart.js` (courbe) · `js/pwa.js` + `sw.js` (hors ligne).
Pour demander un changement : donner à Claude l'accès au dépôt (ou joindre les fichiers), décrire le changement ; Claude modifie, teste, et le dépôt est mis à jour. Après une mise à jour, fermer et rouvrir l'application pour charger la nouvelle version.
Règles de calcul et choix de saisie : voir le récap du projet.
