"""Mesure de l'IA SANS RADAR sur une séquence de référence : vidéo caméra Veo + radar (= la vérité).

    py mesure_vision.py --video C:\\Users\\...\\test.mp4            (séquence off_placee, décalage 13,84 s)
    py mesure_vision.py --video test.mp4 --refaire                  relance YOLO + décor (sinon cache)
    py mesure_vision.py --video test.mp4 --clics 3 5 8              + simulation du calage par clics

La partie lente (YOLO + décor) est faite une fois et rangée dans references/<séquence>/vision_cache.json
(HORS dépôt : positions de joueurs mineurs).
Affiche :
  - erreur des joueurs (médiane, et par tranches de 4 s pour voir la dérive), calage commun et validation croisée ;
  - ballon : vu, erreur médiane, faux ballons à plus de 10 m ;
  - note noter.py des positions « vision » (même calcul que pour le radar).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import noter       # noqa: E402
import sans_radar as sr  # noqa: E402

# Points du terrain faciles à cliquer (mètres, repère du radar 105 x 68) : coins des surfaces + milieu.
REPERES = {
    'surface G haut': (16.5, 13.84), 'surface G bas': (16.5, 54.16),
    'surface D haut': (88.5, 13.84), 'surface D bas': (88.5, 54.16),
    'surface G haut ligne': (0.0, 13.84), 'surface G bas ligne': (0.0, 54.16),
    'surface D haut ligne': (105.0, 13.84), 'surface D bas ligne': (105.0, 54.16),
    'point penalty G': (11.0, 34.0), 'point penalty D': (94.0, 34.0),
    'coin G haut': (0.0, 0.0), 'coin G bas': (0.0, 68.0), 'coin D haut': (105.0, 0.0), 'coin D bas': (105.0, 68.0),
    'centre': (52.5, 34.0), 'milieu haut': (52.5, 0.0), 'milieu bas': (52.5, 68.0),
    'rond haut': (52.5, 24.85), 'rond bas': (52.5, 43.15),
}
W_IMG, H_IMG = 1920, 1080


def build_cache(video, radar, offset, model_name='yolo11s.pt', imgsz=2880, progress=True):
    from ultralytics import YOLO
    model = YOLO(model_name)
    cap = cv2.VideoCapture(video)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 25.0)
    times = [f['t'] for f in radar if 0 <= f['t'] - offset <= dur - 0.05]
    tr = sr.CameraTracker()
    imgs, frames = [], []
    t0 = time.time()
    for k, t in enumerate(times):
        cap.set(cv2.CAP_PROP_POS_MSEC, (t - offset) * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        P, B = sr.detect(model, fr, imgsz=imgsz)
        frames.append(dict(t=t, players=[dict(p, box=list(p['box']), foot=list(p['foot'])) for p in P],
                           balls=[list(b) for b in B]))
        imgs.append((fr, [p['box'] for p in P]))
        if progress:
            print('\r  YOLO %d / %d (%.2f s / image)' % (k + 1, len(times), (time.time() - t0) / (k + 1)), end='', flush=True)
    print()
    # image de référence = celle du milieu ; chaque image reliée directement à elle par le décor, sinon de proche en proche
    ref = len(frames) // 2
    feats = [tr.features(fr, boxes) for fr, boxes in imgs]
    direct = 0
    for k, f in enumerate(frames):
        H = np.eye(3) if k == ref else tr.homography(feats[k], feats[ref])
        if H is not None:
            direct += 1
        elif k > 0 and frames[k - 1].get('H') is not None:
            Hp = tr.homography(feats[k], feats[k - 1])
            H = np.array(frames[k - 1]['H']) @ Hp if Hp is not None else None
        f['H'] = H.tolist() if H is not None else None
    print('  décor : %d / %d images reliées directement à la référence' % (direct, len(frames)))
    return dict(video=os.path.basename(video), offset=offset, model=model_name, imgsz=imgsz, ref=ref, frames=frames)


def radar_at(radar):
    return {round(f['t'], 2): f for f in radar}


def player_errors(G, frames, rad, tol=3.0):
    """[(t, erreur)] des joueurs détectés appariés à leur marque radar (même équipe, à moins de tol m)."""
    out = []
    for f in frames:
        if f['H'] is None:
            continue
        r = rad[round(f['t'], 2)]
        Gk = G @ np.array(f['H'])
        for team in ('jaune', 'noir'):
            P = [p['foot'] for p in f['players'] if p['team'] == team]
            if P and r.get(team):
                out += [(f['t'], d) for _, _, d in sr.match_one_to_one(sr.project(Gk, P), r[team], tol)]
    return out


def samples(frames, rad):
    return [(np.array(f['H']), f['players'], rad[round(f['t'], 2)]) for f in frames if f['H'] is not None]


def calage_radar(cache, rad):
    f = cache['frames'][cache['ref']]
    players = [dict(p, foot=tuple(p['foot'])) for p in f['players']]
    G0 = sr.calibrate_on_radar(players, f['balls'], rad[round(f['t'], 2)], iters=20000)
    return G0, sr.calibrate_joint(G0, samples(cache['frames'], rad))


def calage_clics(G_vrai, px, frames, seed=0, marge=60):
    """Simule le calage par clics du coach. La caméra suit le jeu : un repère n'est visible que sur certaines
    images. Chaque repère est cliqué (erreur `px` pixels au hasard) sur l'image où il est le plus au centre,
    ramené dans l'image de référence par le décor, puis l'homographie est recalculée à partir de ces clics seuls.
    Renvoie (G, nombre de repères cliqués) ; G = None si moins de 4 repères."""
    rng = np.random.default_rng(seed)
    src, dst = [], []
    for m in REPERES.values():
        best = None
        for f in frames:
            if f['H'] is None:
                continue
            Hk = np.array(f['H'])
            p = sr.project(np.linalg.inv(G_vrai @ Hk), [m])[0]
            if marge <= p[0] <= W_IMG - marge and marge <= p[1] <= H_IMG - marge:
                d = np.hypot(p[0] - W_IMG / 2, p[1] - H_IMG / 2)
                if best is None or d < best[0]:
                    best = (d, p, Hk)
        if best:
            src.append(sr.project(best[2], [best[1] + rng.normal(0, px, 2)])[0]); dst.append(m)
    if len(src) < 4:
        return None, len(src)
    G, _ = cv2.findHomography(np.float32(src), np.float32(dst), 0)
    return G, len(src)


def ball_stats(G, frames, rad):
    cands, times, truth = [], [], []
    for f in frames:
        Gk = G @ np.array(f['H']) if f['H'] is not None else None
        cands.append(sr.ball_candidates(f['balls'], Gk) if Gk is not None else [])
        times.append(f['t'])
        truth.append(rad[round(f['t'], 2)].get('ballon'))
    path = sr.ball_path(cands, times)
    seen = [(p, q) for p, q in zip(path, truth) if p is not None and q]
    err = [float(np.hypot(p[0] - q[0], p[1] - q[1])) for p, q in seen]
    return path, len([p for p in path if p]) / max(1, len(path)), err


def vision_brut(G, frames, path):
    out = []
    for f, b in zip(frames, path):
        if f['H'] is None:
            continue
        Gk = G @ np.array(f['H'])
        d = sr.to_brut(f['t'], [dict(p, foot=tuple(p['foot'])) for p in f['players']], [], Gk)
        d['ballon'] = b
        out.append(d)
    return sr.clean_brut(out)


def note_vision(folder, brut):
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, 'vision')
        os.makedirs(d)
        for n in ('codage.json', 'ref.json'):
            shutil.copy(os.path.join(folder, n), d)
        json.dump(brut, open(os.path.join(d, 'radar_brut.json'), 'w', encoding='utf-8'))
        return noter.note(tmp, history=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def med(v):
    return float(np.median(v)) if len(v) else float('nan')


def rapport(G, cache, rad, folder, titre):
    fr = cache['frames']
    e = player_errors(G, fr, rad)
    print('\n== %s' % titre)
    print('Joueurs : erreur médiane %.2f m (%d appariés à moins de 3 m)' % (med([d for _, d in e]), len(e)))
    t0 = fr[0]['t']
    bins = {}
    for t, d in e:
        bins.setdefault(int((t - t0) // 4), []).append(d)
    print('  par tranche de 4 s : ' + '  '.join('%d-%ds %.2f' % (4 * k, 4 * k + 4, med(v)) for k, v in sorted(bins.items())))
    path, vu, err = ball_stats(G, fr, rad)
    print('Ballon : vu %d %%, erreur médiane %.2f m, à plus de 10 m %d %%' % (
        round(100 * vu), med(err), round(100 * np.mean([x > 10 for x in err])) if err else 0))
    glob, _ = note_vision(folder, vision_brut(G, fr, path))
    return med([d for _, d in e]), glob


def main():
    ap = argparse.ArgumentParser(description='Mesure de l\'IA sans radar (vidéo caméra + radar de référence).')
    ap.add_argument('--video', required=True)
    ap.add_argument('--ref', default='off_placee', help='séquence dans references/')
    ap.add_argument('--decalage', type=float, default=13.84, help='s : instant du radar où commence la vidéo caméra')
    ap.add_argument('--refaire', action='store_true', help='relancer YOLO + décor (sinon cache)')
    ap.add_argument('--clics', type=float, nargs='*', default=[], help='simule le calage par clics, erreurs en pixels (ex. 3 5 8)')
    a = ap.parse_args()
    folder = os.path.join(HERE, 'references', a.ref)
    radar = noter.load_raw(os.path.join(folder, 'radar_brut.json'))
    rad = radar_at(radar)
    cp = os.path.join(folder, 'vision_cache.json')
    if a.refaire or not os.path.exists(cp):
        json.dump(build_cache(a.video, radar, a.decalage), open(cp, 'w', encoding='utf-8'))
    cache = json.load(open(cp, encoding='utf-8'))
    fr = cache['frames']
    print('%d images (référence n° %d, t = %.2f s radar)' % (len(fr), cache['ref'], fr[cache['ref']]['t']))

    G0, G = calage_radar(cache, rad)
    rapport(G0, cache, rad, folder, 'Calage sur UNE image (radar)')
    rapport(G, cache, rad, folder, 'Calage commun sur toutes les images (radar)')
    h = len(fr) // 2
    for a_, b_ in ((fr[:h], fr[h:]), (fr[h:], fr[:h])):          # calé sur une moitié, mesuré sur l'autre
        Gh = sr.calibrate_joint(G0, samples(a_, rad))
        print('Validation croisée : %.2f m' % med([d for _, d in player_errors(Gh, b_, rad)]))
    for px in a.clics:
        res, n = [], 0
        for s in range(5):
            Gc, n = calage_clics(G, px, fr, s)
            e = [d for _, d in player_errors(Gc, fr, rad)] if Gc is not None else []
            res.append('%.2f (%d)' % (med(e), len(e)))
        print('\nClics à %.0f px près (%d repères visibles) : erreur médiane joueurs (appariés) %s (5 essais)' % (
            px, n, ' / '.join(res)))


if __name__ == '__main__':
    main()
