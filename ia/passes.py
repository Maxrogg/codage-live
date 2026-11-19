"""PASSES JOUEUR PAR JOUEUR (essai, à côté de jeu.py qui raisonne par ÉQUIPE).

Idée reprise de Vidal-Codina et al. 2022, « Automatic event detection in football using tracking data »
(arXiv 2202.00804, > 90 % des passes retrouvées sur données pro) :
  - possession d'un JOUEUR : ballon dans sa zone (rayon R) ; deux adversaires tout près → duel ;
  - une prise de balle ne compte que si le ballon change de direction ou de vitesse (sinon il passe à côté), ou
    si le joueur le garde un moment ;
  - passe = possession du joueur A puis du joueur B (B ≠ A) ; réussie si même équipe ;
  - ballon lissé (Savitzky-Golay, 2e degré) avant tout.
Ici les joueurs viennent des PISTES de suivi.py (un numéro par joueur suivi). Une piste coupée change de numéro :
garde-fou = même équipe, départ et arrivée à moins de `meme` m et ballon qui a peu bougé → même joueur.

Rien n'est branché par défaut : comparé à jeu.py sur la référence radar et sur Cascol (journal ETAT.md).
"""
import math

import numpy as np

import jeu

CFG = dict(
    R=2.0,           # m : zone de possession autour d'un joueur (positions vidéo à ~0,5-1,5 m près)
    R_duel=1.5,      # m : deux adversaires à moins de ça du ballon → duel
    lisse=5,         # images : fenêtre du lissage du ballon (5 images = 1 s à 5 images / s) ; 0 = sans
    min_pass=5.0,    # m : déplacement minimal du ballon entre deux joueurs pour une passe
    max_s=4.0,       # s : temps maximal entre la perte du ballon par A et la prise par B
    angle=35.0,      # degrés : changement de direction du ballon qui signe un contact
    dv=3.0,          # m/s : changement de vitesse du ballon qui signe un contact
    tenue=3,         # images : possession gardée au moins ça → contact certain
    meme=2.5,        # m : pistes coupées (même équipe, positions proches) = même joueur
)


def lisser(frames, w):
    """Ballon lissé (Savitzky-Golay) sur chaque morceau continu d'au moins w images."""
    if not w:
        return frames
    from scipy.signal import savgol_filter
    out = [dict(f) for f in frames]
    i = 0
    while i < len(out):
        if not out[i].get('ballon'):
            i += 1
            continue
        j = i + 1
        while j < len(out) and out[j].get('ballon') and out[j]['t'] - out[j - 1]['t'] < 0.5:
            j += 1
        if j - i >= w:
            xy = savgol_filter(np.array([out[k]['ballon'] for k in range(i, j)], float), w, 2, axis=0)
            for k in range(i, j):
                out[k]['ballon'] = (float(xy[k - i, 0]), float(xy[k - i, 1]))
        i = j
    return out


def joueurs_par_image(pistes, n, right, nous='jaune'):
    """Par image : [(id, 'N'/'E', x, y)] dans le repère de l'appli (Nous attaque vers la droite)."""
    per = [[] for _ in range(n)]
    for p in pistes:
        if p['team'] not in ('jaune', 'noir'):
            continue
        team = 'N' if p['team'] == nous else 'E'
        for q in p['pts']:
            x, y = q[2], q[3]
            if not right:
                x, y = jeu.L - x, jeu.W - y
            per[q[0]].append((p['id'], team, x, y))
    return per


def possesseurs(frames, J, c):
    """Par image : (id, équipe, position) du joueur qui a le ballon, 'duel', ou None."""
    out = []
    for f, js in zip(frames, J):
        b = f.get('ballon')
        if not b or not js:
            out.append(None)
            continue
        d = sorted((math.dist(b, (x, y)), i, t, (x, y)) for i, t, x, y in js)
        if d[0][0] > c['R']:
            out.append(None)
            continue
        opp = [e for e in d if e[2] != d[0][2] and e[0] <= c['R_duel']]
        if d[0][0] <= c['R_duel'] and opp:
            out.append('duel')
            continue
        out.append((d[0][1], d[0][2], d[0][3]))
    return out


def _vit(frames, i, j):
    a, b = frames[i].get('ballon'), frames[j].get('ballon')
    dt = frames[j]['t'] - frames[i]['t']
    if not a or not b or dt <= 0:
        return None
    return ((b[0] - a[0]) / dt, (b[1] - a[1]) / dt)


def controles(frames, P, c):
    """Possessions validées : [dict(id, team, i0, i1, pos0, pos1)]."""
    seq = []
    i = 0
    while i < len(P):
        p = P[i]
        if not isinstance(p, tuple):
            i += 1
            continue
        j = i
        while j + 1 < len(P) and (isinstance(P[j + 1], tuple) and P[j + 1][0] == p[0]
                                  or (P[j + 1] is None and j + 2 < len(P) and isinstance(P[j + 2], tuple) and P[j + 2][0] == p[0])):
            j += 1
        last = P[j] if isinstance(P[j], tuple) else P[j - 1]
        # contact ? possession tenue, ou ballon qui change de direction / de vitesse
        ok = (j - i + 1) >= c['tenue']
        if not ok:
            vin, vout = _vit(frames, max(0, i - 1), i), _vit(frames, j, min(len(frames) - 1, j + 1))
            if vin and vout:
                ni, no = math.hypot(*vin), math.hypot(*vout)
                if abs(ni - no) > c['dv']:
                    ok = True
                elif ni > 0.5 and no > 0.5:
                    cos = (vin[0] * vout[0] + vin[1] * vout[1]) / (ni * no)
                    ok = cos < math.cos(math.radians(c['angle']))
            else:
                ok = True
        if ok:
            seq.append(dict(id=p[0], team=p[1], i0=i, i1=j, pos0=p[2], pos1=last[2]))
        i = j + 1
    # pistes coupées : même équipe, même endroit → même joueur
    fus = []
    for s in seq:
        if fus and fus[-1]['team'] == s['team'] and fus[-1]['id'] != s['id'] and \
                math.dist(fus[-1]['pos1'], s['pos0']) <= c['meme'] and \
                frames[s['i0']]['t'] - frames[fus[-1]['i1']]['t'] <= 1.0:
            fus[-1].update(i1=s['i1'], pos1=s['pos1'], id=s['id'])
        elif fus and fus[-1]['id'] == s['id']:
            fus[-1].update(i1=s['i1'], pos1=s['pos1'])
        else:
            fus.append(dict(s))
    return fus


def passes(frames, J, half=1, k1=0.0, cfg=None):
    """Passes réussies / ratées (format de l'appli, src 'ia') à partir des possessions joueur par joueur."""
    c = dict(CFG, **(cfg or {}))
    fr = lisser(frames, c['lisse'])
    S = controles(fr, possesseurs(fr, J, c), c)
    start = 0 if half == 1 else 45 * 60000
    ev = []
    for a, b in zip(S, S[1:]):
        if a['id'] == b['id']:
            continue
        i0, i1 = a['i1'], b['i0']
        b0, b1 = fr[i0].get('ballon'), fr[i1].get('ballon')
        if not b0 or not b1 or fr[i1]['t'] - fr[i0]['t'] > c['max_s'] or math.dist(b0, b1) < c['min_pass']:
            continue
        team, ok = a['team'], a['team'] == b['team']
        el = jeu.eliminated(fr, i0, i1, team, b0, b1)
        kind = 'pass_deseq' if ok and el >= jeu.CFG['deseq'] and jeu._fwd(team, b0, b1) > 0 else 'pass'
        t = fr[i0]['t']
        ev.append(dict(kind=kind, team=team, t=int(round((t - k1) * 1000)) + start, half=half, src='ia',
                       video_s=round(t, 1), x=round(b0[0], 1), y=round(b0[1], 1), x2=round(b1[0], 1), y2=round(b1[1], 1),
                       ok=ok, elim=el))
    return ev


def actions(frames, J, half=1, k1=0.0, cfg=None):
    """Toutes les actions : passes joueur par joueur + le reste de jeu.py (frappes, conduites, duels)."""
    autres = [e for e in jeu.actions(frames, k1=k1, half=half) if e['kind'] not in ('pass', 'pass_deseq')]
    return sorted(passes(frames, J, half, k1, cfg) + autres, key=lambda e: e['t'])
