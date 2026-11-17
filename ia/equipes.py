"""ÉQUIPES TROUVÉES SEULES (PISTES.md, piste 3) : au lieu de couleurs écrites en dur (sans_radar.YEL / DARK), on
regroupe les maillots d'une séquence par leur couleur (empreinte L*a*b* de sans_radar.descripteur, KMeans).
Les deux plus gros groupes = les deux équipes ; le reste (arbitre, gardiens, spectateurs) est écarté.
La seule information donnée : la couleur de « Nous » (ex. jaune), pour savoir quel groupe est le nôtre.
Les clés restent celles de jeu.py : Nous → la couleur donnée, l'adversaire → 'noir' (ou 'rouge' si Nous = noir).
"""
import cv2
import numpy as np

# couleur annoncée → repère en a*, b* (OpenCV : a, b centrés sur 128)
TEINTES = {'jaune': (0, 60), 'rouge': (45, 30), 'orange': (25, 55), 'vert': (-40, 30), 'bleu': (5, -40),
           'noir': (0, -8), 'blanc': (0, 0), 'gris': (0, 0)}
CLAIR = {'blanc': 220, 'gris': 140, 'noir': 50}


def _x(feat):
    f = np.array(feat, float).reshape(3, 3)            # lignes : quartiles 25 / 50 / 75 ; colonnes : L, a, b
    L, a, b = f[1]
    # chroma surtout (robuste à l'ombre), un peu de clarté ; plus la dispersion des teintes
    return [0.1 * L, a - 128, b - 128, 0.5 * (f[2, 2] - f[0, 2]), 0.5 * (f[2, 1] - f[0, 1])]


def groupes(feats, k=3, seed=0):
    """KMeans sur les empreintes. Renvoie (étiquette par joueur, centres en (L, a, b) médians, tailles)."""
    X = np.float32([_x(f) for f in feats])
    k = min(k, len(X))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.1)
    cv2.setRNGSeed(seed)
    _, lab, _ = cv2.kmeans(X, k, None, crit, 8, cv2.KMEANS_PP_CENTERS)
    lab = lab.ravel()
    F = np.array([np.array(f, float).reshape(3, 3)[1] for f in feats])
    centres = np.array([np.median(F[lab == i], 0) for i in range(k)])
    return lab, centres, np.bincount(lab, minlength=k)


def distance_teinte(centre, nom):
    L, a, b = centre[0], centre[1] - 128, centre[2] - 128
    ta, tb = TEINTES.get(nom, (0, 0))
    d = np.hypot(a - ta, b - tb)
    if nom in CLAIR:
        d += 0.5 * abs(L - CLAIR[nom])
    return d


def assigner(frames, nous='jaune', k=4, proche=0.0):
    """Réécrit p['team'] de tous les joueurs des images (cache du banc). Renvoie un petit résumé.
    Règle (mesurée le 17 nov. sur off_placee contre le radar : 97,7 % justes, couleurs écrites en dur 97,6 %,
    avec 10 % de joueurs classés en moins ; fusionner les petits groupes (proche > 0) en ajoute mais fait des erreurs) :
    « Nous » = le groupe (≥ 8 % des joueurs) dont la teinte est la plus proche de la couleur annoncée ;
    l'adversaire = le plus gros des autres ; un petit groupe proche (a*, b*) d'une équipe la rejoint (ombre / soleil),
    le reste (arbitre, spectateurs) est écarté."""
    import jeu
    adv = jeu.OTHER.get(nous, 'noir')
    joueurs = [p for f in frames for p in f['players']]
    avec = [p for p in joueurs if p.get('feat')]
    if len(avec) < 20:
        return dict(ok=False, raison='trop peu de joueurs')
    lab, centres, tailles = groupes([p['feat'] for p in avec], k=k)
    gros = [i for i in range(len(tailles)) if tailles[i] >= 0.08 * len(avec)]
    gn = min(gros, key=lambda i: distance_teinte(centres[i], nous))
    autres = [i for i in gros if i != gn]
    if not autres:
        return dict(ok=False, raison='une seule couleur trouvée')
    ga = max(autres, key=lambda i: tailles[i])
    nom = {gn: nous, ga: adv}
    for i in range(len(tailles)):
        if i in nom:
            continue
        d = {g: np.hypot(*(centres[i][1:] - centres[g][1:])) for g in (gn, ga)}
        g = min(d, key=d.get)
        if d[g] < proche:
            nom[i] = nom[g]
    for p in joueurs:
        p['team'] = 'inconnu'
    for p, l in zip(avec, lab):
        p['team'] = nom.get(int(l), 'autre')
    return dict(ok=True, tailles=[int(t) for t in tailles], nous=centres[gn].round(0).tolist(),
                adversaire=centres[ga].round(0).tolist(), groupes={int(i): v for i, v in nom.items()})
