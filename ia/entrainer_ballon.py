"""ENTRAÎNER un détecteur de ballon sur NOS vidéos, sans étiquettes faites à la main (auto-étiquetage).

    py entrainer_ballon.py donnees references/cascol/v2/mt1_a references/cascol/v2/mt1_b2 ... --sortie references/ballon_ds
    py entrainer_ballon.py entrainer references/ballon_ds --epoques 30
    → modeles/ballon_club.pt (hors dépôt)

Exemples POSITIFS : ballons dont on est sûr = choisis par le chemin cohérent (sans_radar.ball_path), confiance YOLO ≥ seuil
et confirmés par les images voisines. Taille de la boîte : ~0,14 x la hauteur médiane des joueurs proches (ballon 22 cm,
joueur U14 ~1,6 m).
Exemples NÉGATIFS (tuiles sans ballon) : faux ballons FIXES (vus au même endroit du terrain pendant plus de 90 s : marques,
plots, sacs, ballons de réserve) sur des images où aucun ballon sûr n'est trouvé.
Tuiles de 640 x 640 de l'image pleine résolution (le ballon y garde sa taille réelle), comme le modèle football de
roboflow/sports. Contrôle sur une AUTRE vidéo (test.mp4 + radar) avant de s'en servir : voir ETAT.md.
Les images du jeu d'entraînement sont des images de match : toujours dans ia/references/ (hors dépôt).
"""
import argparse
import collections
import json
import os
import random
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sans_radar as sr  # noqa: E402
import suivi             # noqa: E402

T = 640


def surs(frames, conf_min=0.55):
    """Ballons sûrs : [(t, x_px, y_px, taille_px)] + images reliées + candidats en mètres."""
    rel = [f for f in frames if f.get('H') is not None]
    cands = [sr.ball_candidates(f['balls'], np.array(f['H'])) for f in rel]
    path = sr.ball_path(cands, [f['t'] for f in rel])
    out = []
    for k, f in enumerate(rel):
        p = path[k]
        if not p or not f['balls']:
            continue
        Hk = np.array(f['H'])
        best = None
        for bx, by, bc in f['balls']:
            q = sr.project(Hk, [(bx, by)])[0]
            if abs(q[0] - p[0]) < 0.3 and abs(q[1] - p[1]) < 0.3:
                best = (bx, by, bc)
        if best is None or best[2] < conf_min:
            continue
        vois = [path[j] for j in (k - 2, k - 1, k + 1, k + 2) if 0 <= j < len(path) and path[j]]
        if len(vois) < 3 or max(np.hypot(v[0] - p[0], v[1] - p[1]) for v in vois) > 12:
            continue
        hs = sorted(pl['box'][3] - pl['box'][1] for pl in f['players']
                    if abs(pl['foot'][0] - best[0]) < 300 and abs(pl['foot'][1] - best[1]) < 200)
        h = hs[len(hs) // 2] if hs else 80.0
        out.append((f['t'], best[0], best[1], float(np.clip(0.14 * h, 6, 40))))
    return out, rel, cands


def cases_fixes(rel, cands, case=1.5, duree=90.0, n_min=25):
    vu = collections.defaultdict(list)
    for f, c in zip(rel, cands):
        for x, y, _ in c:
            vu[(int(x // case), int(y // case))].append(f['t'])
    return {k for k, v in vu.items() if len(v) >= n_min and max(v) - min(v) >= duree}


def donnees(dossiers, sortie, n_pos=2500, n_neg=1200, graine=0):
    rng = random.Random(graine)
    pos, neg = [], []
    for d in dossiers:
        fr = suivi.charger(d)
        video = json.load(open(os.path.join(d, 'source.json'), encoding='utf-8'))['video']
        s, rel, cands = surs(fr)
        fx = cases_fixes(rel, cands)
        tset = {round(x[0], 2) for x in s}
        n0 = len(neg)
        for f in rel:
            if round(f['t'], 2) in tset:
                continue
            Hk = np.array(f['H'])
            for bx, by, bc in f['balls']:
                q = sr.project(Hk, [(bx, by)])[0]
                if (int(q[0] // 1.5), int(q[1] // 1.5)) in fx:
                    neg.append((video, f['t'], bx, by))
        pos += [(video,) + x for x in s]
        print('%s : %d ballons sûrs, %d faux ballons fixes' % (d, len(s), len(neg) - n0), flush=True)
    rng.shuffle(pos); rng.shuffle(neg)
    pos, neg = pos[:n_pos], neg[:n_neg]
    for part in ('train', 'val'):
        for sub in ('images', 'labels'):
            os.makedirs(os.path.join(sortie, sub, part), exist_ok=True)
    items = sorted([('p', x) for x in pos] + [('n', x) for x in neg], key=lambda it: it[1][1])   # lecture dans l'ordre
    caps = {}
    for i, (kind, it) in enumerate(items):
        v, t, x, y = it[0], it[1], it[2], it[3]
        cap = caps.setdefault(v, cv2.VideoCapture(v))
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, img = cap.read()
        if not ok:
            continue
        H, W = img.shape[:2]
        x0 = int(np.clip(x - rng.randint(60, T - 60), 0, W - T))
        y0 = int(np.clip(y - rng.randint(60, T - 60), 0, H - T))
        part = 'val' if rng.random() < 0.1 else 'train'
        nom = '%s_%05d' % (kind, i)
        cv2.imwrite(os.path.join(sortie, 'images', part, nom + '.jpg'), img[y0:y0 + T, x0:x0 + T])
        with open(os.path.join(sortie, 'labels', part, nom + '.txt'), 'w') as fh:
            if kind == 'p':
                fh.write('0 %.5f %.5f %.5f %.5f\n' % ((x - x0) / T, (y - y0) / T, it[4] / T, it[4] / T))
    with open(os.path.join(sortie, 'ballon.yaml'), 'w', encoding='utf-8') as fh:
        fh.write('path: %s\ntrain: images/train\nval: images/val\nnames:\n  0: ball\n' % os.path.abspath(sortie).replace('\\', '/'))
    print('%d positifs, %d négatifs → %s' % (len(pos), len(neg), sortie))


def entrainer(ds, epoques=30, base='yolo11s.pt'):
    from ultralytics import YOLO
    m = YOLO(os.path.join(HERE, base))
    m.train(data=os.path.join(ds, 'ballon.yaml'), epochs=epoques, imgsz=T, batch=16, device=0, workers=4,
            project=os.path.abspath(os.path.join(ds, 'runs')), name='ballon', exist_ok=True, verbose=False, plots=False)
    best = os.path.join(ds, 'runs', 'ballon', 'weights', 'best.pt')
    os.makedirs(os.path.join(HERE, 'modeles'), exist_ok=True)
    shutil.copy(best, os.path.join(HERE, 'modeles', 'ballon_club.pt'))
    print('→ modeles/ballon_club.pt')


def main():
    ap = argparse.ArgumentParser(description='Détecteur de ballon entraîné sur nos vidéos (auto-étiquetage).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('donnees'); d.add_argument('dossiers', nargs='+'); d.add_argument('--sortie', required=True)
    d.add_argument('--positifs', type=int, default=2500); d.add_argument('--negatifs', type=int, default=1200)
    e = sub.add_parser('entrainer'); e.add_argument('ds'); e.add_argument('--epoques', type=int, default=30)
    a = ap.parse_args()
    os.chdir(HERE)
    if a.cmd == 'donnees':
        donnees(a.dossiers, a.sortie, a.positifs, a.negatifs)
    else:
        entrainer(a.ds, a.epoques)


if __name__ == '__main__':
    main()
