"""SUIVI d'un match entier (sans radar) : détection → pistes des joueurs et du ballon → stats et quadrillage.

    py suivi.py detecter VIDEO --debut 300 --fin 2700 --fps 5 --sortie references/cascol/mt1
        YOLO + décor sur toute la période, écrit au fur et à mesure (detections.jsonl) : reprend où il s'était
        arrêté si on le relance.
    py suivi.py pistes references/cascol/mt1 [--terrain references/terrain_club]
        pistes des joueurs (même joueur d'une image à l'autre, en mètres) + chemin du ballon → radar_brut.json
    py suivi.py stats references/cascol/mt1 [--veo references/cascol/veo_mt1.json]
        possession, passes, frappes (règles de jeu.py), quadrillage du terrain, cartes de chaleur → rapport.html

Pourquoi des pistes : la couleur du maillot se lit mal à l'ombre ou de dos (« inconnu ») ; un joueur suivi garde
l'équipe que la MAJORITÉ de ses images lui donnent. Les pistes se font EN MÈTRES (la caméra Veo tourne et zoome :
dans l'image, tout bouge). Les arbitres (vert) sont suivis puis écartés.

Limites (à dire au coach) : la caméra ne montre qu'une partie du terrain, les cartes des joueurs penchent vers
là où elle regarde ; la carte du ballon et la possession par zone sont plus sûres.
Sorties = données de match : toujours dans ia/references/ (ignoré par git), jamais dans le dépôt public.
"""
import argparse
import json
import math
import os
import sys
import time
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jeu                  # noqa: E402
import sans_radar as sr     # noqa: E402

EQUIPES = ('jaune', 'noir')

CFG = dict(
    marge=3.0,        # m : détection gardée jusqu'à ça hors du terrain
    porte=2.5,        # m : distance acceptée entre la position prévue et la détection (+ vmax·dt)
    vmax=8.0,         # m/s : vitesse maximale d'un joueur (sprint U14 ~ 7-8 m/s)
    equipe_pen=3.0,   # m : pénalité si la détection et la piste ont deux équipes connues différentes
    age=2.0,          # s : une piste sans détection depuis plus longtemps est close
    trou=1.0,         # s : trous comblés (interpolation) dans une piste jusqu'à ça
    min_images=3,     # images détectées au minimum pour qu'une piste compte
)


# --------------------------------------------------------------------------------------------- détection
def detecter(video, debut, fin, fps, sortie, terrain='references/terrain_club', imgsz=2880, model_name='yolo11s.pt'):
    """YOLO + lien au décor, écrit image par image dans <sortie>/detections.jsonl (reprise possible)."""
    import cv2
    from ultralytics import YOLO
    import banc
    os.makedirs(sortie, exist_ok=True)
    path = os.path.join(sortie, 'detections.jsonl')
    deja = None
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                try:
                    deja = json.loads(line)['t']
                except ValueError:
                    break
    json.dump(dict(video=video, debut=debut, fin=fin, fps=fps, terrain=terrain, imgsz=imgsz, model=model_name,
                   H_radar=True),                          # H de chaque image = image → mètres (G déjà appliqué)
              open(os.path.join(sortie, 'source.json'), 'w', encoding='utf-8'), indent=1)
    T, ref_img = banc.charger_terrain(terrain)
    model = YOLO(os.path.join(HERE, model_name))
    tr = sr.CameraTracker()
    refs = references(tr, T, ref_img, terrain)
    cap = cv2.VideoCapture(video)
    vfps = cap.get(cv2.CAP_PROP_FPS)
    pas = max(1, int(round(vfps / fps)))
    k_debut = int(round(debut * vfps))
    k0 = k_debut
    if deja is not None:                                       # reprise : image suivante sur la même grille
        k0 = k_debut + (int(round(deja * vfps)) - k_debut) // pas * pas + pas
    k_fin = int(fin * vfps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, k0)
    k, n, t0 = k0, 0, time.time()
    prev = None                                                # dernière image reliée : (features, H)
    with open(path, 'a', encoding='utf-8') as out:
        while k <= k_fin:
            ok, fr = cap.read()
            if not ok:
                break
            P, B = sr.detect(model, fr, imgsz=imgsz, device=0, half=True)
            fe = tr.features(fr, [p['box'] for p in P])
            H = relier(tr, fe, refs)
            if H is None and prev is not None:
                Hp = tr.homography(fe, prev[0])
                H = prev[1] @ Hp if Hp is not None else None
            if H is not None:
                prev = (fe, H)
            t = k / vfps
            out.write(json.dumps(dict(
                t=round(t, 3),
                players=[dict(team=p['team'], foot=[round(v, 1) for v in p['foot']], conf=round(p['conf'], 3),
                              box=[round(v, 1) for v in p['box']], feat=p['feat']) for p in P],
                balls=[[round(b[0], 1), round(b[1], 1), round(b[2], 3)] for b in B],
                H=H.tolist() if H is not None else None)) + '\n')
            n += 1
            if n % 25 == 0:
                out.flush()
                v = n / (time.time() - t0)
                print('\r  %d / %d s vidéo  (%.1f images / s, reste ~%.0f min)   ' % (
                    int(t), int(fin), v, (k_fin - k) / pas / max(v, 1e-6) / 60), end='', flush=True)
            for _ in range(pas - 1):                           # images sautées : lecture sans décodage
                cap.grab()
            k += pas
    print()


def references(tr, T, ref_img, terrain):
    """Images connues du décor, chacune avec M = image → repère radar (mètres, 105 x 68) :
      - terrain.json "vues": [{"image": "vue_415.png", "G": 3x3}] : calage PAR VUE (chaque vue calée sur ses propres
        repères). Recommandé : relier une vue de but à une vue du centre fait extrapoler l'homographie loin hors de
        l'image, et quelques pixels d'erreur y deviennent plusieurs mètres (Cascol, 19 nov. 2026 : 10 à 110 px d'écart
        selon le chemin pour la même image ; un calage unique sur 16 repères gardait 1,2 m d'erreur moyenne) ;
      - sinon l'image de référence (G) + "ancres": [{"image": ..., "H": 3x3 ancre → référence}]."""
    import cv2
    d = terrain if os.path.isabs(terrain) else os.path.join(HERE, terrain)
    if T.get('vues'):
        refs = []
        for v in T['vues']:
            img = cv2.imread(os.path.join(d, v['image']))
            if img is None:
                raise SystemExit('Image de vue introuvable : ' + v['image'])
            refs.append((tr.features(img, []), np.array(v['G'])))
        return refs
    G = np.array(T['G'])
    refs = [(tr.features(ref_img, []), G)]
    for a in T.get('ancres', []):
        img = cv2.imread(os.path.join(d, a['image']))
        if img is not None:
            refs.append((tr.features(img, []), G @ np.array(a['H'])))
    return refs


def lien(tr, fa, fb):
    """Comme CameraTracker.homography (mêmes garde-fous), mais renvoie aussi le nombre de points d'accord."""
    import cv2
    (ka, da), (kb, db) = fa, fb
    if da is None or db is None:
        return None, 0
    ms = sorted(tr.bf.match(da, db), key=lambda m: m.distance)[:800]
    if len(ms) < 20:
        return None, 0
    pa = np.float32([ka[m.queryIdx].pt for m in ms])
    pb = np.float32([kb[m.trainIdx].pt for m in ms])
    H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 3.0)
    if H is None or inl.sum() < tr.MIN_INLIERS or not sr.plausible(H):
        return None, 0
    return H, int(inl.sum())


def relier(tr, fe, refs, assez=120):
    """Image → repère radar par la vue connue qui lui ressemble le plus (le plus de points d'accord), sinon None.
    La vue qui a servi la dernière fois est essayée d'abord : si elle donne au moins `assez` points d'accord, on
    s'arrête là (5 vues essayées à chaque image : 0,5 s / image, 19 nov. 2026)."""
    best = (None, 0, None)
    for i in ([relier.derniere] if relier.derniere is not None and relier.derniere < len(refs) else []) + list(range(len(refs))):
        if i == best[2]:
            continue
        fr, M = refs[i]
        h, n = lien(tr, fe, fr)
        if h is not None and n > best[1]:
            best = (M @ h, n, i)
            if i == relier.derniere and n >= assez:
                break
    relier.derniere = best[2] if best[2] is not None else relier.derniere
    return best[0]


relier.derniere = None


def charger(sortie):
    out = []
    with open(os.path.join(sortie, 'detections.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                break                                          # dernière ligne coupée (arrêt brutal)
    return out


# --------------------------------------------------------------------------------------------- pistes
def en_metres(G, frames, marge=CFG['marge']):
    """[(t, [dict(x, y, team, conf)])] pour les images reliées au décor."""
    res = []
    for f in frames:
        if f.get('H') is None:
            continue
        Gk = G @ np.array(f['H'])
        D = []
        if f['players']:
            q = sr.project(Gk, [p['foot'] for p in f['players']])
            for p, (x, y) in zip(f['players'], q):
                if -marge <= x <= 105 + marge and -marge <= y <= 68 + marge:
                    D.append(dict(x=float(x), y=float(y), team=p['team'], conf=p.get('conf', 1.0)))
        res.append((f['t'], D))
    return res


def suivre(dets, cfg=None):
    """Pistes : liste de dict(id, team, votes, pts=[(i, t, x, y, team_vue)]) ; i = rang de l'image dans dets.
    Association un pour un (la plus proche d'abord) entre positions prévues (vitesse constante) et détections."""
    c = dict(CFG, **(cfg or {}))
    pistes, actives = [], []
    for i, (t, D) in enumerate(dets):
        actives = [p for p in actives if t - p['t'] <= c['age']]
        cand = []
        for a, p in enumerate(actives):
            dt = t - p['t']
            px, py = p['x'] + p['vx'] * dt, p['y'] + p['vy'] * dt
            porte = c['porte'] + c['vmax'] * dt
            maj = p['votes'].most_common(1)[0][0] if p['votes'] else None
            for b, d in enumerate(D):
                e = math.hypot(d['x'] - px, d['y'] - py)
                if e > porte:
                    continue
                if maj and d['team'] != 'inconnu' and d['team'] != maj:
                    e += c['equipe_pen']
                cand.append((e, a, b))
        cand.sort()
        pa, pb = set(), set()
        for e, a, b in cand:
            if a in pa or b in pb:
                continue
            pa.add(a); pb.add(b)
            p, d = actives[a], D[b]
            dt = max(1e-3, t - p['t'])
            vx, vy = (d['x'] - p['x']) / dt, (d['y'] - p['y']) / dt
            s = math.hypot(vx, vy)
            if s > c['vmax']:
                vx, vy = vx * c['vmax'] / s, vy * c['vmax'] / s
            p['vx'], p['vy'] = 0.5 * p['vx'] + 0.5 * vx, 0.5 * p['vy'] + 0.5 * vy
            p.update(x=d['x'], y=d['y'], t=t)
            p['pts'].append((i, t, d['x'], d['y'], d['team']))
            if d['team'] != 'inconnu':
                p['votes'][d['team']] += 1
        for b, d in enumerate(D):
            if b in pb:
                continue
            p = dict(id=len(pistes), x=d['x'], y=d['y'], t=t, vx=0.0, vy=0.0, votes=Counter(),
                     pts=[(i, t, d['x'], d['y'], d['team'])])
            if d['team'] != 'inconnu':
                p['votes'][d['team']] += 1
            pistes.append(p)
            actives.append(p)
    out = []
    for p in pistes:
        if len(p['pts']) < c['min_images']:
            continue
        v = p['votes']
        team = v.most_common(1)[0][0] if v else 'inconnu'
        out.append(dict(id=p['id'], team=team, votes=dict(v), pts=p['pts']))
    return out


def positions(pistes, n, cfg=None):
    """Par image : {équipe: [(x, y)]} ; position lissée (moyenne 1-2-1 des voisines de la piste), trous de moins
    de `trou` s comblés en ligne droite."""
    c = dict(CFG, **(cfg or {}))
    per = [{'jaune': [], 'noir': []} for _ in range(n)]
    for p in pistes:
        if p['team'] not in EQUIPES:
            continue
        pts = p['pts']
        xy = np.array([(q[2], q[3]) for q in pts])
        sm = xy.copy()
        if len(xy) >= 3:
            sm[1:-1] = (xy[:-2] + 2 * xy[1:-1] + xy[2:]) / 4
        for k, q in enumerate(pts):
            per[q[0]][p['team']].append((round(float(sm[k, 0]), 2), round(float(sm[k, 1]), 2)))
            if k + 1 < len(pts):
                i1, t1 = pts[k + 1][0], pts[k + 1][1]
                if i1 - q[0] > 1 and t1 - q[1] <= c['trou']:
                    for i in range(q[0] + 1, i1):
                        r = (i - q[0]) / (i1 - q[0])
                        x = sm[k, 0] + r * (sm[k + 1, 0] - sm[k, 0])
                        y = sm[k, 1] + r * (sm[k + 1, 1] - sm[k, 1])
                        per[i][p['team']].append((round(float(x), 2), round(float(y), 2)))
    return per


def reetiqueter(frames, G, pistes):
    """Copie des images (format cache du banc) où chaque joueur prend l'équipe de sa piste (pour mesurer)."""
    rel = [f for f in frames if f.get('H') is not None]
    equipe = {}
    for p in pistes:
        for q in p['pts']:
            equipe[(q[0], round(q[2], 3), round(q[3], 3))] = p['team']
    out = []
    for i, f in enumerate(rel):
        Gk = G @ np.array(f['H'])
        P = []
        if f['players']:
            q = sr.project(Gk, [p['foot'] for p in f['players']])
            for p, (x, y) in zip(f['players'], q):
                P.append(dict(p, team=equipe.get((i, round(float(x), 3), round(float(y), 3)), p['team'])))
        out.append(dict(f, players=P))
    return out


def controle(pistes, cfg=None):
    """Mesures SANS vérité de la qualité des pistes."""
    c = dict(CFG, **(cfg or {}))
    pas = vite = votes = contre = 0
    durees = []
    for p in pistes:
        pts = p['pts']
        durees.append(pts[-1][1] - pts[0][1])
        for a, b in zip(pts, pts[1:]):
            pas += 1
            if math.hypot(b[2] - a[2], b[3] - a[3]) / max(1e-3, b[1] - a[1]) > c['vmax'] + 1:
                vite += 1
        for k, v in p['votes'].items():
            votes += v
            if k != p['team']:
                contre += v
    return dict(pistes=len(pistes), duree_med_s=round(float(np.median(durees)), 1) if durees else 0,
                trop_vite=round(vite / max(1, pas), 3), equipe_contredite=round(contre / max(1, votes), 3),
                sans_equipe=round(sum(1 for p in pistes if p['team'] == 'inconnu') / max(1, len(pistes)), 3))


def ballon(G, frames):
    """Chemin du ballon (sr.ball_path, Viterbi) sur les images reliées."""
    rel = [f for f in frames if f.get('H') is not None]
    cands = [sr.ball_candidates(f['balls'], G @ np.array(f['H'])) for f in rel]
    return sr.ball_path(cands, [f['t'] for f in rel])


def brut_suivi(G, frames, path, cfg=None):
    """Comme mesure_vision.vision_brut, mais les joueurs passent par les pistes. Renvoie (brut, pistes).
    path = chemin du ballon sur les images reliées (même ordre)."""
    dets = en_metres(G, frames)
    pistes = suivre(dets, cfg)
    per = positions(pistes, len(dets), cfg)
    brut = [dict(t=round(t, 2), jaune=per[i]['jaune'], noir=per[i]['noir'], ballon=path[i] if i < len(path) else None)
            for i, (t, _) in enumerate(dets)]
    return sr.clean_brut(brut), pistes


# --------------------------------------------------------------------------------------------- stats
TIERS = ('défensif', 'milieu', 'offensif')
COULOIRS = ('gauche', 'axe', 'droit')          # vus dans le sens de l'attaque de Nous


def zone(p):
    """(tiers, couloir) d'un point du repère appli (Nous attaque vers la droite ; y = 0 = côté gauche de Nous)."""
    x, y = p
    tx = max(0, min(2, int(x // 35)))
    cy = 0 if y < 68 / 3 else (1 if y < 2 * 68 / 3 else 2)
    return tx, cy


def possession(frames, cfg=jeu.CFG, dt_max=1.0):
    """Temps de possession : le ballon appartient à la dernière équipe qui l'a eu (porteur net, jeu.holder)
    tant que l'autre ne l'a pas. Renvoie (N %, E %, porteur par image)."""
    cur, tN, tE = None, 0.0, 0.0
    qui = []
    for k, f in enumerate(frames):
        h = jeu.holder(f, cfg)
        if h in ('N', 'E'):
            cur = h
        qui.append(cur)
        if k and cur:
            dt = min(dt_max, f['t'] - frames[k - 1]['t'])
            if cur == 'N':
                tN += dt
            else:
                tE += dt
    tot = tN + tE
    return (round(100 * tN / tot, 1) if tot else None, round(100 * tE / tot, 1) if tot else None, qui)


def stats(brut, nous='jaune', veo=None, half=1):
    frames, right = jeu.normalize(brut, nous)
    frames = jeu.fill_ball(frames)
    pN, pE, qui = possession(frames)
    ev = jeu.actions(frames, half=half)
    res = jeu.summary(frames, ev)
    res['sens_nous'] = 'droite' if right else 'gauche'
    res['possession'] = dict(N=pN, E=pE)
    grille = np.zeros((3, 3)); gN = np.zeros((3, 3))
    for f, q in zip(frames, qui):
        b = f['ballon']
        if b and 0 <= b[0] <= 105 and 0 <= b[1] <= 68:
            tx, cy = zone(b)
            grille[cy, tx] += 1
            if q == 'N':
                gN[cy, tx] += 1
    tot = grille.sum()
    res['ballon_zones_pct'] = {'%s / %s' % (TIERS[tx], COULOIRS[cy]): round(100 * grille[cy, tx] / tot, 1)
                               for tx in range(3) for cy in range(3)} if tot else {}
    res['ballon_tiers_pct'] = {TIERS[tx]: round(100 * grille[:, tx].sum() / tot, 1) for tx in range(3)} if tot else {}
    res['possession_nous_par_tiers_pct'] = {TIERS[tx]: (round(100 * gN[:, tx].sum() / grille[:, tx].sum(), 1)
                                                        if grille[:, tx].sum() else None) for tx in range(3)}
    res['joueurs_vus_med'] = dict(N=float(np.median([len(f['N']) for f in frames])),
                                  E=float(np.median([len(f['E']) for f in frames])))
    if veo:
        A = res['actions']
        res['comparaison_veo'] = [
            ('possession Nous %', veo['nous']['possession_pct'], pN),
            ('passes réussies Nous', veo['nous']['passes_reussies'], A['N']['passes_reussies']),
            ('passes ratées Nous', veo['nous']['passes'] - veo['nous']['passes_reussies'], A['N']['passes_ratees']),
            ('passes réussies Eux', veo['eux']['passes_reussies'], A['E']['passes_reussies']),
            ('passes ratées Eux', veo['eux']['passes'] - veo['eux']['passes_reussies'], A['E']['passes_ratees']),
            ('tentatives Nous', veo['nous']['tentatives'], A['N']['frappes']),
            ('tentatives Eux', veo['eux']['tentatives'], A['E']['frappes']),
        ]
    return res, frames, ev


def cartes(frames, dossier, cell=5.0):
    """Cartes de chaleur (ballon, Nous, Eux) en PNG, repère appli (Nous attaque vers la droite)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    nx, ny = int(105 / cell), int(68 / cell)

    def grille(pts):
        g = np.zeros((ny, nx))
        for x, y in pts:
            if 0 <= x < 105 and 0 <= y < 68:
                g[min(ny - 1, int(y / cell)), min(nx - 1, int(x / cell))] += 1
        return g / max(1, g.sum()) * 100
    sets = [('ballon', [f['ballon'] for f in frames if f['ballon']], 'Ballon'),
            ('nous', [p for f in frames for p in f['N']], 'Nous (jaune), positions vues'),
            ('eux', [p for f in frames for p in f['E']], 'Eux (noir), positions vues')]
    noms = []
    for nom, pts, titre in sets:
        fig, ax = plt.subplots(figsize=(7.5, 5))
        ax.imshow(grille(pts), extent=(0, 105, 68, 0), cmap='YlOrRd', interpolation='bilinear')
        for x in (35, 70):
            ax.axvline(x, color='k', lw=0.6, ls='--')
        for y in (68 / 3, 2 * 68 / 3):
            ax.axhline(y, color='k', lw=0.6, ls='--')
        ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], 'k', lw=1.2)
        ax.plot([52.5, 52.5], [0, 68], 'k', lw=1)
        ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color='k', lw=1))
        for x0, s in ((0, 1), (105, -1)):
            ax.plot([x0, x0 + s * 16.5, x0 + s * 16.5, x0], [13.84, 13.84, 54.16, 54.16], 'k', lw=1)
        ax.set_title(titre + '  (attaque de Nous →)')
        ax.set_xticks([]); ax.set_yticks([])
        f = os.path.join(dossier, 'carte_%s.png' % nom)
        fig.savefig(f, dpi=110, bbox_inches='tight')
        plt.close(fig)
        noms.append(os.path.basename(f))
    return noms


def rapport(dossier, res, images, ctrl):
    def tab(rows, head):
        return '<table><tr>%s</tr>%s</table>' % (''.join('<th>%s</th>' % h for h in head), ''.join(
            '<tr>%s</tr>' % ''.join('<td>%s</td>' % ('–' if v is None else v) for v in r) for r in rows))
    A = res['actions']
    h = ['<!doctype html><meta charset="utf-8"><title>Suivi du match</title><style>body{font-family:sans-serif;'
         'max-width:900px;margin:auto;padding:16px}table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;'
         'padding:4px 8px;text-align:right}th{background:#eee}img{max-width:100%}</style>',
         '<h1>Suivi automatique – %s</h1>' % os.path.basename(os.path.abspath(dossier)),
         '<p>%d images, %.0f min, ballon vu %d %% des images, joueurs vus par image (médiane) : Nous %g, Eux %g. '
         'Nous attaque vers la %s du radar.</p>' % (res['images'], res['duree_s'] / 60, res['ballon_vu_pct'],
                                                   res['joueurs_vus_med']['N'], res['joueurs_vus_med']['E'], res['sens_nous'])]
    if res.get('comparaison_veo'):
        h.append('<h2>Comparaison avec Veo</h2>' + tab(res['comparaison_veo'], ['', 'Veo', 'IA']))
    h.append('<h2>Possession et actions (IA)</h2>' + tab([
        ('possession %', res['possession']['N'], res['possession']['E']),
        ('passes réussies', A['N']['passes_reussies'], A['E']['passes_reussies']),
        ('passes ratées', A['N']['passes_ratees'], A['E']['passes_ratees']),
        ('passes de déséquilibre', A['N']['passes_deseq'], A['E']['passes_deseq']),
        ('conduites de déséquilibre', A['N']['conduites_deseq'], A['E']['conduites_deseq']),
        ('frappes', A['N']['frappes'], A['E']['frappes'])], ['', 'Nous', 'Eux']))
    h.append('<p>Duels (Nous) : gagnés %d, perdus %d.</p>' % (A['duels']['gagnes'], A['duels']['perdus']))
    h.append('<h2>Quadrillage : où est le ballon (%% du temps)</h2>' + tab(
        [(c,) + tuple(res['ballon_zones_pct'].get('%s / %s' % (t, c)) for t in TIERS) for c in COULOIRS],
        ['couloir'] + list(TIERS)))
    h.append('<p>Possession de Nous par tiers : %s</p>' % ', '.join(
        '%s %s %%' % (k, v) for k, v in res['possession_nous_par_tiers_pct'].items()))
    for im in images:
        h.append('<img src="%s">' % im)
    h.append('<h2>Contrôle des pistes (sans vérité)</h2>' + tab([(k, v) for k, v in ctrl.items()], ['mesure', 'valeur']))
    h.append('<p><small>Limites : la caméra ne montre qu\'une partie du terrain (les cartes des joueurs penchent vers '
             'là où elle regarde). Passes et frappes : règles de jeu.py, approximatives.</small></p>')
    open(os.path.join(dossier, 'rapport.html'), 'w', encoding='utf-8').write('\n'.join(h))


# --------------------------------------------------------------------------------------------- commande
def main():
    ap = argparse.ArgumentParser(description='Suivi d\'un match entier sans radar.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('detecter')
    d.add_argument('video'); d.add_argument('--debut', type=float, required=True); d.add_argument('--fin', type=float, required=True)
    d.add_argument('--fps', type=float, default=5); d.add_argument('--sortie', required=True)
    d.add_argument('--terrain', default='references/terrain_club')
    p = sub.add_parser('pistes')
    p.add_argument('sortie'); p.add_argument('--terrain', default=None, help='anciennes détections (sans H_radar) seulement')
    s = sub.add_parser('stats')
    s.add_argument('sortie'); s.add_argument('--veo'); s.add_argument('--nous', default='jaune')
    a = ap.parse_args()
    os.chdir(HERE)
    if a.cmd == 'detecter':
        detecter(a.video, a.debut, a.fin, a.fps, a.sortie, a.terrain)
    elif a.cmd == 'pistes':
        import banc
        src = json.load(open(os.path.join(a.sortie, 'source.json'), encoding='utf-8'))
        if src.get('H_radar'):
            G = np.eye(3)                                      # les H des images vont déjà jusqu'aux mètres
        else:
            T, _ = banc.charger_terrain(a.terrain or src['terrain'])
            G = np.array(T['G'])
        frames = charger(a.sortie)
        path = ballon(G, frames)
        brut, pistes = brut_suivi(G, frames, path)
        json.dump(brut, open(os.path.join(a.sortie, 'radar_brut.json'), 'w', encoding='utf-8'))
        ctrl = controle(pistes)
        ctrl['images_reliees'] = round(len(brut) / max(1, len(frames)), 3)
        json.dump(ctrl, open(os.path.join(a.sortie, 'controle.json'), 'w', encoding='utf-8'), indent=1)
        print(json.dumps(ctrl, ensure_ascii=False))
    else:
        brut = json.load(open(os.path.join(a.sortie, 'radar_brut.json'), encoding='utf-8'))
        brut = [dict(f, jaune=[tuple(p) for p in f['jaune']], noir=[tuple(p) for p in f['noir']],
                     ballon=tuple(f['ballon']) if f.get('ballon') else None) for f in brut]
        veo = json.load(open(a.veo, encoding='utf-8')) if a.veo else None
        res, frames, ev = stats(brut, a.nous, veo)
        json.dump(res, open(os.path.join(a.sortie, 'stats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(ev, open(os.path.join(a.sortie, 'actions_ia.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        cp = os.path.join(a.sortie, 'controle.json')
        ctrl = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
        rapport(a.sortie, res, cartes(frames, a.sortie), ctrl)
        print(json.dumps({k: res[k] for k in ('possession', 'actions', 'ballon_tiers_pct', 'comparaison_veo') if k in res},
                         ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
