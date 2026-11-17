"""AUTO-CONTRÔLE de l'IA sans radar : des mesures qui ne demandent AUCUNE vérité (ni radar, ni codage).
Elles permettent de tester l'IA sur n'importe quel match (voir PISTES.md, piste 1, et banc.py).

  - lignes : part des lignes du terrain calé (dessinées sur l'image) qui tombent sur une ligne BLANCHE de
    l'image (les lignes bleues du foot à 8 ne comptent pas ; les joueurs sont masqués). Bon calage ≈ haut.
  - reliees : part des images reliées à l'image de référence par le décor.
  - joueurs : joueurs par équipe sur le terrain (médiane) et part des images à plus de 11 dans une équipe.
  - ballon : part des images avec un ballon, et part des sauts impossibles (> 30 m/s).
"""
import math

import cv2
import numpy as np

import sans_radar as sr

ECHELLE = 0.5          # masques des lignes rangés à demi-résolution (960 x 540)
TOL = 2                # px à demi-résolution (= 4 px pleine image) : tolérance ligne dessinée / ligne vue


def _demi(frame):
    return cv2.resize(frame, None, fx=ECHELLE, fy=ECHELLE, interpolation=cv2.INTER_AREA)


def _sans_joueurs(m, boxes):
    for x0, y0, x1, y1 in boxes:
        m[max(0, int(y0 * ECHELLE) - 2):int(y1 * ECHELLE) + 2, max(0, int(x0 * ECHELLE) - 2):int(x1 * ECHELLE) + 2] = False
    return m


def masques(frame, boxes=()):
    """(blanc, zone) à demi-résolution. blanc = lignes blanches fines sur la pelouse ; zone = où une ligne
    peut être vue (pelouse fermée sur ses lignes, sans joueurs ni logo Veo)."""
    small = _demi(frame)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)))
    turf = sr.turf_mask(small).astype(np.uint8)
    turf = cv2.morphologyEx(turf, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))          # feuillage clairsemé enlevé
    turf = cv2.morphologyEx(turf, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)))
    # la pelouse = la grande zone verte reliée au bas de l'image (les arbres et haies au-dessus n'en font pas partie)
    n, lab, st, _ = cv2.connectedComponentsWithStats(turf)
    bas = [l for l in np.unique(lab[-3:, :]) if l]
    keep = max(bas, key=lambda l: st[l, cv2.CC_STAT_AREA]) if bas else (int(np.argmax(st[1:, cv2.CC_STAT_AREA])) + 1 if n > 1 else 0)
    zone = lab == keep
    # trous (lignes, joueurs) bouchés ; au-dessus du bord haut de la pelouse, rien
    cols = zone.any(axis=0)
    top = np.where(cols, zone.argmax(axis=0), zone.shape[0])
    zone = np.arange(zone.shape[0])[:, None] >= top[None, :]
    H, W = zone.shape
    zone[int(H * 0.86):, int(W * 0.84):] = False
    zone = _sans_joueurs(zone, boxes)
    # blanc : nettement plus clair que la pelouse autour ; au soleil V ≈ 250, à l'ombre teinté bleu (S ≈ 120).
    # Les lignes bleues (foot à 8) sont sombres (V ≈ 85, S > 200) : exclues.
    blanc = (tophat > 40) & (s < 150) & (v > 160) & zone
    return blanc, zone


def recouvrement(Gk, blanc, zone, lignes_m):
    """Part des points des lignes du terrain (Gk : image → terrain) qui tombent sur du blanc. Renvoie (part, n)."""
    if Gk is None:
        return None, 0
    try:
        inv = np.linalg.inv(Gk)
    except np.linalg.LinAlgError:
        return None, 0
    near = cv2.dilate(blanc.astype(np.uint8), np.ones((2 * TOL + 1, 2 * TOL + 1), np.uint8)) > 0
    H, W = blanc.shape
    # signe « devant la caméra » : celui du point du terrain vu au centre de l'image
    devant = np.sign((Gk @ np.array([W / ECHELLE / 2, H / ECHELLE / 2, 1.0]))[2]) or 1.0
    hit = n = 0
    for pl in lignes_m:
        P = np.float64(pl)
        w = devant * (inv[2, 0] * P[:, 0] + inv[2, 1] * P[:, 1] + inv[2, 2])   # < 0 : derrière la caméra
        p = cv2.perspectiveTransform(P.reshape(-1, 1, 2), inv).reshape(-1, 2) * ECHELLE
        for (x, y), ww in zip(p, w):
            if ww <= 0:
                continue
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < W and 0 <= yi < H and zone[yi, xi]:
                n += 1
                hit += bool(near[yi, xi])
    return (hit / n if n else None), n


def joueurs(frames_brut):
    """Médiane des joueurs par équipe sur le terrain, et part des images où une équipe dépasse 11."""
    if not frames_brut:
        return {'jaune': 0.0, 'noir': 0.0}, 0.0
    med = {t: float(np.median([len(f.get(t, [])) for f in frames_brut])) for t in ('jaune', 'noir')}
    trop = float(np.mean([max(len(f.get('jaune', [])), len(f.get('noir', []))) > 11 for f in frames_brut]))
    return med, trop


def ballon(path, times, vmax=30.0, tol=3.0):
    """Part des images avec un ballon, part des sauts impossibles entre deux ballons consécutifs vus."""
    vus = [(t, p) for t, p in zip(times, path) if p]
    sauts = [math.dist(a, b) > vmax * (tb - ta) + tol for (ta, a), (tb, b) in zip(vus, vus[1:])]
    return len(vus) / max(1, len(path)), (float(np.mean(sauts)) if sauts else 0.0)
