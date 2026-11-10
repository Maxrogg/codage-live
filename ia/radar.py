"""Lecture du radar 2D de Veo (mini-carte en haut à droite du lecteur Veo Analytics).

Veo calcule déjà la position des 22 joueurs et l'affiche sur ce radar. On lit simplement les pixels.
Deux affichages connus :
  1. ancien : fond bleu-ardoise, triangles rouges / ronds noirs, croix jaune = ballon  → clés « rouge », « noir »
  2. nouveau (nov. 2026) : panneau transparent assombri, lignes grises, ronds jaunes numérotés / triangles noirs
     numérotés, croix orange = ballon ; le panneau peut être déplacé, agrandi, et même dépasser du haut de
     l'écran                                                                            → clés « jaune », « noir »
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


def find_radar(frame, full=False):
    """Trouve le rectangle du radar (x, y, w, h) dans l'image, ou None.
    Par défaut on cherche en haut à droite (enregistrement d'écran) ; full=True cherche dans toute l'image
    (vidéo qui ne montrerait que le radar)."""
    H, Wd = frame.shape[:2]
    x0, y1 = (0, H) if full else (int(Wd * 0.5), int(H * 0.45))
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


# ---------------------------------------------------------------------------------------------------------
# Nouveau radar (nov. 2026) : on le trouve par ses lignes (gabarit du terrain dessiné, plusieurs tailles),
# puis on vérifie qu'il contient bien des marques de joueurs.
RATIO2 = 1.56                    # largeur / hauteur du terrain dessiné (mesuré : 465 x 298 px et 223 x 143 px)
BOX2 = dict(depth=0.150, height=0.587, circle=0.0815)   # surfaces (profondeur / largeur, hauteur / hauteur), rond central (rayon / largeur)
MARK2 = 0.043                    # diamètre d'une marque / largeur du radar
MIN_W2 = 300                     # en dessous, les marques font < 13 px : illisibles → agrandir le radar dans Veo
YELLOW2 = dict(h=(22, 36), s_min=120, v_min=190)        # ronds jaunes (le fond assombri reste sous V 120)
DARK2 = 32                                              # triangles noirs : max(B,G,R) < 32
ORANGE2 = dict(h=(3, 17), s_min=150, v_min=170)         # croix du ballon


def _line_mask(frame):
    """Traits fins clairs et peu colorés (les lignes grises du radar)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    th = cv2.morphologyEx(hsv[:, :, 2], cv2.MORPH_TOPHAT, np.ones((7, 7), np.uint8)).astype(np.float32)
    th[hsv[:, :, 1] > 70] = 0
    return cv2.GaussianBlur(np.clip(th - 15, 0, 60), (0, 0), 1.0)


_tpl_cache = {}


def _template(w):
    k = int(round(w * 4))
    if k in _tpl_cache:
        return _tpl_cache[k]
    h = w / RATIO2
    W_, H_ = int(round(w)) + 1, int(round(h)) + 1
    t = np.zeros((H_, W_), np.float32)
    X = lambda v: int(round(v * w / L)); Y = lambda v: int(round(v * h / W))  # noqa: E731
    cv2.rectangle(t, (0, 0), (W_ - 1, H_ - 1), 1, 1)
    cv2.line(t, (X(L / 2), 0), (X(L / 2), H_ - 1), 1, 1)
    r = int(round(BOX2['circle'] * w))
    cv2.ellipse(t, (X(L / 2), Y(W / 2)), (r, r), 0, 0, 360, 1, 1)
    d, bh = BOX2['depth'] * L, BOX2['height'] * W
    for x0, x1 in ((0, d), (L - d, L)):
        cv2.rectangle(t, (X(x0), Y(W / 2 - bh / 2)), (X(x1), Y(W / 2 + bh / 2)), 1, 1)
    t = cv2.GaussianBlur(t, (0, 0), 1.0)
    t -= t.mean()
    _tpl_cache[k] = (t, float((t > 0).sum()))
    return _tpl_cache[k]


def _score_at(mask, box):
    """Force moyenne des lignes du gabarit posé sur `box` (même mesure que la recherche)."""
    x, y, w = box
    t, n = _template(w)
    pad = max(0, -y)
    m = cv2.copyMakeBorder(mask, pad, 0, 0, 0, cv2.BORDER_CONSTANT, value=0) if pad else mask
    yy = y + pad
    if x < 0 or yy + t.shape[0] > m.shape[0] or x + t.shape[1] > m.shape[1]:
        return 0.0
    return float((m[yy:yy + t.shape[0], x:x + t.shape[1]] * t).sum() / n)


def _candidates(mask, wmin=MIN_W2, wmax=1100, step=1.03, pad_top=80, keep=6):
    """Meilleures positions du gabarit (x, y, w) ; y peut être négatif (radar qui dépasse du haut)."""
    m = cv2.copyMakeBorder(mask, pad_top, 0, 0, 0, cv2.BORDER_CONSTANT, value=0)
    cands = []
    w = float(wmin)
    while w <= wmax:
        t, n = _template(w)
        if t.shape[0] < m.shape[0] and t.shape[1] < m.shape[1]:
            r = cv2.matchTemplate(m, t, cv2.TM_CCORR) / n
            for _ in range(2):                            # 2 pics par taille
                _, mx, _, loc = cv2.minMaxLoc(r)
                cands.append((mx, (loc[0], loc[1] - pad_top, w)))
                cv2.rectangle(r, (loc[0] - 20, loc[1] - 20), (loc[0] + 20, loc[1] + 20), -1e9, -1)
        w *= step
    cands.sort(key=lambda c: -c[0])
    out = []
    for sc, b in cands:                                   # on garde des positions bien différentes
        if all(abs(b[0] - o[1][0]) > 15 or abs(b[1] - o[1][1]) > 15 or abs(b[2] / o[1][2] - 1) > 0.06 for o in out):
            out.append((sc, b))
        if len(out) >= keep:
            break
    return out


def _refine(mask, box, pad_top=80):
    """Ajuste position et taille au pixel près autour de `box`."""
    x, y, w = box
    best = (_score_at(mask, box), box)
    for ww in np.arange(w * 0.97, w * 1.03, max(0.5, w * 0.003)):
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                b = (x + dx, y + dy, float(ww))
                s = _score_at(mask, b)
                if s > best[0]:
                    best = (s, b)
    return best


def _marks_ok(d):
    return len(d['jaune']) >= 3 and len(d['noir']) >= 3 and len(d['jaune']) + len(d['noir']) >= 9


def find_radar2(frame, prev=None, mask=None):
    """Radar nouveau style : (x, y, w, score) ou None. `prev` = résultat précédent (le radar bouge rarement)."""
    H = frame.shape[0]
    if mask is None:
        mask = _line_mask(frame)
        mask[int(H * 0.55):] = 0                           # le radar est dans le haut de l'écran
    if prev is not None:
        s = _score_at(mask, prev[:3])
        if s >= 0.6 * prev[3] and _marks_ok(read_frame2(frame, prev)):
            return prev[:3] + (max(prev[3] * 0.9, s) if s < prev[3] else prev[3],)
    for sc, b in _candidates(mask):
        s, b = _refine(mask, (int(b[0]), int(b[1]), b[2]))
        if _marks_ok(read_frame2(frame, b + (s,))):
            return b + (s,)
    return None


def read_frame2(frame, box):
    """Marques du nouveau radar. box = (x, y, w[, score]) ; renvoie dict(jaune, noir, ballon) en mètres."""
    x, y, w = box[0], box[1], box[2]
    h = w / RATIO2
    pad = int(0.03 * w)
    X0, Y0 = max(0, int(x) - pad), max(0, int(y) - pad)
    c = frame[Y0:int(y + h) + pad, X0:int(x + w) + pad]
    if c.size == 0:
        return dict(jaune=[], noir=[], ballon=None)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).astype(np.int16)
    H_, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    d = MARK2 * w
    a_ref = np.pi * (d / 2) ** 2
    k = max(3, int(d * 0.35)) | 1
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    yel = ((H_ >= YELLOW2['h'][0]) & (H_ <= YELLOW2['h'][1]) & (S > YELLOW2['s_min']) & (V > YELLOW2['v_min'])).astype(np.uint8)
    yel = cv2.morphologyEx(yel, cv2.MORPH_CLOSE, ker)     # bouche le numéro
    dark = (c.max(axis=2) < DARK2).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, ker)
    org = ((H_ >= ORANGE2['h'][0]) & (H_ <= ORANGE2['h'][1]) & (S > ORANGE2['s_min']) & (V > ORANGE2['v_min'])).astype(np.uint8)

    def blobs(mask, lo, hi):
        n, _, st, cen = cv2.connectedComponentsWithStats(mask)
        out = []
        for i in range(1, n):
            a = st[i, 4]
            if lo * a_ref <= a <= hi * a_ref:
                out.append((cen[i][0], cen[i][1], int(a)))
            elif hi * a_ref < a < 4 * hi * a_ref:          # marques collées
                kk = int(round(a / ((lo + hi) / 2 * a_ref)))
                out += [(cen[i][0], cen[i][1], int(a))] * max(1, min(kk, 3))
        return out
    J = blobs(yel, 0.45, 1.6)
    N = blobs(dark, 0.30, 1.4)
    O = blobs(org, 0.10, 1.5)
    ball = max(O, key=lambda b: b[2]) if O else None

    def to_m(px, py):
        return (round((px + X0 - x) / w * L, 2), round((py + Y0 - y) / h * W, 2))
    # Le porteur : la croix recouvre sa marque. Si aucune marque entière n'est sous la croix mais qu'il reste
    # assez de pixels jaunes (ou noirs) autour, on ajoute un joueur de cette couleur à la place du ballon.
    if ball:
        bx, by = ball[0], ball[1]
        if not any((a - bx) ** 2 + (b - by) ** 2 <= (0.6 * d) ** 2 for a, b, _ in J + N):
            yy, xx = np.ogrid[:c.shape[0], :c.shape[1]]
            near = (xx - bx) ** 2 + (yy - by) ** 2 <= (0.8 * d) ** 2
            ny, nd = int((yel.astype(bool) & near).sum()), int((dark.astype(bool) & near).sum())
            if max(ny, nd) >= 0.15 * a_ref:
                (J if ny >= nd else N).append((bx, by, 0))
    return dict(jaune=[to_m(a, b) for a, b, _ in J], noir=[to_m(a, b) for a, b, _ in N],
                ballon=to_m(ball[0], ball[1]) if ball else None)


def read_video(path, fps=5.0, progress=None):
    """Lit toute la vidéo à `fps` images par seconde. Renvoie une liste de dict(t=secondes, <couleurs>, ballon).
    Ancien radar : clés rouge / noir. Nouveau radar : clés jaune / noir. Les images sans radar lisible sont sautées
    (read_video.skipped donne leur nombre)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit('Impossible d\'ouvrir la vidéo : ' + path)
    src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    every = max(1, int(round(src / fps)))
    out, box, box2, i, style, skipped, retry = [], None, None, 0, None, 0, 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % every == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            if style != 2 and (box is None or i % (every * 50) == 0):   # on revérifie la place du radar de temps en temps
                b = find_radar(fr) or (find_radar(fr, full=True) if fr.shape[1] < 1000 else None)
                box = b or box
                if box is not None:
                    style = 1
            d = None
            if style == 1 and box is not None:
                d = read_frame(fr, box)
            elif style != 1:
                if box2 is not None or retry <= 0:
                    box2 = find_radar2(fr, box2)
                    retry = 0 if box2 else 4                   # recherche complète au plus 1 image sur 5
                    if box2 is not None:
                        style = 2
                else:
                    retry -= 1
                if box2 is not None:
                    d = read_frame2(fr, box2)
            if d is not None:
                d['t'] = round(i / src, 2)
                out.append(d)
            else:
                skipped += 1
            if progress and total:
                progress(i / total)
        i += 1
    cap.release()
    read_video.skipped = skipped
    return out


read_video.skipped = 0
