#!/usr/bin/env python3
"""Construit l'application installable (PWA) à partir du code source de /home/claude/codage-live."""
import hashlib, json, os, shutil, subprocess, sys
from PIL import Image, ImageDraw
SRC, OUT = '/home/claude/codage-live', '/home/claude/codage-live-app'
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
for n in ('index.html', 'css', 'js'):
    (shutil.copytree if os.path.isdir(f'{SRC}/{n}') else shutil.copy)(f'{SRC}/{n}', f'{OUT}/{n}')

# --- icônes (terrain stylisé, générique)
def icon(size, path, pad=0.0):
    im = Image.new('RGB', (size, size), '#111215'); d = ImageDraw.Draw(im)
    m = int(size * (0.14 + pad)); w = max(3, size // 64); c = '#ffd21f'
    d.rectangle([m, m * 1.25, size - m, size - m * 1.25], outline=c, width=w)
    d.line([size // 2, m * 1.25, size // 2, size - m * 1.25], fill=c, width=w)
    r = size // 9; d.ellipse([size // 2 - r, size // 2 - r, size // 2 + r, size // 2 + r], outline=c, width=w)
    bw, bh = int(size * .11), int(size * .26)
    for x0 in (m, size - m - bw):
        d.rectangle([x0, size // 2 - bh // 2, x0 + bw, size // 2 + bh // 2], outline=c, width=w)
    im.save(path)
os.makedirs(f'{OUT}/icons')
icon(192, f'{OUT}/icons/icon-192.png'); icon(512, f'{OUT}/icons/icon-512.png'); icon(512, f'{OUT}/icons/icon-maskable-512.png', pad=0.08)

# --- manifest
json.dump({
    'name': 'Codage live — Match', 'short_name': 'Codage live', 'lang': 'fr',
    'start_url': './index.html', 'scope': './', 'display': 'standalone',
    'background_color': '#111215', 'theme_color': '#111215',
    'icons': [{'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
              {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
              {'src': 'icons/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}]
}, open(f'{OUT}/manifest.webmanifest', 'w'), ensure_ascii=False, indent=1)

# --- pwa.js : service worker + bouton « Installer »
open(f'{OUT}/js/pwa.js', 'w').write("""/* PWA : fonctionnement hors ligne + bouton « Installer l'application ». Ne fait rien dans un simple fichier local. */
(function () {
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    navigator.serviceWorker.register('sw.js').catch(function () { /* hors ligne impossible : l'outil marche quand même en ligne */ });
  }
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    const b = document.createElement('button'); b.textContent = 'Installer l\\'application'; b.style.marginLeft = '8px';
    b.onclick = function () { e.prompt(); b.remove(); };
    const nav = document.querySelector('header nav'); if (nav) nav.appendChild(b);
  });
})();
""")

# --- index.html : manifest + pwa.js
s = open(f'{OUT}/index.html', encoding='utf-8').read()
s = s.replace('<link rel="stylesheet" href="css/style.css">', '<link rel="manifest" href="manifest.webmanifest">\n<meta name="theme-color" content="#111215">\n<link rel="icon" href="icons/icon-192.png">\n<link rel="stylesheet" href="css/style.css">')
s = s.replace('<script>FC.ui.init();</script>', '<script src="js/pwa.js"></script>\n<script>FC.ui.init();</script>')
open(f'{OUT}/index.html', 'w', encoding='utf-8').write(s)

# --- sw.js : tout en cache ; la version change quand un fichier change
files = []
for root, _, names in os.walk(OUT):
    for n in names:
        p = os.path.relpath(os.path.join(root, n), OUT)
        if p not in ('sw.js', 'README.md') and not p.endswith('.zip'): files.append(p)
files.sort()
h = hashlib.sha256(b''.join(open(f'{OUT}/{p}', 'rb').read() for p in files)).hexdigest()[:10]
open(f'{OUT}/sw.js', 'w').write(f"""/* Service worker : met tous les fichiers en cache pour fonctionner hors ligne. Version {h}. */
const V = 'codage-live-{h}';
const FILES = {json.dumps(['./'] + files)};
self.addEventListener('install', function (e) {{ e.waitUntil(caches.open(V).then(function (c) {{ return c.addAll(FILES); }}).then(function () {{ return self.skipWaiting(); }})); }});
self.addEventListener('activate', function (e) {{
  e.waitUntil(caches.keys().then(function (ks) {{ return Promise.all(ks.filter(function (k) {{ return k !== V; }}).map(function (k) {{ return caches.delete(k); }})); }}).then(function () {{ return self.clients.claim(); }}));
}});
self.addEventListener('fetch', function (e) {{
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request, {{ ignoreSearch: true }}).then(function (r) {{ return r || fetch(e.request); }}));
}});
""")
print('version', h, len(files), 'fichiers')

# --- README + zip
open(f'{OUT}/README.md', 'w', encoding='utf-8').write("""# Codage live — application de match

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
""")
subprocess.run(['rm', '-f', '/home/claude/codage-live-app.zip'])
subprocess.run(['zip', '-qr', '/home/claude/codage-live-app.zip', '.'], cwd=OUT, check=True)
print('zip ok')
