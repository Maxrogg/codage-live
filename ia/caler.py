"""CALAGE DU TERRAIN PAR CLICS (pour l'IA sans radar). Une fois par terrain : la Veo est toujours à la même place.

    py caler.py video.mp4 --nom stade_club --longueur 105 --largeur 68
    (ou glisser la vidéo sur caler.bat)

Vidéo : 1 à 2 minutes de la caméra Veo pendant que le jeu va d'un but à l'autre (la caméra balaie tout le terrain).
Le programme montre la vidéo ; on clique les REPÈRES du terrain (coins, surfaces, ligne médiane, rond central...)
sur l'image où on les voit le mieux. Chaque clic est ramené dans une image de référence par le décor (arbres,
maisons, clôture), puis le calage image → terrain est calculé. 10 à 12 repères bien cliqués ≈ 0,5-1 m d'erreur
(mesuré le 17 nov. 2026, voir ETAT.md). « Loin » = côté opposé à la caméra, « G » = à gauche vu de la caméra.

Touches :
    clic                cliquer le repère affiché en haut : une loupe s'ouvre, re-cliquer le point exact
    Échap               fermer la loupe sans rien garder
    N / P               repère suivant / précédent (pour en passer un)
    → / ←  (ou D / Q)   image suivante / précédente (0,2 s)      ↑ / ↓ (ou Z / S) : ± 5 s
    U                   annuler le dernier clic
    L                   montrer / cacher les lignes du terrain calculées (pour vérifier)
    Entrée              calculer et enregistrer        X : quitter (ou fermer la fenêtre)

Résultat : ia/terrains/<nom>/terrain.json + reference.jpg (HORS dépôt : image du stade).
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sans_radar as sr  # noqa: E402

RADAR = (105.0, 68.0)         # repère du radar Veo (et de jeu.py) : x le long du terrain, y = 0 côté loin


def reperes(longueur=105.0, largeur=68.0, surface=(16.5, 40.32), but=(5.5, 18.32), rond=9.15, penalty=11.0):
    """Repères du terrain réel (mètres) ramenés au repère du radar 105 x 68. Ordre = ordre des clics proposé."""
    L, W = longueur, largeur
    sx, sy = RADAR[0] / L, RADAR[1] / W
    m = W / 2
    pts = [
        ('centre du terrain', L / 2, m), ('milieu, touche loin', L / 2, 0), ('milieu, touche pres', L / 2, W),
        ('rond central, cote loin', L / 2, m - rond), ('rond central, cote pres', L / 2, m + rond),
    ]
    for cote, x0, s in (('G', 0.0, 1), ('D', L, -1)):
        pts += [
            ('surface %s : coin loin (sur la ligne de but)' % cote, x0, m - surface[1] / 2),
            ('surface %s : coin loin (avant)' % cote, x0 + s * surface[0], m - surface[1] / 2),
            ('surface %s : coin pres (avant)' % cote, x0 + s * surface[0], m + surface[1] / 2),
            ('surface %s : coin pres (sur la ligne de but)' % cote, x0, m + surface[1] / 2),
            ('point de penalty %s' % cote, x0 + s * penalty, m),
            ('surface de but %s : coin loin (avant)' % cote, x0 + s * but[0], m - but[1] / 2),
            ('surface de but %s : coin pres (avant)' % cote, x0 + s * but[0], m + but[1] / 2),
            ('corner %s loin' % cote, x0, 0), ('corner %s pres' % cote, x0, W),
        ]
    return [(n, x * sx, y * sy) for n, x, y in pts]


def lignes(longueur=105.0, largeur=68.0, surface=(16.5, 40.32), but=(5.5, 18.32), rond=9.15, **_):
    """Lignes du terrain (polylignes, repère du radar) pour vérifier le calage à l'œil."""
    L, W = longueur, largeur
    sx, sy = RADAR[0] / L, RADAR[1] / W
    m = W / 2
    out = [[(0, 0), (L, 0), (L, W), (0, W), (0, 0)], [(L / 2, 0), (L / 2, W)]]
    out.append([(L / 2 + rond * np.cos(a), m + rond * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 49)])
    for x0, s in ((0.0, 1), (L, -1)):
        for p, w in (surface, but):
            out.append([(x0, m - w / 2), (x0 + s * p, m - w / 2), (x0 + s * p, m + w / 2), (x0, m + w / 2)])
    dense = []
    for pl in out:                                   # points rapprochés : les lignes restent justes en perspective
        d = []
        for a, b in zip(pl, pl[1:]):
            d += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in np.linspace(0, 1, 12)[:-1]]
        d.append(pl[-1])
        dense.append([(x * sx, y * sy) for x, y in d])
    return dense


def calculer(clics):
    """clics = [(nom, (x_ref, y_ref) pixels dans l'image de référence, (X, Y) terrain)] →
    (G image de référence → terrain, {nom: écart en m}) ; G = None si moins de 4 repères."""
    if len(clics) < 4:
        return None, {}
    src = np.float32([c[1] for c in clics])
    dst = np.float32([c[2] for c in clics])
    G = None
    if len(clics) >= 6:
        G, _ = cv2.findHomography(src, dst, cv2.RANSAC, 2.0)
    if G is None:
        G, _ = cv2.findHomography(src, dst, 0)
    if G is None:
        return None, {}
    P = sr.project(G, src)
    return G, {c[0]: round(float(np.hypot(*(p - np.array(c[2])))), 2) for c, p in zip(clics, P)}


class Video:
    """Images de la vidéo à 5 / s, lues à la demande, et leur lien avec l'image de référence par le décor."""

    def __init__(self, path, fps=5.0, ref=None):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise SystemExit('Vidéo illisible : ' + path)
        src = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.step = 1.0 / fps
        self.n = max(1, int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) / src * fps))
        self.tr = sr.CameraTracker()
        self._img, self._H = {}, {}
        self.set_ref(self.n // 2 if ref is None else ref)

    def image(self, k):
        if k not in self._img:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, k * self.step * 1000)
            ok, fr = self.cap.read()
            self._img[k] = fr if ok else None
            if len(self._img) > 60:                  # mémoire : on garde les 60 dernières
                self._img.pop(next(k2 for k2 in self._img if k2 not in (k, getattr(self, 'ref', None))))
        return self._img[k]

    def set_ref(self, k):
        self.ref = k
        self.f_ref = self.tr.features(self.image(k), [])
        self._H = {k: np.eye(3)}

    def H(self, k):
        """Homographie image k → image de référence (None si le décor ne correspond pas)."""
        if k not in self._H:
            fr = self.image(k)
            self._H[k] = None if fr is None else self.tr.homography(self.tr.features(fr, []), self.f_ref)
        return self._H[k]


class Caleur:
    ZOOM = 5                                          # grossissement de la loupe
    LOUPE = (384, 216)                                # zone grossie (pixels de la vidéo)

    def __init__(self, video, dims, nom):
        self.v, self.dims, self.nom = video, dims, nom
        self.rep = reperes(**dims)
        self.k, self.i = video.ref, 0
        self.clics = []                               # [(nom, k, (x, y) pixels de l'image k)]
        self.loupe = None                             # (x0, y0) coin de la zone grossie
        self.voir_lignes = False
        self.G, self.ecarts = None, {}
        self.msg = ''
        self.aff = 1.0                                # échelle d'affichage (écran)

    # --- clics -----------------------------------------------------------------------------------------
    def souris(self, ev, x, y, *_):
        """x, y = position dans la fenêtre (image affichée)."""
        if ev != cv2.EVENT_LBUTTONDOWN:
            return
        if self.loupe is None:
            fr = self.v.image(self.k)
            if fr is None:
                return
            Hh, Ww = fr.shape[:2]
            lw, lh = self.LOUPE
            x, y = x / self.aff, y / self.aff
            self.loupe = (int(min(max(0, x - lw / 2), Ww - lw)), int(min(max(0, y - lh / 2), Hh - lh)))
            return
        x0, y0 = self.loupe
        z = self.ZOOM * self.aff                      # pixels de la fenêtre par pixel vidéo, dans la loupe
        self.ajouter((x0 + x / z, y0 + y / z))
        self.loupe = None

    def ajouter(self, p):
        if self.v.H(self.k) is None:
            self.msg = 'Decor non reconnu sur cette image : prendre une autre image.'
            return
        nom = self.rep[self.i][0]
        self.clics = [c for c in self.clics if c[0] != nom] + [(nom, self.k, (float(p[0]), float(p[1])))]
        self.recalculer()
        self.suivant(1)

    def suivant(self, d):
        faits = {c[0] for c in self.clics}
        for _ in range(len(self.rep)):
            self.i = (self.i + d) % len(self.rep)
            if d != 1 or self.rep[self.i][0] not in faits:
                break

    def recalculer(self):
        pos = {n: (x, y) for n, x, y in self.rep}
        cl = []
        for nom, k, p in self.clics:
            q = sr.project(self.v.H(k), [p])[0]
            cl.append((nom, (float(q[0]), float(q[1])), pos[nom]))
        self.G, self.ecarts = calculer(cl)
        if self.G is not None:
            pire = max(self.ecarts.items(), key=lambda kv: kv[1])
            self.msg = '%d reperes, ecart moyen %.2f m (pire : %s, %.1f m)' % (
                len(cl), float(np.mean(list(self.ecarts.values()))), pire[0], pire[1])
        else:
            self.msg = '%d repere(s) : il en faut au moins 4 (mieux : 10-12, des deux cotes du terrain)' % len(cl)

    # --- affichage -------------------------------------------------------------------------------------
    def dessin(self):
        fr = self.v.image(self.k)
        if fr is None:
            return np.zeros((540, 960, 3), np.uint8)
        im = fr.copy()
        Hk = self.v.H(self.k)
        if self.voir_lignes and self.G is not None and Hk is not None:
            inv = np.linalg.inv(self.G @ Hk)
            for pl in lignes(**self.dims):
                q = sr.project(inv, pl)
                cv2.polylines(im, [np.int32(q).reshape(-1, 1, 2)], False, (0, 0, 255), 2, cv2.LINE_AA)
        for nom, k, p in self.clics:
            if k == self.k:
                cv2.drawMarker(im, (int(p[0]), int(p[1])), (0, 255, 255), cv2.MARKER_CROSS, 24, 2)
        if self.loupe is not None:
            x0, y0 = self.loupe
            lw, lh = self.LOUPE
            im = cv2.resize(im[y0:y0 + lh, x0:x0 + lw], (lw * self.ZOOM, lh * self.ZOOM), interpolation=cv2.INTER_CUBIC)
        if self.aff != 1:
            im = cv2.resize(im, None, fx=self.aff, fy=self.aff, interpolation=cv2.INTER_AREA)
        haut = [
            'A CLIQUER : %s   (%d / %d)' % (self.rep[self.i][0], self.i + 1, len(self.rep)),
            't = %.1f s%s  | clic = loupe  N/P = repere  fleches = image  U = annuler  L = lignes  Entree = enregistrer  X = quitter'
            % (self.k * self.v.step, '' if Hk is not None else '  DECOR NON RECONNU'),
            'LOUPE : cliquer le point exact (Echap = annuler)' if self.loupe else self.msg,
        ]
        for j, txt in enumerate(haut):
            if txt:
                cv2.putText(im, txt, (10, 28 + 26 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(im, txt, (10, 28 + 26 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        return im

    def touche(self, key):
        """Renvoie False pour quitter."""
        if key == 27:
            self.loupe = None
        elif key in (ord('n'), ord('N')):
            self.suivant(1)
        elif key in (ord('p'), ord('P')):
            self.suivant(-1)
        elif key in (2555904, ord('d'), ord('D')):                   # →
            self.k = min(self.v.n - 1, self.k + 1)
        elif key in (2424832, ord('q'), ord('Q')):                   # ←
            self.k = max(0, self.k - 1)
        elif key in (2490368, ord('z'), ord('Z')):                   # ↑
            self.k = min(self.v.n - 1, self.k + 25)
        elif key in (2621440, ord('s'), ord('S')):                   # ↓
            self.k = max(0, self.k - 25)
        elif key in (ord('u'), ord('U')):
            if self.clics:
                self.clics.pop()
                self.recalculer()
        elif key in (ord('l'), ord('L')):
            self.voir_lignes = not self.voir_lignes
        elif key in (13, 10):
            self.enregistrer()
        elif key in (ord('x'), ord('X')):
            return False
        return True

    def enregistrer(self, dossier=None):
        if self.G is None:
            self.msg = 'Pas encore de calage : au moins 4 reperes.'
            return None
        d = dossier or os.path.join(HERE, 'terrains', self.nom)
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, 'reference.jpg'), self.v.image(self.v.ref), [cv2.IMWRITE_JPEG_QUALITY, 95])
        out = dict(nom=self.nom, dims=self.dims, ref_t=round(self.v.ref * self.v.step, 3),
                   G=self.G.tolist(), ecarts=self.ecarts,
                   clics=[dict(nom=n, t=round(k * self.v.step, 3), px=[round(p[0], 1), round(p[1], 1)]) for n, k, p in self.clics])
        p = os.path.join(d, 'terrain.json')
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        self.msg = 'Enregistre : ' + p
        return p

    def lancer(self):
        fr = self.v.image(self.k)
        self.aff = min(1.0, 1500 / fr.shape[1])                       # tient dans l'écran
        win = 'Calage du terrain'
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(win, self.souris)
        while True:
            cv2.imshow(win, self.dessin())
            key = cv2.waitKeyEx(30)
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key != -1 and not self.touche(key):
                break
        cv2.destroyAllWindows()
        print(self.msg)


def main():
    ap = argparse.ArgumentParser(description='Calage du terrain par clics (IA sans radar).')
    ap.add_argument('video')
    ap.add_argument('--nom', default='terrain_club', help='nom du terrain (dossier ia/terrains/<nom>)')
    ap.add_argument('--longueur', type=float, default=105.0, help='m, ligne de but à ligne de but')
    ap.add_argument('--largeur', type=float, default=68.0, help='m, touche à touche')
    ap.add_argument('--surface', type=float, nargs=2, default=[16.5, 40.32], help='surface de réparation : profondeur largeur (m)')
    ap.add_argument('--but', type=float, nargs=2, default=[5.5, 18.32], help='surface de but : profondeur largeur (m)')
    ap.add_argument('--rond', type=float, default=9.15, help='rayon du rond central (m)')
    ap.add_argument('--penalty', type=float, default=11.0, help='distance du point de penalty (m)')
    a = ap.parse_args()
    dims = dict(longueur=a.longueur, largeur=a.largeur, surface=list(a.surface), but=list(a.but), rond=a.rond, penalty=a.penalty)
    Caleur(Video(a.video), dims, a.nom).lancer()


if __name__ == '__main__':
    main()
