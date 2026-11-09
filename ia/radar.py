"""Lecture du radar 2D de Veo (mini-carte en haut à droite du lecteur Veo Analytics).

Veo calcule déjà la position des 22 joueurs et l'affiche sur ce radar. On lit simplement les pixels :
  - triangles rouges  = une équipe
  - ronds noirs       = l'autre équipe
  - croix jaune       = le ballon (à confirmer sur plus de vidéos)
Pas besoin de carte graphique : OpenCV + numpy suffisent.

Repère de sortie : mètres, 105 x 68, tel que le radar l'affiche (x = 0 à gauche du radar, y = 0 en haut).
La normalisation « Nous attaque vers la droite » est faite plus loin (jeu.py).
"""
import cv2
import numpy as np

L, W = 105.0, 68.0

# Couleurs en HSV OpenCV (H 0-180). Réglables si Veo change son affichage.
SLATE = dict(h=(90, 115), s_min=80, v=(45, 110))       # fond bleu-ardoise du radar
RED = dict(h_lo=8, h_hi=165, s_min=120, v_min=100)      # triangles
BLACK_MAX = 26                                          # ronds : max(B,G,R) < 26 (le radar est transparent : les arbres derrière font ~35)
YELLOW = dict(h=(20, 40), s_min=120, v_min=150)         # croix


def find_radar(frame):
    """Trouve le rectangle du radar (x, y, w, h) dans l'image entière, ou None."""
    H, Wd = frame.shape[:2]
    x0, y1 = int(Wd * 0.5), int(H * 0.45)
    reg = frame[0:y1, x0:]
    hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    m = ((h > SLATE['h'][0]) & (h < SLATE['h'][1]) & (s > SLATE['s_min']) &
         (v > SLATE['v'][0]) & (v < SLATE['v'][1])).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    i = 1 + int(np.argmax(st[1:, 4]))
    x, y, w, hh, area = st[i]
    ratio = w / max(hh, 1)
    if area < 0.004 * H * Wd or not (1.3 < ratio < 1.8):  # trop petit ou pas la forme d'un terrain
        return None
    return int(x + x0), int(y), int(w), int(hh)


def _blobs(mask, min_area, max_area):
    n, _, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    out = []
    for i in range(1, n):
        a = st[i, 4]
        if min_area <= a <= max_area:
            out.append((float(cen[i][0]), float(cen[i][1]), int(a)))
        elif a > max_area:                               # deux marques collées : on compte 2 (ou plus) au même endroit
            k = int(round(a / ((min_area + max_area) / 2)))
            out += [(float(cen[i][0]), float(cen[i][1]), int(a // max(k, 1)))] * max(1, min(k, 3))
    return out


def read_frame(frame, box):
    """Positions lues sur une image. Renvoie dict(rouge=[(x,y)], noir=[(x,y)], ballon=(x,y)|None) en mètres."""
    x, y, w, h = box
    pad = 6                                              # les marques peuvent dépasser du bord du terrain
    y0, x0 = max(0, y - pad), max(0, x - pad)
    c = frame[y0:y + h + pad, x0:x + w + pad]
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).astype(np.int16)
    H_, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    unit = (w * h) / (289 * 184)                         # taille des marques proportionnelle au radar (référence : 289 x 184 px)
    red = (S > RED['s_min']) & ((H_ < RED['h_lo']) | (H_ > RED['h_hi'])) & (V > RED['v_min'])
    blk = c.max(axis=2) < BLACK_MAX
    yel = (H_ > YELLOW['h'][0]) & (H_ < YELLOW['h'][1]) & (S > YELLOW['s_min']) & (V > YELLOW['v_min'])

    def to_m(px, py):
        return (round((px + x0 - x) / w * L, 2), round((py + y0 - y) / h * W, 2))

    rb = _blobs(red, 25 * unit, 75 * unit)
    kb = _blobs(blk, 45 * unit, 130 * unit)
    yb = _blobs(yel, 15 * unit, 120 * unit)
    ball = to_m(yb[0][0], yb[0][1]) if yb else None
    # Le porteur : la croix du ballon recouvre en partie sa marque, qui n'est plus reconnue. On regarde les pixels
    # noirs / rouges restants autour de la croix ; s'il y en a assez, on ajoute un joueur à la place du ballon.
    if yb:
        bxp, byp = yb[0][0], yb[0][1]
        rad = 8 * unit ** 0.5
        yy, xx = np.ogrid[:c.shape[0], :c.shape[1]]
        near = (xx - bxp) ** 2 + (yy - byp) ** 2 <= rad ** 2
        best = None
        for mask, lst, mn in ((blk, kb, 45 * unit), (red, rb, 25 * unit)):
            if any((a - bxp) ** 2 + (b - byp) ** 2 <= (rad * 0.9) ** 2 for a, b, _ in lst):
                best = None
                break                                    # une marque entière est déjà sous la croix
            n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
            frag = np.isin(lab, [i for i in range(1, n) if st[i, 4] < mn])   # morceaux trop petits pour être une marque entière
            cnt = int((frag & near).sum())
            if cnt >= 8 * unit and (best is None or cnt > best[0]):
                best = (cnt, lst)
        if best:
            best[1].append((bxp, byp, best[0]))
    r = [to_m(a, b) for a, b, _ in rb]
    k = [to_m(a, b) for a, b, _ in kb]
    return dict(rouge=r, noir=k, ballon=ball)


def read_video(path, fps=5.0, progress=None):
    """Lit toute la vidéo à `fps` images par seconde. Renvoie une liste de dict(t=secondes, rouge, noir, ballon)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit('Impossible d\'ouvrir la vidéo : ' + path)
    src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    every = max(1, int(round(src / fps)))
    out, box, i = [], None, 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % every == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            if box is None or i % (every * 50) == 0:     # on revérifie la place du radar de temps en temps
                b = find_radar(fr)
                box = b or box
            if box is not None:
                d = read_frame(fr, box)
                d['t'] = round(i / src, 2)
                out.append(d)
            if progress and total:
                progress(i / total)
        i += 1
    cap.release()
    return out
