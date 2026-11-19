"""VÉRIFICATION À L'ŒIL des actions trouvées par l'IA (sans codage du coach) : planches d'images tirées au hasard.

    py verifier.py references/cascol/v2/mt1_a --parties ... --sens gauche --n 30 --type pass
    → <dossier>/verif/action_XX.jpg : 4 images (0,6 s avant, départ, milieu, arrivée + 0,4 s) ; ballon vu par l'IA
      (cercle rouge), départ (vert) et arrivée (bleu) de la passe ; + verif/liste.json (verdict à remplir).

On juge chaque planche (vraie passe ? bonne équipe ? réussie ?) → part d'actions justes (précision) et causes des
erreurs, sur un échantillon au hasard : une mesure de vérité sans codage, à refaire après chaque changement.
"""
import argparse
import json
import os
import random
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import suivi  # noqa: E402

L, W = 105.0, 68.0


def vers_radar(p, right):
    """Repère appli (Nous attaque vers la droite) → repère radar."""
    return p if right else (L - p[0], W - p[1])


def planche(cap, Hs, ts, ev, right, brut_t, n=8):
    """n images de 0,6 s avant à 0,6 s après la passe, recadrées autour de l'action (départ, arrivée, ballon)."""
    t0 = ev['video_s']
    a = vers_radar((ev['x'], ev['y']), right)
    b = vers_radar((ev.get('x2', ev['x']), ev.get('y2', ev['y'])), right)
    dist = float(np.hypot(b[0] - a[0], b[1] - a[1]))
    dur = max(0.4, dist / 12.0)                              # durée estimée (ballon ~12 m/s)
    vues = []
    for t in np.linspace(t0 - 0.6, t0 + dur + 0.6, n):
        i = int(np.argmin(abs(ts - t)))
        cap.set(cv2.CAP_PROP_POS_MSEC, ts[i] * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        Hi = np.linalg.inv(Hs[i])

        def px(p):
            q = Hi @ np.array([p[0], p[1], 1.0])
            return int(np.clip(q[0] / q[2], -5000, 5000)), int(np.clip(q[1] / q[2], -5000, 5000))
        pts = [px(a), px(b)]
        bt = brut_t.get(round(ts[i], 2))
        if bt and bt.get('ballon'):
            pb = px(bt['ballon']); pts.append(pb)
            cv2.circle(f, pb, 16, (0, 0, 255), 2)
        cv2.circle(f, pts[0], 10, (0, 220, 0), 2)
        cv2.circle(f, pts[1], 10, (255, 120, 0), 2)
        vues.append((ts[i], f, pts))
    P = np.array([p for _, _, pts in vues for p in pts if abs(p[0]) < 3000 and abs(p[1]) < 3000] or [(960, 540)])
    cx, cy = np.clip(P.mean(0), 0, (1920, 1080))
    w = max(640, min(1920, (P[:, 0].max() - P[:, 0].min()) * 1.6)); h = w * 9 / 16
    x0 = int(np.clip(cx - w / 2, 0, 1920 - w)); y0 = int(np.clip(cy - h / 2, 0, 1080 - h))
    ims = []
    for t, f, _ in vues:
        c = cv2.resize(f[y0:y0 + int(h), x0:x0 + int(w)], (480, 270))
        cv2.putText(c, '%.1f' % t, (8, 26), 0, 0.8, (0, 0, 255), 2)
        ims.append(c)
    while len(ims) < n:
        ims.append(np.zeros((270, 480, 3), np.uint8))
    img = np.vstack([np.hstack(ims[:4]), np.hstack(ims[4:8])])
    txt = '%s %s %s %.0f m (%.1f s) vert=depart bleu=arrivee rouge=ballon IA' % (
        ev['kind'], 'NOUS' if ev['team'] == 'N' else 'EUX', 'reussie' if ev.get('ok') else 'ratee', dist, t0)
    cv2.putText(img, txt, (10, 530), 0, 0.8, (0, 255, 255), 2)
    return img


def main():
    ap = argparse.ArgumentParser(description='Planches pour vérifier à l\'œil des actions de l\'IA.')
    ap.add_argument('sortie'); ap.add_argument('--parties', nargs='*', default=[])
    ap.add_argument('--sens', choices=['droite', 'gauche'], required=True)
    ap.add_argument('--n', type=int, default=30); ap.add_argument('--type', default='pass')
    ap.add_argument('--actions', default='actions_ia.json'); ap.add_argument('--graine', type=int, default=0)
    ap.add_argument('--dossier', default='verif')
    a = ap.parse_args()
    frames = suivi.charger(a.sortie)
    for d in a.parties:
        frames += suivi.charger(d)
    frames.sort(key=lambda f: f['t'])
    rel = [f for f in frames if f.get('H') is not None]
    ts = np.array([f['t'] for f in rel])
    Hs = [np.array(f['H']) for f in rel]
    brut = json.load(open(os.path.join(a.sortie, 'radar_brut.json'), encoding='utf-8'))
    brut_t = {round(f['t'], 2): f for f in brut}
    ev = json.load(open(os.path.join(a.sortie, a.actions), encoding='utf-8'))
    ev = [e for e in ev if e['kind'].startswith(a.type)]
    random.Random(a.graine).shuffle(ev)
    ev = ev[:a.n]
    src = json.load(open(os.path.join(a.sortie, 'source.json'), encoding='utf-8'))
    cap = cv2.VideoCapture(src['video'])
    d = os.path.join(a.sortie, a.dossier)
    os.makedirs(d, exist_ok=True)
    for k, e in enumerate(ev):
        cv2.imwrite(os.path.join(d, 'action_%02d.jpg' % k), planche(cap, Hs, ts, e, a.sens == 'droite', brut_t))
    json.dump([dict(e, planche='action_%02d.jpg' % k, verdict=None) for k, e in enumerate(ev)],
              open(os.path.join(d, 'liste.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(ev), 'planches dans', d)


if __name__ == '__main__':
    main()
