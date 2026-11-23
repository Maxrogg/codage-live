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


def donnees(dossiers, sortie, n_pos=2500, n_neg=1200, graine=0, conf_min=0.55):
    rng = random.Random(graine)
    pos, neg = [], []
    for d in dossiers:
        fr = suivi.charger(d)
        video = json.load(open(os.path.join(d, 'source.json'), encoding='utf-8'))['video']
        s, rel, cands = surs(fr, conf_min)
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


def entrainer(ds, epoques=30, base='yolo11s.pt', sortie='modeles/ballon_club.pt', nom='ballon'):
    from ultralytics import YOLO
    m = YOLO(os.path.join(HERE, base))
    m.train(data=os.path.join(ds, 'ballon.yaml'), epochs=epoques, imgsz=T, batch=16, device=0,
            workers=0,                     # workers > 0 : plantage sous Windows (19 nov.)
            project=os.path.abspath(os.path.join(ds, 'runs')), name=nom, exist_ok=True, verbose=False, plots=False)
    best = os.path.join(ds, 'runs', nom, 'weights', 'best.pt')
    os.makedirs(os.path.dirname(os.path.join(HERE, sortie)), exist_ok=True)
    shutil.copy(best, os.path.join(HERE, sortie))
    print('->', sortie)


def controler(modele, conf=0.1):
    """Contrôle sur test.mp4 (séquence off_placee, JAMAIS utilisée à l'entraînement) contre le ballon du RADAR et le
    codage du coach : dict(juste, faux, non_vu, reussies_trouvees, reussies_vraies, reussies_ia, ratees_ia)."""
    import banc
    import comparer
    import jeu
    import mesure_vision as mv
    import noter
    from ultralytics import YOLO
    T_, _ = banc.charger_terrain('references/terrain_club')
    G = np.array(T_['G'])
    cache = json.load(open(os.path.join(HERE, 'references', 'banc_cache', 'off_placee.json'), encoding='utf-8'))
    rel = [f for f in cache['frames'] if f['H'] is not None]
    seq = [q for q in json.load(open(os.path.join(HERE, 'references', 'banc.json'), encoding='utf-8'))['sequences']
           if q['nom'] == 'off_placee'][0]
    dec = seq['decalage']
    rad = mv.radar_at(noter.load_raw(os.path.join(HERE, 'references', 'off_placee', 'radar_brut.json')))
    m = YOLO(os.path.join(HERE, modele))
    cap = cv2.VideoCapture(seq['video'])
    fr = []
    for f in rel:
        cap.set(cv2.CAP_PROP_POS_MSEC, f['t'] * 1000)
        ok, img = cap.read()
        fr.append(dict(f, balls=[list(b) for b in sr.ballons_foot(m, img, conf=conf, device=0, half=True)] if ok else []))
    cands = [sr.ball_candidates(f['balls'], G @ np.array(f['H'])) for f in fr]
    path = sr.ball_path(cands, [f['t'] for f in fr])
    res = dict(juste=0, faux=0, non_vu=0)
    for f, p in zip(fr, path):
        q = rad.get(round(f['t'] + dec, 2), {}).get('ballon')
        if not q:
            continue
        if p is None:
            res['non_vu'] += 1
        elif np.hypot(p[0] - q[0], p[1] - q[1]) < 3:
            res['juste'] += 1
        else:
            res['faux'] += 1
    brut, _ = suivi.brut_suivi(G, fr, path)
    brut = [dict(x, t=round(x['t'] + dec, 2)) for x in brut]
    ref = json.load(open(os.path.join(HERE, 'references', 'off_placee', 'ref.json'), encoding='utf-8'))
    frs, _ = jeu.normalize(brut, ref['nous'], ref['sens'] == 'droite')
    ia = jeu.actions(jeu.fill_ball(frs))
    man, _ = comparer.load(os.path.join(HERE, 'references', 'off_placee', 'codage.json'))
    man = [e for e in man if e.get('video_s') is not None and frs[0]['t'] - 1 <= e['video_s'] <= frs[-1]['t'] + 1]
    ok_m = [e for e in man if comparer.CATS[0][1](e)]
    ok_i = [e for e in ia if comparer.CATS[0][1](e)]
    res.update(reussies_trouvees=len(comparer.match(ok_m, ok_i, 4.0)), reussies_vraies=len(ok_m), reussies_ia=len(ok_i),
               ratees_ia=sum(1 for e in ia if comparer.CATS[1][1](e)))
    return res


def score(r):
    """Plus haut = mieux : un faux ballon coûte deux fois un ballon juste (c'est lui qui invente des passes)."""
    return r['juste'] - 2 * r['faux']


def boucle(dossiers, tours=3, epoques=20, journal='references/ballon_boucle.csv', debut=1, depuis_meilleur=False, conf_min=0.55):
    """Auto-amélioration : le meilleur modèle refait le ballon des analyses (ballons sûrs de SES détections) → nouvel
    entraînement → contrôle sur test.mp4 → gardé seulement s'il fait mieux (score, et pas plus de 3 ballons justes en
    moins). Journal : references/ballon_boucle.csv."""
    import csv
    import time as _t
    best = 'modeles/ballon_club.pt'
    rb = controler(best)
    print('départ', best, rb, 'score', score(rb), flush=True)
    for k in range(debut, debut + tours):
        tag = 'r%d' % k
        dets = []
        for d in dossiers:
            dn = os.path.normpath(d)
            out = os.path.normpath(os.path.join(os.path.dirname(dn), '..', 'boucle_' + tag, os.path.basename(dn)))
            suivi.reballon(d, out, best)
            dets.append(out)
        ds = os.path.join(HERE, 'references', 'ballon_ds_' + tag)
        donnees(dets, ds, n_pos=4000, n_neg=1500, graine=k, conf_min=conf_min)
        cand = 'modeles/ballon_club_%s.pt' % tag
        entrainer(ds, epoques, sortie=cand, nom=tag, base=best if depuis_meilleur else 'yolo11s.pt')
        rc = controler(cand)
        garde = score(rc) > score(rb) and rc['juste'] >= rb['juste'] - 3
        print(tag, rc, 'score', score(rc), '->', 'GARDÉ' if garde else 'écarté', flush=True)
        new = not os.path.exists(journal)
        with open(journal, 'a', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh, delimiter=';')
            if new:
                w.writerow(['date', 'tour', 'modele', 'juste', 'faux', 'non_vu', 'reussies_trouvees', 'reussies_ia',
                            'ratees_ia', 'score', 'decision'])
            w.writerow([_t.strftime('%Y-%m-%d %H:%M'), tag, cand, rc['juste'], rc['faux'], rc['non_vu'],
                        rc['reussies_trouvees'], rc['reussies_ia'], rc['ratees_ia'], score(rc), 'garde' if garde else 'ecarte'])
        if garde:
            shutil.copy(os.path.join(HERE, cand), os.path.join(HERE, 'modeles', 'ballon_club.pt'))
            rb = rc


def main():
    ap = argparse.ArgumentParser(description='Détecteur de ballon entraîné sur nos vidéos (auto-étiquetage).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('donnees'); d.add_argument('dossiers', nargs='+'); d.add_argument('--sortie', required=True)
    d.add_argument('--positifs', type=int, default=2500); d.add_argument('--negatifs', type=int, default=1200)
    e = sub.add_parser('entrainer'); e.add_argument('ds'); e.add_argument('--epoques', type=int, default=30)
    c = sub.add_parser('controler'); c.add_argument('modele')
    b = sub.add_parser('boucle'); b.add_argument('dossiers', nargs='+'); b.add_argument('--tours', type=int, default=3)
    b.add_argument('--epoques', type=int, default=20); b.add_argument('--debut', type=int, default=1)
    b.add_argument('--depuis-meilleur', action='store_true', help='affiner le meilleur modèle au lieu de repartir de yolo11s')
    b.add_argument('--conf-min', type=float, default=0.55, help='confiance minimale des ballons « sûrs »')
    a = ap.parse_args()
    os.chdir(HERE)
    if a.cmd == 'donnees':
        donnees(a.dossiers, a.sortie, a.positifs, a.negatifs)
    elif a.cmd == 'entrainer':
        entrainer(a.ds, a.epoques)
    elif a.cmd == 'controler':
        r = controler(a.modele)
        print(r, 'score', score(r))
    else:
        boucle(a.dossiers, a.tours, a.epoques, debut=a.debut, depuis_meilleur=a.depuis_meilleur, conf_min=a.conf_min)


if __name__ == '__main__':
    main()
