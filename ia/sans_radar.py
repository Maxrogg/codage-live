"""IA SANS RADAR (prototype, pour le live Veo).

En live il n'y a que l'image de la caméra Veo (qui suit le jeu, pas de vue panoramique). Ce module :
  1. trouve les joueurs et le ballon dans l'image (detect) ;
  2. les place sur le terrain en mètres (calage d'une image + suivi de la caméra par le décor : CameraTracker,
     project, to_brut) et sort le format radar_brut (t, jaune, noir, ballon) → jeu.py reste inchangé.
Pour l'instant le calage initial se fait avec le radar (calibrate_on_radar, pour mesurer) ; en live il
faudra le faire sans (lignes du terrain, ou 4 clics du coach).

Détection : YOLO (ultralytics, modèle « personne » + « ballon » pré-entraîné), puis l'équipe par la couleur
du maillot, calculée sur les pixels du joueur (la pelouse dans la boîte est ignorée).
Installation (une fois) :
    py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    py -m pip install ultralytics
    (statistiques anonymes d'ultralytics coupées : from ultralytics import settings; settings.update({'sync': False}))
Essai :
    python sans_radar.py video.mp4 sortie_%d.jpg 2 8 14     → images annotées aux secondes demandées

Mesures (10 nov. 2026, test.mp4, 5 images, modèle yolo11s, imgsz 2880, processeur : ~1,8 s / image) :
  - quasiment tous les joueurs présents à l'image sont trouvés, y compris au fond (25-35 px de haut) ;
  - maillots jaunes / bleu marine (« noir ») bien séparés ; l'arbitre (maillot pâle) est parfois pris pour un noir ;
  - spectateurs derrière la clôture aussi détectés → seront écartés par le passage en mètres (hors terrain) ;
  - ballon souvent trouvé, avec quelques faux.
"""
import sys
import cv2
import numpy as np

YEL = dict(h=(17, 33), s_min=110, v_min=90)          # maillot jaune (Nous)
DARK = dict(h=(102, 140), s_min=50, v_max=120)        # maillot bleu marine (Eux, « noir » sur le radar)
LIME = dict(h=(30, 50), s_min=130, v_min=170)         # arbitre (vert fluo)
GRASS = dict(h=(34, 100), s=(35, 200))               # synthétique ; 19 nov. : s ≤ 125 et h ≥ 40 rejetaient le gazon AU SOLEIL de Cascol (s 127-176, h 37-42) → joueurs au soleil écartés


def turf_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s = hsv[:, :, 0].astype(np.int16), hsv[:, :, 1].astype(np.int16)
    return (h >= GRASS['h'][0]) & (h <= GRASS['h'][1]) & (s >= GRASS['s'][0])


def team_of(frame, box):
    """'jaune', 'noir', 'arbitre' ou 'inconnu', d'après le haut du corps (pelouse exclue)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    hh = y1 - y0
    torso = frame[y0 + int(0.12 * hh):y0 + int(0.55 * hh), x0:x1]
    if torso.size == 0:
        return 'inconnu'
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    h, s, v = [hsv[:, :, i].astype(np.int16) for i in range(3)]
    grass = (h >= GRASS['h'][0]) & (h <= GRASS['h'][1]) & (s >= GRASS['s'][0]) & (s <= GRASS['s'][1])
    n = max(1, int((~grass).sum()))
    yel = ((h >= YEL['h'][0]) & (h <= YEL['h'][1]) & (s > YEL['s_min']) & (v > YEL['v_min'])).sum() / n
    lime = ((h >= LIME['h'][0]) & (h <= LIME['h'][1]) & (s > LIME['s_min']) & (v > LIME['v_min'])).sum() / n
    dark = ((((h >= DARK['h'][0]) & (h <= DARK['h'][1]) & (s > DARK['s_min']) & (v < DARK['v_max'])) | (v < 40))
            & ~grass).sum() / n
    if lime > 0.12 and lime > yel:
        return 'arbitre'
    if yel > 0.12 and yel > 0.5 * dark:
        return 'jaune'
    if dark > 0.12 and yel < 0.06:
        return 'noir'
    return 'inconnu'


def on_grass(turf, x0, y0, x1, y1):
    """Les pieds touchent du gazon (écarte les gens devant un mur, un bâtiment...)."""
    H, W = turf.shape
    fy = int(min(H - 1, y1)); w = max(6, int(x1 - x0))
    band = turf[max(0, fy - 2):min(H, fy + 8), max(0, int(x0) - w // 2):min(W, int(x1) + w // 2)]
    return band.size > 0 and band.mean() > 0.35


def detect(model, frame, imgsz=2880, conf=0.12, **kw):
    """Renvoie (joueurs, ballons) en pixels. joueur = dict(team, box, foot=(x, y) point au sol, conf).
    kw : passé à YOLO (ex. device='0', half=True pour la carte graphique)."""
    turf = turf_mask(frame)
    H, W = frame.shape[:2]
    r = model.predict(frame, imgsz=imgsz, conf=conf, classes=[0, 32], verbose=False, **kw)[0]
    players, balls = [], []
    for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        x0, y0, x1, y1 = b
        if x1 > W * 0.84 and y1 > H * 0.86:                  # logo Veo
            continue
        if int(c) == 32:
            balls.append(((x0 + x1) / 2, (y0 + y1) / 2, p))
            continue
        if not on_grass(turf, x0, y0, x1, y1):
            continue
        players.append(dict(team=team_of(frame, b), box=(x0, y0, x1, y1), foot=((x0 + x1) / 2, y1), conf=p,
                            feat=descripteur(frame, b)))
    return players, balls


def descripteur(frame, box):
    """Empreinte couleur du maillot (pour trouver les équipes par regroupement, equipes.py) : médianes et
    quartiles L*, a*, b* des pixels du haut du corps qui ne sont pas de la pelouse. None si trop peu de pixels."""
    x0, y0, x1, y1 = [int(v) for v in box]
    hh, ww = y1 - y0, x1 - x0
    torso = frame[max(0, y0 + int(0.12 * hh)):y0 + int(0.5 * hh), max(0, x0 + int(0.2 * ww)):x1 - int(0.2 * ww)]
    if torso.size < 12:
        return None
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int16)
    grass = (hsv[:, 0] >= GRASS['h'][0]) & (hsv[:, 0] <= GRASS['h'][1]) & (hsv[:, 1] >= GRASS['s'][0]) & (hsv[:, 1] <= GRASS['s'][1])
    lab = cv2.cvtColor(torso, cv2.COLOR_BGR2LAB).reshape(-1, 3)[~grass].astype(float)
    if len(lab) < 6:
        return None
    q = np.percentile(lab, [25, 50, 75], axis=0)
    return [round(float(v), 1) for v in q.ravel()]


# ---------------------------------------------------------------------------------------------------------
# Étape 2 : de l'image aux mètres. La caméra Veo tourne et zoome autour d'un point fixe : d'une image à la
# suivante, tout le décor (arbres, maisons, clôture) se déplace selon une homographie. On cale UNE image
# (G = image → terrain), puis on relie chaque image à l'image de référence par le décor (directement : le décor
# ne bouge pas, ça marche sur 100 % des images de test.mp4 ; sinon de proche en proche) : G_k = G_ref · H(k → ref).
# Mesures (10 nov. 2026, test.mp4, 161 images) : calage sur 1 image → erreur médiane des joueurs 1,22 m ;
# calage commun sur toutes les images (calibrate_joint) → 0,70 m. Ballon vu 90 %, erreur médiane 1,8 m.
# Pour le live : garder l'image de référence + son calage pour le terrain du club (même place de la Veo).

def project(G, pts):
    """Points image → terrain (mètres du radar) par l'homographie G."""
    p = cv2.perspectiveTransform(np.asarray(pts, np.float64).reshape(-1, 1, 2), G)
    return p.reshape(-1, 2)


class CameraTracker:
    """Homographie entre deux images par les points du décor (joueurs et logo masqués)."""

    def __init__(self, n=3000):
        self.orb = cv2.ORB_create(n)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def features(self, frame, boxes):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        m = np.full(g.shape, 255, np.uint8)
        H, W = g.shape
        m[int(H * 0.86):, int(W * 0.84):] = 0
        for x0, y0, x1, y1 in boxes:
            cv2.rectangle(m, (int(x0) - 6, int(y0) - 6), (int(x1) + 6, int(y1) + 6), 0, -1)
        return self.orb.detectAndCompute(g, m)

    def homography(self, fa, fb):
        """Homographie image a → image b (fa, fb = features()), ou None."""
        (ka, da), (kb, db) = fa, fb
        if da is None or db is None:
            return None
        ms = sorted(self.bf.match(da, db), key=lambda m: m.distance)[:800]
        if len(ms) < 20:
            return None
        pa = np.float32([ka[m.queryIdx].pt for m in ms])
        pb = np.float32([kb[m.trainIdx].pt for m in ms])
        H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 3.0)
        if H is None or inl.sum() < self.MIN_INLIERS or not plausible(H):
            return None
        return H

    MIN_INLIERS = 30          # 17 nov. : 15 laissait passer de faux liens (lignes du terrain dessinées n'importe où)


def plausible(H, w=1920, h=1080):
    """Un lien image → image de la Veo (rotation + zoom autour d'un point fixe) garde un quadrilatère convexe,
    devant la caméra, de taille comparable (zoom entre 1/4 et 4)."""
    c = np.float64([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]]) @ np.asarray(H, float).T
    if not (np.all(c[:, 2] > 0) or np.all(c[:, 2] < 0)):
        return False
    q = c[:, :2] / c[:, 2:]
    if not cv2.isContourConvex(np.float32(q).reshape(-1, 1, 2)):
        return False
    r = abs(cv2.contourArea(np.float32(q))) / (w * h)
    return 1 / 16 < r < 16


def match_one_to_one(P, R, tol):
    """Appariement un pour un (le plus proche d'abord) entre points P et R ; renvoie [(i, j, distance)]."""
    P, R = np.asarray(P, float), np.asarray(R, float)
    if not len(P) or not len(R):
        return []
    d = np.hypot(P[:, None, 0] - R[None, :, 0], P[:, None, 1] - R[None, :, 1])
    out, up, ur = [], set(), set()
    for k in np.argsort(d, axis=None):
        a, b = divmod(int(k), d.shape[1])
        if a in up or b in ur or d[a, b] > tol:
            continue
        up.add(a); ur.add(b); out.append((a, b, float(d[a, b])))
    return out


def calibrate_joint(G_ref, samples, iters=4, tol=3.0):
    """Calage de l'image de RÉFÉRENCE sur beaucoup d'images à la fois (installation, une fois par terrain).
    samples = [(H_k_vers_ref, joueurs_k, image_radar_k)] : chaque pied détecté est ramené dans l'image de
    référence par le décor, apparié à sa marque radar (même équipe), puis UNE homographie est ajustée.
    Mesure (test.mp4, 10 nov. 2026) : erreur médiane 1,22 m (calage sur 1 image) → 0,70 m ; en validation
    croisée (calé sur une moitié de la vidéo, mesuré sur l'autre) 0,74 et 0,83 m."""
    G = G_ref
    for _ in range(iters):
        src, dst = [], []
        for Hk, players, rad in samples:
            for team in ('jaune', 'noir'):
                P = [p['foot'] for p in players if p['team'] == team]
                if not P or not rad.get(team):
                    continue
                Pref = project(Hk, P)
                for a, b, _ in match_one_to_one(project(G, Pref), rad[team], tol):
                    src.append(Pref[a]); dst.append(rad[team][b])
        if len(src) < 8:
            break
        G2, _ = cv2.findHomography(np.float32(src), np.float32(dst), cv2.RANSAC, 1.5)
        if G2 is None:
            break
        G = G2
    return G


def on_pitch_m(q, margin=3.0):
    return -margin <= q[0] <= 105 + margin and -margin <= q[1] <= 68 + margin


def to_brut(t, players, balls, G):
    """Une image au format radar_brut (jaune / noir / ballon en mètres), hors terrain écarté."""
    pos = {'jaune': [], 'noir': []}
    for p in players:
        if p['team'] in pos:
            q = project(G, [p['foot']])[0]
            if on_pitch_m(q):
                pos[p['team']].append((round(float(q[0]), 2), round(float(q[1]), 2)))
    ball = None
    if balls:
        b = max(balls, key=lambda x: x[2])
        q = project(G, [(b[0], b[1])])[0]
        if on_pitch_m(q):
            ball = (round(float(q[0]), 2), round(float(q[1]), 2))
    return dict(t=round(t, 2), jaune=pos['jaune'], noir=pos['noir'], ballon=ball)


def ball_candidates(balls, G, margin=1.0):
    """Tous les ballons YOLO d'une image, en mètres : [(x, y, confiance)] (hors terrain écarté)."""
    out = []
    for x, y, conf in balls:
        q = project(G, [(x, y)])[0]
        if on_pitch_m(q, margin):
            out.append((float(q[0]), float(q[1]), float(conf)))
    return out


def ball_path(cands, times, miss=2.5, vmax=30.0, w_jump=0.15, w_conf=3.0):
    """Le VRAI ballon parmi les candidats (chaussettes, plots, lignes donnent de faux ballons) : chemin le plus
    cohérent sur toute la séquence (Viterbi). Coût = sauts au-delà de vmax·dt + manque de confiance ;
    « pas vu » coûte `miss`. En live : à faire sur une fenêtre glissante de 1-2 s (petit retard).
    Mesure (test.mp4) : faux ballons à plus de 10 m 20 % → 13 %, erreur médiane 1,6 → 1,5 m, vu 83 % ;
    note sur les 10 actions 16 → 28 (passes réussies 47 → 59)."""
    import math
    T = len(cands)
    if not T:
        return []
    states = [list(c) + [None] for c in cands]
    em = lambda s: w_conf * (1 - s[2]) if s else miss          # noqa: E731
    cost = [[em(s) for s in states[0]]]
    back = [[-1] * len(states[0])]
    for k in range(1, T):
        dt = times[k] - times[k - 1]
        row, brow = [], []
        for s in states[k]:
            best = (float('inf'), -1)
            for j, p in enumerate(states[k - 1]):
                tr = 0.0 if (s is None or p is None) else w_jump * max(0.0, math.dist(s[:2], p[:2]) - vmax * dt - 2.0) ** 1.5
                if cost[k - 1][j] + tr < best[0]:
                    best = (cost[k - 1][j] + tr, j)
            row.append(best[0] + em(s)); brow.append(best[1])
        cost.append(row); back.append(brow)
    j = min(range(len(cost[-1])), key=lambda i: cost[-1][i])
    path = [None] * T
    for k in range(T - 1, -1, -1):
        s = states[k][j]
        path[k] = (round(s[0], 2), round(s[1], 2)) if s else None
        j = back[k][j]
    return path


# Nettoyage des positions « vision » avant jeu.py (qui suppose un ballon propre, comme celui du radar Veo).
CLEAN = dict(
    vmax=30.0,       # m/s : vitesse maximale du ballon (frappe) ; au-delà, c'est un faux ballon
    tol=3.0,         # m : marge ajoutée (erreur de position)
    reacq=3,         # images : après autant de rejets cohérents entre eux, on reprend le nouveau ballon
    gap=1.0,         # s : trous du ballon comblés jusqu'à ça
    smooth=0,        # lissage 1-2-1 du ballon (1 = oui) : testé, moins bon (passes réussies 46 au lieu de 57)
    margin=1.0,      # m : hors du terrain au-delà → spectateur, banc
    per_team=11,     # joueurs par équipe au plus
)


def clean_brut(frames, cfg=None):
    """Ballon : rejette les sauts impossibles, comble les petits trous, lisse. Joueurs : hors terrain écartés,
    11 par équipe au plus (on enlève les plus proches du bord). Renvoie une nouvelle liste."""
    import math
    c = dict(CLEAN, **(cfg or {}))
    out = [dict(f) for f in frames]
    # joueurs
    for f in out:
        for team in ('jaune', 'noir'):
            pts = [p for p in f.get(team, []) if -c['margin'] <= p[0] <= 105 + c['margin'] and -c['margin'] <= p[1] <= 68 + c['margin']]
            if len(pts) > c['per_team']:
                pts.sort(key=lambda p: -min(p[0], 105 - p[0], p[1], 68 - p[1]))
                pts = pts[:c['per_team']]
            f[team] = pts
    # ballon : rejet des sauts
    last, pend = None, []                                    # pend = [(image, ballon rejeté)]
    for i, f in enumerate(out):
        b = f.get('ballon')
        if b is None:
            continue
        if last is None or math.dist(b, out[last]['ballon']) <= c['vmax'] * (f['t'] - out[last]['t']) + c['tol']:
            last, pend = i, []
            continue
        pend.append((i, b))
        f['ballon'] = None
        if len(pend) >= c['reacq'] and all(
                math.dist(pa, pb) <= c['vmax'] * (out[ib]['t'] - out[ia]['t']) + c['tol']
                for (ia, pa), (ib, pb) in zip(pend, pend[1:])):
            for j, pb in pend:                               # le ballon est vraiment là-bas : on le reprend
                out[j]['ballon'] = pb
            last, pend = i, []
    # petits trous comblés
    known = [i for i, f in enumerate(out) if f.get('ballon')]
    for a, b in zip(known, known[1:]):
        ta, tb = out[a]['t'], out[b]['t']
        if b - a > 1 and tb - ta <= c['gap']:
            (xa, ya), (xb, yb) = out[a]['ballon'], out[b]['ballon']
            for i in range(a + 1, b):
                r = (out[i]['t'] - ta) / (tb - ta)
                out[i]['ballon'] = (xa + r * (xb - xa), ya + r * (yb - ya))
    # lissage 1-2-1 (seulement entre images où le ballon est vu)
    if c['smooth']:
        raw = [f.get('ballon') for f in out]
        for i in range(1, len(out) - 1):
            a, b, d = raw[i - 1], raw[i], raw[i + 1]
            if a and b and d:
                out[i]['ballon'] = ((a[0] + 2 * b[0] + d[0]) / 4, (a[1] + 2 * b[1] + d[1]) / 4)
    for f in out:
        if f.get('ballon'):
            f['ballon'] = (round(f['ballon'][0], 2), round(f['ballon'][1], 2))
    return out


def calibrate_on_radar(players, balls, radar_frame, iters=150000, seed=0):
    """Calage G sur une image À L'AIDE DU RADAR (pour mesurer, pas pour le live) : RANSAC sur des
    correspondances joueur ↔ marque radar de la même équipe, ancré sur le ballon quand il est vu."""
    rng = np.random.default_rng(seed)
    det = [(p['foot'], p['team']) for p in players if p['team'] in ('jaune', 'noir')]
    byteam = {t: [d for d, tt in det if tt == t] for t in ('jaune', 'noir')}
    rad = {t: radar_frame.get(t) or [] for t in ('jaune', 'noir')}
    anchor = None
    if balls and radar_frame.get('ballon'):
        b = max(balls, key=lambda x: x[2])
        anchor = ((b[0], b[1]), tuple(radar_frame['ballon']))

    def matched(G, tol=2.0):
        errs = []
        for team in ('jaune', 'noir'):
            if not byteam[team] or not rad[team]:
                continue
            P = project(G, byteam[team]); R = np.array(rad[team])
            d = np.hypot(P[:, None, 0] - R[None, :, 0], P[:, None, 1] - R[None, :, 1])
            up, ur = set(), set()
            for k in np.argsort(d, axis=None):             # un pour un, le plus proche d'abord
                a, c = divmod(int(k), d.shape[1])
                if a in up or c in ur:
                    continue
                up.add(a); ur.add(c); errs.append(d[a, c])
        e = np.array(errs) if errs else np.array([99.0])
        return int((e < tol).sum()), float(np.median(e[e < tol])) if (e < tol).any() else 99.0

    best = (0, 99.0, None)
    for _ in range(iters):
        src, dst = ([anchor[0]], [anchor[1]]) if anchor else ([], [])
        while len(src) < 4:
            team = 'jaune' if rng.random() < 0.5 else 'noir'
            if not byteam[team] or not rad[team]:
                team = 'noir' if team == 'jaune' else 'jaune'
                if not byteam[team] or not rad[team]:
                    return None
            src.append(byteam[team][rng.integers(len(byteam[team]))]); dst.append(rad[team][rng.integers(len(rad[team]))])
        src, dst = np.float32(src), np.float32(dst)
        if len({tuple(s) for s in src.tolist()}) < 4 or len({tuple(d) for d in dst.tolist()}) < 4:
            continue
        G = cv2.getPerspectiveTransform(src, dst)
        if not np.isfinite(G).all():
            continue
        n, med = matched(G)
        if n > best[0] or (n == best[0] and med < best[1]):
            best = (n, med, G)
    return best[2]


def main():
    from ultralytics import YOLO
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    model = YOLO('yolo11s.pt')
    cap = cv2.VideoCapture(sys.argv[1])
    col = dict(jaune=(0, 220, 255), noir=(255, 0, 255), arbitre=(0, 255, 0), inconnu=(160, 160, 160))
    for t in [float(a) for a in sys.argv[3:]]:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        P, B = detect(model, fr)
        print('t=%.1f s  %s  ballon %d' % (t, {k: sum(p['team'] == k for p in P) for k in col}, len(B)))
        for p in P:
            x0, y0, x1, y1 = [int(v) for v in p['box']]
            cv2.rectangle(fr, (x0, y0), (x1, y1), col[p['team']], 2)
        for x, y, _ in B:
            cv2.circle(fr, (int(x), int(y)), 14, (0, 0, 255), 3)
        cv2.imwrite(sys.argv[2] % int(t), fr)


if __name__ == '__main__':
    main()
