"""CALAGE PAR VUE : un calage (image → terrain) pour CHAQUE vue type du match (centre, demi-terrains, buts), à partir
de repères lus sur ces images ; longueur et largeur du terrain trouvées en même temps (communes à toutes les vues).

Pourquoi : la Veo filme des vues virtuelles d'un panorama. Relier une vue de but à UNE image de référence prise au
centre oblige à extrapoler l'homographie loin hors de cette image : quelques pixels d'erreur y deviennent plusieurs
mètres (Cascol, 19 nov. 2026 : même image reliée par 2 chemins → 10 à 110 px d'écart ; calage unique sur 16 repères
→ 1,2 m d'erreur moyenne et ligne médiane décalée). Par vue : 0,12 m d'écart médian sur 62 observations.

    py caler_vues.py references/cascol/reperes.json references/terrain_cascol

reperes.json (HORS dépôt) :
    {"video": "C:/.../match.mp4",
     "vues": {"415": {"points": [[1056, 502, "rond x médiane loin"], ...],      repères nommés (REPERES)
                      "cercle": [[537, 573], ...],                             points du rond central
                      "lignes": [[500, 435, "touche loin"], ...]},             points sur une ligne (LIGNES)
              ...}}
Les vues doivent se ressembler assez pour que toute image du match se relie à l'une d'elles (suivi.references) ;
la longueur n'est trouvée que si une vue montre à la fois une surface et le rond central (sinon : --longueur).
Sortie : <dossier>/terrain.json ("vues": [{image, G}], dims) + vue_<t>.png + reference.jpg (1re vue).
"""
import argparse
import json
import os
import shutil

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPERES = {
    'centre': lambda L, W: (L / 2, W / 2),
    'rond x médiane loin': lambda L, W: (L / 2, W / 2 - 9.15),
    'rond x médiane près': lambda L, W: (L / 2, W / 2 + 9.15),
    'médiane x touche loin': lambda L, W: (L / 2, 0),
    'médiane x touche près': lambda L, W: (L / 2, W),
}
for nom, x in (('gauche', lambda L, d: d), ('droite', lambda L, d: L - d)):
    REPERES.update({
        'coin loin %s' % nom: (lambda x: lambda L, W: (x(L, 0), 0))(x),
        'coin près %s' % nom: (lambda x: lambda L, W: (x(L, 0), W))(x),
        'surface %s coin loin' % nom: (lambda x: lambda L, W: (x(L, 16.5), W / 2 - 20.16))(x),
        'surface %s coin près' % nom: (lambda x: lambda L, W: (x(L, 16.5), W / 2 + 20.16))(x),
        'surface %s x but loin' % nom: (lambda x: lambda L, W: (x(L, 0), W / 2 - 20.16))(x),
        'surface %s x but près' % nom: (lambda x: lambda L, W: (x(L, 0), W / 2 + 20.16))(x),
        'surf. but %s coin loin' % nom: (lambda x: lambda L, W: (x(L, 5.5), W / 2 - 9.16))(x),
        'surf. but %s coin près' % nom: (lambda x: lambda L, W: (x(L, 5.5), W / 2 + 9.16))(x),
        'surf. but %s x but loin' % nom: (lambda x: lambda L, W: (x(L, 0), W / 2 - 9.16))(x),
        'surf. but %s x but près' % nom: (lambda x: lambda L, W: (x(L, 0), W / 2 + 9.16))(x),
        'arc %s x surface loin' % nom: (lambda x: lambda L, W: (x(L, 16.5), W / 2 - 7.31))(x),
        'arc %s x surface près' % nom: (lambda x: lambda L, W: (x(L, 16.5), W / 2 + 7.31))(x),
    })
# ligne : a x + b y = c
LIGNES = {
    'touche loin': lambda L, W: (0, 1, 0), 'touche près': lambda L, W: (0, 1, W), 'médiane': lambda L, W: (1, 0, L / 2),
    'but gauche': lambda L, W: (1, 0, 0), 'but droite': lambda L, W: (1, 0, L),
    'surface gauche': lambda L, W: (1, 0, 16.5), 'surface droite': lambda L, W: (1, 0, L - 16.5),
}


def _proj(h, q):
    H = np.append(h, 1).reshape(3, 3)
    p = np.column_stack([np.asarray(q, float), np.ones(len(q))]) @ H.T
    return p[:, :2] / p[:, 2:]


def residus(z, vues, L_fixe=None, W_fixe=None):
    L = L_fixe or z[0]
    W = W_fixe or z[1]
    r = []
    for k, V in enumerate(vues):
        h = z[2 + 8 * k: 10 + 8 * k]
        if V.get('points'):
            m = _proj(h, [p[:2] for p in V['points']])
            r += list((m - np.array([REPERES[p[2]](L, W) for p in V['points']])).ravel())
        if V.get('cercle'):
            m = _proj(h, V['cercle'])
            r += list(np.hypot(m[:, 0] - L / 2, m[:, 1] - W / 2) - 9.15)
        for x, y, nom in V.get('lignes', []):
            a, b, c = LIGNES[nom](L, W)
            u, v = _proj(h, [(x, y)])[0]
            r.append(a * u + b * v - c)
    return np.array(r)


def _init(L, W, vues):
    z = [L, W]
    for V in vues:
        src = [p[:2] for p in V.get('points', [])]
        dst = [REPERES[p[2]](L, W) for p in V.get('points', [])]
        c = V.get('cercle', [])
        if len(src) < 4 and len(c) >= 2:                  # extrémités gauche / droite du rond (à peu près)
            a, b = sorted(c, key=lambda q: q[0])[0], sorted(c, key=lambda q: q[0])[-1]
            src += [a, b]; dst += [(L / 2 - 9.15, W / 2), (L / 2 + 9.15, W / 2)]
        if len(src) < 4:
            raise SystemExit('Une vue a moins de 4 repères (points + extrémités du rond).')
        H, _ = cv2.findHomography(np.float32(src), np.float32(dst), 0)
        z += list((H / H[2, 2]).ravel()[:8])
    return np.array(z)


def caler(vues, longueur=None, largeur=None):
    """vues = [dict(points, cercle, lignes)] → (L, W, [G image → mètres réels], résidus)."""
    from scipy.optimize import least_squares
    best = None
    for L0, W0 in ((95, 55), (100, 62), (105, 68), (100, 55), (105, 60)):
        s = least_squares(residus, _init(longueur or L0, largeur or W0, vues), args=(vues, longueur, largeur),
                          loss='soft_l1', f_scale=0.5)
        if best is None or s.cost < best.cost:
            best = s
    z = best.x
    L, W = longueur or z[0], largeur or z[1]
    Gs = [np.append(z[2 + 8 * k: 10 + 8 * k], 1).reshape(3, 3) for k in range(len(vues))]
    return float(L), float(W), Gs, residus(z, vues, longueur, largeur)


def main():
    ap = argparse.ArgumentParser(description='Calage du terrain par vue (repères lus sur les images).')
    ap.add_argument('reperes'); ap.add_argument('sortie')
    ap.add_argument('--longueur', type=float); ap.add_argument('--largeur', type=float)
    a = ap.parse_args()
    R = json.load(open(a.reperes, encoding='utf-8'))
    ts = list(R['vues'])
    vues = [R['vues'][t] for t in ts]
    L, W, Gs, r = caler(vues, a.longueur, a.largeur)
    print('Terrain %.1f x %.1f m ; écart médian %.2f m, max %.2f m (%d observations)' % (L, W, np.median(abs(r)), abs(r).max(), len(r)))
    for t in ts:
        autres = [u for u in ts if u != t]
        if autres and not (a.longueur and a.largeur):
            try:
                L2, W2, _, _ = caler([R['vues'][u] for u in autres], a.longueur, a.largeur)
                print('  sans la vue %s : %.1f x %.1f m' % (t, L2, W2))
            except SystemExit:
                pass
    os.makedirs(a.sortie, exist_ok=True)
    cap = cv2.VideoCapture(R['video'])
    out = []
    for t, G in zip(ts, Gs):
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
        ok, img = cap.read()
        if not ok:
            raise SystemExit('Image illisible à %s s' % t)
        nom = 'vue_%s.png' % t
        cv2.imwrite(os.path.join(a.sortie, nom), img)
        if not out:
            cv2.imwrite(os.path.join(a.sortie, 'reference.jpg'), img)
        out.append(dict(t=float(t), image=nom, G=(np.diag([105 / L, 68 / W, 1]) @ G).tolist()))
    json.dump(dict(nom=os.path.basename(a.sortie), dims=dict(longueur=round(L, 1), largeur=round(W, 1)), vues=out,
                   G=out[0]['G'], ref_t=out[0]['t'], source='caler_vues'),
              open(os.path.join(a.sortie, 'terrain.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('→', os.path.join(a.sortie, 'terrain.json'))


if __name__ == '__main__':
    main()
