"""CALAGE AUTOMATIQUE DU TERRAIN (sans radar, sans clics) : PISTES.md, piste 2.

Idée : la Veo est fixe. Toutes les images d'un match sont reliées à UNE image de référence par le décor (banc.py).
On cherche une CAMÉRA (position au bord du terrain, hauteur, orientation, zoom) et les DIMENSIONS du terrain telles
que les lignes du terrain, dessinées dans toutes ces images, tombent sur les lignes blanches vues (autocontrole.py).
  1. recherche large (méthode de l'entropie croisée) sur des paramètres physiques (bien moins de faux calages
     qu'avec les 8 nombres d'une homographie) ;
  2. affinage : chaque point de ligne du modèle est apparié au blanc le plus proche, homographie ajustée, on recommence
     en resserrant (ICP).
Sortie : G = image de référence → repère du radar 105 x 68 (comme caler.py), + dimensions estimées.

    py calage_auto.py --seq off_placee cascol_10 cascol_50 cascol_100 --nom club_auto
    → references/terrain_<nom>/terrain.json + reference.jpg (+ controle.jpg : lignes dessinées)
"""
import argparse
import json
import math
import os
import shutil
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autocontrole as ac  # noqa: E402
import caler               # noqa: E402

E = ac.ECHELLE
S = np.diag([E, E, 1.0])
W_IMG, H_IMG = 1920, 1080


# ------------------------------------------------------------------ caméra → homographie terrain → image de référence
def homographie(p, L, W):
    """p = (cx, d, h, pan, tilt, roulis, f) : caméra en (cx, W + d, h) mètres (d = recul derrière la touche près),
    angles en degrés, f en pixels (image de référence). Renvoie H terrain réel (x, y) → pixels."""
    cx, d, h, pan, tilt, roll, f = p
    th, ph, ro = map(math.radians, (pan, tilt, roll))
    fw = np.array([math.sin(th) * math.cos(ph), -math.cos(th) * math.cos(ph), -math.sin(ph)])
    rt = np.array([math.cos(th), math.sin(th), 0.0])
    dn = np.cross(rt, fw)
    rt, dn = math.cos(ro) * rt + math.sin(ro) * dn, -math.sin(ro) * rt + math.cos(ro) * dn
    R = np.stack([rt, dn, fw])
    C = np.array([cx, W + d, h])
    K = np.array([[f, 0, W_IMG / 2], [0, f, H_IMG / 2], [0, 0, 1.0]])
    return K @ np.column_stack([R[:, 0], R[:, 1], -R @ C])


def vers_radar(L, W):
    return np.diag([caler.RADAR[0] / L, caler.RADAR[1] / W, 1.0])


def modele(L, W, pas=1.0):
    """Points des lignes du terrain (mètres réels), tous les ~pas mètres."""
    pts = []
    sx, sy = L / caler.RADAR[0], W / caler.RADAR[1]
    for pl in caler.lignes(longueur=L, largeur=W):
        pl = np.array(pl) * [sx, sy]                       # caler.lignes est en repère radar : retour en mètres réels
        for a, b in zip(pl, pl[1:]):
            n = max(1, int(np.hypot(*(b - a)) / pas))
            pts += [a + (b - a) * t for t in np.arange(n) / n]
    return np.array(pts)


# ------------------------------------------------------------------ vues (masques des lignes + lien au décor)
class Vue:
    def __init__(self, H, blanc, zone):
        self.H = np.array(H)                              # cette image → image de référence
        self.Hinv = np.linalg.inv(self.H)
        self.blanc, self.zone = blanc, zone
        self.dt, self.lab = cv2.distanceTransformWithLabels((~blanc).astype(np.uint8), cv2.DIST_L2, 3,
                                                            labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(blanc)
        self.near = np.zeros((self.lab.max() + 1, 2), np.float32)   # label → pixel blanc le plus proche
        self.near[self.lab[ys, xs]] = np.stack([xs, ys], 1)
        self.wpts = np.stack([xs, ys], 1)
        if len(self.wpts) > 3000:
            self.wpts = self.wpts[np.random.default_rng(0).choice(len(self.wpts), 3000, replace=False)]


def charger_vues(seqs):
    import banc
    vues = []
    for s in seqs:
        c = json.load(open(os.path.join(banc.REF, 'banc_cache', s + '.json'), encoding='utf-8'))
        m = banc.charger_masques(np.load(os.path.join(banc.REF, 'banc_cache', s + '_lignes.npz')))
        for i, (b, z) in m.items():
            if c['frames'][i]['H'] is not None and b.sum() > 200:
                vues.append(Vue(c['frames'][i]['H'], b, z))
    return vues


def projeter(Hw, vue, pts):
    """Points terrain → pixels (demi-résolution) de la vue ; masque « devant la caméra »."""
    M = S @ vue.Hinv @ Hw
    P = np.column_stack([pts, np.ones(len(pts))]) @ M.T
    sgn = np.sign(P[:, 2].mean()) or 1.0
    ok = P[:, 2] * sgn > 1e-9
    q = P[:, :2] / np.where(ok, P[:, 2], 1)[:, None]
    return q, ok


def score(Hw, vues, pts, sigma, segs=None):
    """F1 entre lignes du modèle et blanc vu. Rappel : points du modèle (dans la pelouse) proches du blanc ;
    précision : pixels blancs (de la pelouse) proches d'une ligne du modèle dessinée."""
    rec_s = rec_n = pre_s = pre_n = 0.0
    for v in vues:
        q, ok = projeter(Hw, v, pts)
        h, w = v.blanc.shape
        ins = ok & (q[:, 0] >= 0) & (q[:, 0] < w - 1) & (q[:, 1] >= 0) & (q[:, 1] < h - 1)
        qi = q[ins].astype(int)
        qi = qi[v.zone[qi[:, 1], qi[:, 0]]]
        if len(qi):
            rec_s += np.exp(-v.dt[qi[:, 1], qi[:, 0]] ** 2 / (2 * sigma ** 2)).sum()
            rec_n += len(qi)
        img = np.zeros((h, w), np.uint8)
        qv = q[ok & (np.abs(q[:, 0]) < 4 * w) & (np.abs(q[:, 1]) < 4 * h)].astype(int)
        img[np.clip(qv[:, 1], 0, h - 1), np.clip(qv[:, 0], 0, w - 1)] = 0      # (bord ignoré)
        inside = (qv[:, 0] >= 0) & (qv[:, 0] < w) & (qv[:, 1] >= 0) & (qv[:, 1] < h)
        img[qv[inside, 1], qv[inside, 0]] = 255
        img = cv2.dilate(img, np.ones((2, 2), np.uint8))
        dt_m = cv2.distanceTransform(255 - img, cv2.DIST_L2, 3)
        pre_s += np.exp(-dt_m[v.wpts[:, 1], v.wpts[:, 0]] ** 2 / (2 * sigma ** 2)).sum()
        pre_n += len(v.wpts)
    if rec_n < 200:
        return 0.0
    r, p = rec_s / rec_n, pre_s / max(pre_n, 1)
    return 2 * r * p / (r + p + 1e-9)


# ------------------------------------------------------------------ 1. recherche large (entropie croisée)
BORNES = np.array([
    # cx (part de L), d (m), h (m), pan, tilt, roulis (deg), f (px), L (m), W (m)
    (0.2, 0.8), (-2, 30), (3, 20), (-70, 70), (2, 40), (-6, 6), (500, 4000), (55, 110), (38, 75)], float)


def decode(z):
    cx, d, h, pan, tilt, roll, f, L, W = z
    return (cx * L, d, h, pan, tilt, roll, f), L, W


def recherche(vues, n0=1500, n=250, iters=12, elite=25, sigma=6.0, seed=0, log=print, dims=None):
    rng = np.random.default_rng(seed)
    lo, hi = BORNES[:, 0].copy(), BORNES[:, 1].copy()
    if dims:
        lo[7], hi[7], lo[8], hi[8] = dims[0], dims[0], dims[1], dims[1]
    base = {}

    def f(z, sg):
        p, L, W = decode(z)
        key = (round(L), round(W))
        if key not in base:
            base[key] = modele(key[0], key[1], pas=1.5)
        pts = base[key] * [L / max(key[0], 1), W / max(key[1], 1)]
        return score(homographie(p, L, W), vues, pts, sg)

    Z = rng.uniform(lo, hi, (n0, len(lo)))
    sc = np.array([f(z, sigma) for z in Z])
    for it in range(iters):
        order = np.argsort(-sc)[:elite]
        best = Z[order]
        mu, sd = best.mean(0), best.std(0) + 1e-4 * (hi - lo)
        Zn = np.clip(rng.normal(mu, sd, (n, len(lo))), lo, hi)
        sigma = max(2.0, sigma * 0.85)
        Z = np.vstack([best, Zn])
        sc = np.array([f(z, sigma) for z in Z])                # tout re-noté avec le nouveau sigma
        zb = Z[sc.argmax()]
        log('  recherche %2d : meilleur %.3f  L %.1f W %.1f  h %.1f d %.1f tilt %.1f f %.0f' % (
            it, sc.max(), zb[7], zb[8], zb[2], zb[1], zb[4], zb[6]))
    z = Z[sc.argmax()]
    p, L, W = decode(z)
    return homographie(p, L, W), L, W, float(sc.max()), z


# ------------------------------------------------------------------ 2. affinage (ICP sur l'homographie)
def affiner(Hw, L, W, vues, tols=(8, 5, 3, 2), log=print):
    pts = modele(L, W, pas=0.5)
    for tol in tols:
        n_src = n_inl = 0
        for _ in range(3):
            src, dst = [], []
            for v in vues:
                q, ok = projeter(Hw, v, pts)
                h, w = v.blanc.shape
                idx = np.nonzero(ok & (q[:, 0] >= 0) & (q[:, 0] < w - 1) & (q[:, 1] >= 0) & (q[:, 1] < h - 1))[0]
                qi = q[idx].astype(int)
                keep = v.zone[qi[:, 1], qi[:, 0]] & (v.dt[qi[:, 1], qi[:, 0]] <= tol)
                idx, qi = idx[keep], qi[keep]
                if not len(idx):
                    continue
                nearest = v.near[v.lab[qi[:, 1], qi[:, 0]]] / E                       # pleine résolution
                ref = cv2.perspectiveTransform(nearest.reshape(-1, 1, 2).astype(np.float64), v.H).reshape(-1, 2)
                src.append(pts[idx]); dst.append(ref)
            if not src:
                return Hw
            src, dst = np.vstack(src), np.vstack(dst)
            H2, inl = cv2.findHomography(src.astype(np.float32), dst.astype(np.float32), cv2.RANSAC, 2.0 / E)
            if H2 is None:
                return Hw
            Hw, n_src, n_inl = H2, len(src), int(inl.sum())
        log('  affinage (tolérance %d px) : %d appariements, %d gardés' % (tol, n_src, n_inl))
    return Hw


def choisir(vues, n=16, seed=0):
    """Quelques vues pour la recherche large (les plus riches en lignes, réparties) : la note coûte ~3 ms par vue."""
    if len(vues) <= n:
        return vues
    ordre = sorted(range(len(vues)), key=lambda i: -vues[i].blanc.sum())[:3 * n]
    rng = np.random.default_rng(seed)
    return [vues[i] for i in sorted(rng.choice(ordre, n, replace=False))]


def calage(vues, log=print, seeds=(0, 1, 2), dims=None, n_vues=16):
    best = None
    for s in seeds:
        Hw, L, W, sc, z = recherche(choisir(vues, n_vues, s), seed=s, log=log, dims=dims)
        log(' essai %d : %.3f (L %.1f, W %.1f)' % (s, sc, L, W))
        if best is None or sc > best[3]:
            best = (Hw, L, W, sc)
    Hw, L, W, sc = best
    sc = score(Hw, vues, modele(L, W, 1.5), 2.0)
    Hw = affiner(Hw, L, W, vues, log=log)
    sc2 = score(Hw, vues, modele(L, W, 1.5), 2.0)
    G = vers_radar(L, W) @ np.linalg.inv(Hw)          # image de référence → repère radar 105 x 68
    return G, L, W, sc, sc2


def dessiner(img, G, dims, couleur=(0, 0, 255)):
    im = img.copy()
    inv = np.linalg.inv(G)
    for pl in caler.lignes(**dims):
        q = cv2.perspectiveTransform(np.float64(pl).reshape(-1, 1, 2), inv)
        cv2.polylines(im, [np.int32(q)], False, couleur, 2, cv2.LINE_AA)
    return im


def main():
    ap = argparse.ArgumentParser(description='Calage automatique du terrain (sans radar ni clics).')
    ap.add_argument('--seq', nargs='+', required=True, help='séquences du banc (même terrain, même image de référence)')
    ap.add_argument('--terrain', default='references/terrain_club', help='dossier du terrain (reference.jpg)')
    ap.add_argument('--nom', default='club_auto')
    ap.add_argument('--dims', type=float, nargs=2, help='longueur largeur connues (sinon cherchées)')
    ap.add_argument('--essais', type=int, default=3)
    a = ap.parse_args()
    t0 = time.time()
    vues = charger_vues(a.seq)
    print('%d vues' % len(vues))
    G, L, W, sc, sc2 = calage(vues, dims=a.dims, seeds=range(a.essais))
    d = os.path.join(HERE, 'references', 'terrain_' + a.nom)
    os.makedirs(d, exist_ok=True)
    src = a.terrain if os.path.isabs(a.terrain) else os.path.join(HERE, a.terrain)
    shutil.copy(os.path.join(src, 'reference.jpg'), d)
    dims = dict(longueur=round(float(L), 1), largeur=round(float(W), 1))
    json.dump(dict(nom=a.nom, dims=dims, G=G.tolist(), source='calage_auto', score=round(float(sc2), 3), score_avant_affinage=round(float(sc), 3), seqs=a.seq),
              open(os.path.join(d, 'terrain.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cv2.imwrite(os.path.join(d, 'controle.jpg'), dessiner(cv2.imread(os.path.join(d, 'reference.jpg')), G, dims))
    print('Terrain %.1f x %.1f m, score %.3f → %.3f après affinage, %.0f s → %s' % (L, W, sc, sc2, time.time() - t0, d))


if __name__ == '__main__':
    main()
