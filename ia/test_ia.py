"""Tests du module d'analyse (sans vidéo réelle) : python test_ia.py
Fabrique des images de radar façon Veo, puis vérifie lecture, sens, gardien, possession, actions, format appli."""
import json
import math
import os
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radar  # noqa: E402
import jeu    # noqa: E402
import analyser  # noqa: E402

FAIL = []


def ok(c, msg):
    print(('OK   ' if c else 'ÉCHEC ') + msg)
    if not c:
        FAIL.append(msg)


BOX = (1620, 12, 289, 184)


def m2px(x, y):
    bx, by, w, h = BOX
    return int(bx + x / 105 * w), int(by + y / 68 * h)


def frame(rouge, noir, ballon):
    """Image 1920x1080 avec un radar dessiné comme celui de Veo."""
    im = np.full((1080, 1920, 3), (60, 140, 60), np.uint8)               # pelouse
    im[:300, :] = (200, 160, 110)                                          # ciel
    bx, by, w, h = BOX
    cv2.rectangle(im, (bx, by), (bx + w, by + h), (82, 67, 42), -1)       # fond ardoise
    cv2.line(im, (bx + w // 2, by), (bx + w // 2, by + h), (150, 150, 150), 1)
    for x, y in rouge:
        cx, cy = m2px(x, y)
        pts = np.array([[cx, cy - 5], [cx - 5, cy + 4], [cx + 5, cy + 4]], np.int32)
        cv2.fillPoly(im, [pts], (60, 40, 210))
    for x, y in noir:
        cx, cy = m2px(x, y)
        cv2.circle(im, (cx, cy), 6, (200, 200, 200), 1)
        cv2.circle(im, (cx, cy), 5, (5, 5, 5), -1)
    if ballon:
        cx, cy = m2px(*ballon)
        cv2.line(im, (cx - 5, cy), (cx + 5, cy), (40, 230, 240), 3)
        cv2.line(im, (cx, cy - 5), (cx, cy + 5), (40, 230, 240), 3)
    return im


# --- lecture du radar ---
R = [(100, 34), (80, 20), (80, 48), (70, 34), (60, 15), (60, 55), (55, 34), (45, 25), (45, 45), (35, 20), (35, 50)]
N = [(5, 34), (25, 20), (25, 48), (30, 34), (40, 10), (40, 58), (50, 30), (65, 22), (65, 46), (75, 34)]
im = frame(R, N, (75.5, 35))
ok(radar.find_radar(im) is not None, 'radar trouvé : %s' % (radar.find_radar(im),))
d = radar.read_frame(im, radar.find_radar(im))
ok(len(d['rouge']) == 11 and len(d['noir']) == 10, 'marques lues : %d rouges, %d noires' % (len(d['rouge']), len(d['noir'])))
ok(d['ballon'] and abs(d['ballon'][0] - 75.5) < 1.5 and abs(d['ballon'][1] - 35) < 1.5, 'ballon lu : %s' % (d['ballon'],))
err = max(min(abs(a - x) + abs(b - y) for a, b in d['noir']) for x, y in N)
ok(err < 2.5, 'précision des positions noires : écart max %.1f m' % err)

# --- sens d'attaque et gardien dans l'autre couleur ---
frames = [dict(t=i * 0.2, rouge=R, noir=N[1:], ballon=(75, 34)) for i in range(20)]   # notre gardien manquant chez les noirs
frames_gk = [dict(t=f['t'], rouge=R + [(12, 34)], noir=N[1:], ballon=f['ballon']) for f in frames]  # ... affiché en rouge, à 12 m (le leur est sur sa ligne)
ok(jeu.attack_right(frames_gk, 'noir') is True, 'sens : Nous (noir) attaque vers la droite malgré le gardien en rouge')
mir = [dict(t=f['t'], rouge=[(105 - x, 68 - y) for x, y in f['rouge']], noir=[(105 - x, 68 - y) for x, y in f['noir']], ballon=(30, 34)) for f in frames_gk]
ok(jeu.attack_right(mir, 'noir') is False, 'sens : terrain retourné → vers la gauche')
nf, right = jeu.normalize(mir, 'noir')
ok(right is False and any(abs(x - 12) < 0.1 for x, _ in nf[0]['N']), 'normalisation : retourné et gardien rendu à Nous')
ok(len(nf[0]['N']) == 10 and len(nf[0]['E']) == 11, 'gardien déplacé : %d Nous / %d Eux' % (len(nf[0]['N']), len(nf[0]['E'])))

# --- actions (mêmes types que le codage manuel) ---
GK_E, GK_N = (103, 34), (2, 34)


def seq(steps, n_extra=(), e_extra=()):
    """steps = liste de (ballon, porteurs N, porteurs E) image par image à 5 i/s."""
    out = []
    for i, (b, n, e) in enumerate(steps):
        out.append(dict(t=round(i * 0.2, 2), N=[GK_N] + list(n) + list(n_extra), E=[GK_E] + list(e) + list(e_extra), ballon=b))
    return out


def line(a, b, k):
    return [(a[0] + (b[0] - a[0]) * i / (k - 1), a[1] + (b[1] - a[1]) * i / (k - 1)) for i in range(k)]


def kinds(ev):
    return [(e['kind'], e['team'], e.get('ok')) for e in ev]


A, B = (40, 30), (55, 40)
far_e = [(80, 10), (80, 58)]
# 1. passe simple : A garde, le ballon file vers B qui attendait, B garde
st = [((40, 30), [A, B], far_e)] * 5 + [(p, [A, B], far_e) for p in line((40, 30), (55, 40), 5)[1:-1]] + [((55, 40), [A, B], far_e)] * 5
ev = jeu.actions(seq(st))
ok(kinds(ev) == [('pass', 'N', True)], 'passe réussie détectée %s' % kinds(ev))
# 2. même passe avec 4 adversaires entre les deux : passe de déséquilibre
mid_e = [(45, 15), (48, 50), (50, 25), (52, 60)]
st2 = [(b, n, list(e) + mid_e) for b, n, e in st]
ev = jeu.actions(seq(st2))
ok(kinds(ev) == [('pass_deseq', 'N', True)] and ev[0]['elim'] == 4, 'passe de déséquilibre (4 éliminés) %s' % [(e['kind'], e.get('elim')) for e in ev])
# 3. conduite : le porteur avance avec le ballon de 20 m, 3 adversaires dépassés
path = line((40, 30), (60, 30), 18)
st3 = [(p, [p], far_e + [(45, 20), (50, 45), (55, 25)]) for p in path]
ev = jeu.actions(seq(st3))
ok(kinds(ev) == [('carry_deseq', 'N', True)] and ev[0]['elim'] == 3, 'conduite de déséquilibre %s' % [(e['kind'], e.get('elim')) for e in ev])
# 4. passe interceptée : le ballon file vers un adversaire
C = (52, 34)
st4 = [((40, 30), [A], [C] + far_e)] * 5 + [(p, [A], [C] + far_e) for p in line((40, 30), C, 5)[1:-1]] + [(C, [A], [C] + far_e)] * 5
ev = jeu.actions(seq(st4))
ok(kinds(ev) == [('pass', 'N', False)], 'passe ratée (interceptée) %s' % kinds(ev))
# 5. duel perdu : ballon au pied, adversaire au contact, puis il repart avec
D, E2 = (50, 30), (51.5, 30)
st5 = [((50, 30), [D], [(58, 30)] + far_e)] * 5 + [((50.7, 30), [D], [E2] + far_e)] * 3 + [((53, 30), [D], [(53, 30)] + far_e)] * 5
ev = jeu.actions(seq(st5))
ok(kinds(ev) == [('perte', 'N', None)], 'duel perdu = E (perte) %s' % kinds(ev))
st5b = [((50, 30), [(58, 30)], [D] + far_e)] * 5 + [((50.7, 30), [E2], [D] + far_e)] * 3 + [((53, 30), [(53, 30)], [D] + far_e)] * 5
ev = jeu.actions(seq(st5b))
ok(kinds(ev) == [('recup', 'N', None)], 'duel gagné = Z (récup) %s' % kinds(ev))
# 6. frappe : ballon qui part vite vers le but adverse depuis 20 m
S = (85, 34)
st6 = [(S, [S], far_e)] * 5 + [(p, [S], far_e) for p in line(S, (104, 35), 5)[1:]]
ev = jeu.actions(seq(st6))
ok(('shot', 'N', None) in kinds(ev), 'frappe détectée %s' % kinds(ev))
ev = jeu.actions(seq(st), k1=0.5)
ok(ev[0]['t'] == int(round((ev[0]['video_s'] - 0.5) * 1000)), 'temps appli = (vidéo - k1) en ms')

# --- chaîne complète sur une petite vidéo fabriquée ---
tmp = tempfile.mkdtemp()
vp = os.path.join(tmp, 'essai.mp4')
vw = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*'mp4v'), 25, (1920, 1080))
for i in range(100):                                      # 4 s : le ballon passe d'un noir à l'autre
    bx = 50 + (65 - 50) * min(1, max(0, (i - 30) / 30))
    vw.write(frame(R, N, (bx, 30 if i < 45 else 22)))
vw.release()
sys.argv = ['analyser.py', vp, '--nous', 'noir', '--mi-temps', '1', '--sens', 'droite', '--sortie', os.path.join(tmp, 'out')]
analyser.main()
m = json.load(open(os.path.join(tmp, 'out', 'match_ia.json'), encoding='utf-8'))
ok(m['version'] == 2 and isinstance(m['matches'][0]['events'], list), 'match_ia.json au format sauvegarde de l\'appli (%d actions)' % len(m['matches'][0]['events']))
ok(all(e['src'] == 'ia' and 'id' in e for e in m['matches'][0]['events']), 'actions marquées src = ia, avec id')
ok(os.path.exists(os.path.join(tmp, 'out', 'rapport.png')), 'rapport.png créé')

# --- comparaison IA / codage manuel ---
import comparer  # noqa: E402
man = [dict(kind='pass', team='N', ok=True, video_s=11.5), dict(kind='recup', team='N', video_s=36.0), dict(kind='shot', team='N', video_s=49)]
iae = [dict(kind='pass', team='N', ok=True, video_s=10.0), dict(kind='recup', team='N', video_s=30.0), dict(kind='shot', team='N', video_s=50)]
pairs = comparer.match(man, iae, 4.0)
ok(sorted(pairs) == [(0, 0), (2, 2)], 'comparaison : 2 actions communes à ±4 s, la récup à 6 s d\'écart non appariée')

# --- note automatique sur un jeu de référence ---
import noter  # noqa: E402
refd = tempfile.mkdtemp()
r = os.path.join(refd, 'seq1')
os.makedirs(r)
json.dump([dict(t=f['t'], noir=f['N'], rouge=f['E'], ballon=f['ballon']) for f in seq(st)], open(os.path.join(r, 'radar_brut.json'), 'w'))
json.dump({'nous': 'noir', 'sens': 'droite', 'mi_temps': 1}, open(os.path.join(r, 'ref.json'), 'w'))
json.dump({'format': 'codage-live/actions-video', 'actions': [dict(kind='pass', team='N', ok=True, video_s=0.8)]}, open(os.path.join(r, 'codage.json'), 'w'))
g, sc = noter.note(refd, {}, quiet=True)
ok(g == 100, 'note automatique : passe codée retrouvée → 100 / 100 (%s)' % g)
g2, _ = noter.note(refd, {'min_pass': '30'}, quiet=True)
ok(g2 == 0 and os.path.exists(os.path.join(refd, 'historique.csv')), 'note avec réglage modifié (min_pass=30 → 0) + historique')
# --- nouveau radar Veo (panneau transparent, ronds jaunes / triangles noirs, croix orange) ---
def radar2_image(x, y, w, jaunes, noirs, ballon, W_=1920, H_=1080):
    img = np.zeros((H_, W_, 3), np.uint8); img[:] = (60, 120, 90)          # « vidéo » derrière
    h = w / radar.RATIO2
    X = lambda m: int(round(x + m / radar.L * w)); Y = lambda m: int(round(y + m / radar.W * h))  # noqa: E731
    pan = img[max(0, y):int(y + h), x:x + w].astype(np.float32)
    img[max(0, y):int(y + h), x:x + w] = (pan * 0.45).astype(np.uint8)     # panneau assombri
    g = (175, 175, 175)
    cv2.rectangle(img, (x, y), (x + w, int(y + h)), g, 1)
    cv2.line(img, (X(52.5), y), (X(52.5), int(y + h)), g, 1)
    cv2.circle(img, (X(52.5), Y(34)), int(radar.BOX2['circle'] * w), g, 1)
    d, bh = radar.BOX2['depth'] * radar.L, radar.BOX2['height'] * radar.W
    for a, b in ((0, d), (radar.L - d, radar.L)):
        cv2.rectangle(img, (X(a), Y(34 - bh / 2)), (X(b), Y(34 + bh / 2)), g, 1)
    r = int(radar.MARK2 * w / 2)
    for px, py in jaunes:
        cv2.circle(img, (X(px), Y(py)), r, (40, 240, 250), -1)
    for px, py in noirs:
        cx, cy = X(px), Y(py)
        tri = np.array([[cx, cy - r - 2], [cx - r - 1, cy + r], [cx + r + 1, cy + r]], np.int32)
        cv2.fillPoly(img, [tri], (12, 12, 12)); cv2.polylines(img, [tri], True, (235, 235, 235), 1)
    bx, by = X(ballon[0]), Y(ballon[1])
    cv2.line(img, (bx - r, by), (bx + r, by), (40, 110, 245), 3); cv2.line(img, (bx, by - r), (bx, by + r), (40, 110, 245), 3)
    return img


J2 = [(5, 34), (20, 15), (22, 50), (35, 30), (45, 10), (48, 58), (60, 25), (62, 45), (75, 20), (80, 50)]
N2 = [(100, 34), (85, 30), (88, 12), (70, 40), (55, 8), (52, 60), (40, 45), (30, 20), (28, 55), (15, 35)]
img2 = radar2_image(1100, -15, 466, J2, N2, (66, 34))
b2 = radar.find_radar2(img2)
ok(b2 is not None and abs(b2[0] - 1100) <= 4 and abs(b2[2] - 466) <= 8, 'nouveau radar trouvé (même coupé en haut) : %s' % (b2,))
d2 = radar.read_frame2(img2, b2) if b2 else dict(jaune=[], noir=[], ballon=None)
ok(len(d2['jaune']) == 10 and len(d2['noir']) == 10, 'nouveau radar : %d jaunes, %d noirs' % (len(d2['jaune']), len(d2['noir'])))
ok(d2['ballon'] is not None and abs(d2['ballon'][0] - 66) < 2.5 and abs(d2['ballon'][1] - 34) < 2.5, 'nouveau radar : ballon %s' % (d2['ballon'],))
fr2 = [dict(t=0, jaune=J2, noir=N2, ballon=(66, 34))]
ok(jeu.other(fr2, 'jaune') == 'noir' and jeu.other(fr2, 'noir') == 'jaune', 'adversaire = l\'autre couleur présente (jaune / noir)')

# --- sans radar : équipe d'après la couleur du maillot (images fabriquées) ---
import sans_radar  # noqa: E402
def joueur(maillot):
    im = np.zeros((60, 20, 3), np.uint8); im[:] = (60, 110, 20)              # pelouse bleu-vert
    im[8:34, 4:16] = maillot; im[34:46, 5:15] = (20, 20, 20)
    return sans_radar.team_of(im, (0, 0, 20, 60))
ok(joueur((20, 200, 230)) == 'jaune' and joueur((60, 30, 20)) == 'noir' and joueur((60, 110, 20)) == 'inconnu',
   'sans radar : maillot jaune / bleu marine / rien = %s / %s / %s' % (joueur((20, 200, 230)), joueur((60, 30, 20)), joueur((60, 110, 20))))

# --- sans radar : suivi de la caméra par le décor (image fabriquée, décalée de 40 px) ---
rng_ = np.random.default_rng(1)
deco = cv2.GaussianBlur((rng_.random((600, 900)) * 255).astype(np.uint8), (0, 0), 1.5)
deco = cv2.cvtColor(cv2.resize(deco, (1200, 800)), cv2.COLOR_GRAY2BGR)
a_, b_ = deco[100:640, 100:1060], deco[100:640, 140:1100]       # la caméra tourne : le décor glisse de 40 px
trk = sans_radar.CameraTracker()
Hab = trk.homography(trk.features(a_, []), trk.features(b_, []))
dx = sans_radar.project(Hab, [(480, 270)])[0][0] - 480 if Hab is not None else 99
ok(Hab is not None and abs(dx + 40) < 2, 'sans radar : mouvement de caméra retrouvé par le décor (%.1f px pour -40)' % dx)

# --- sans radar : nettoyage (faux ballon, spectateur, plus de 11 joueurs) ---
fv = [dict(t=i * 0.2, jaune=[(30 + i, 20)] + ([(50, -6)] if i == 2 else []), noir=[(60, 30)] * (13 if i == 0 else 1),
           ballon=(30 + i, 20) if i != 3 else (95, 60)) for i in range(8)]
cv = sans_radar.clean_brut(fv)
ok(cv[3]['ballon'] != (95, 60) and cv[3]['ballon'] is not None, 'sans radar : faux ballon (saut de 65 m) rejeté et comblé : %s' % (cv[3]['ballon'],))
ok(len(cv[2]['jaune']) == 1 and len(cv[0]['noir']) == 11, 'sans radar : spectateur hors terrain écarté, 11 joueurs max par équipe')

# --- sans radar : calage commun sur plusieurs images (vrai calage connu, départ faussé) ---
Gv = np.array([[0.06, 0.01, -20.0], [0.002, 0.11, -35.0], [0.0, 0.0006, 1.0]])       # image → terrain
Gi = np.linalg.inv(Gv)
smp = []
for k in range(6):
    pts = [(10 + 15 * j + 3 * k, 8 + (7 * j + 11 * k) % 52) for j in range(6)]
    img_pts = sans_radar.project(Gi, pts)
    pl = [dict(team='jaune' if j % 2 else 'noir', foot=tuple(img_pts[j])) for j in range(6)]
    smp.append((np.eye(3), pl, dict(jaune=[pts[j] for j in range(6) if j % 2], noir=[pts[j] for j in range(6) if not j % 2])))
G0 = Gv @ np.array([[1.01, 0, 6], [0, 0.99, -5], [0, 0, 1]])                         # départ faussé (~1 m)
Gc = sans_radar.calibrate_joint(G0, smp)
e_av = np.median([math.dist(a, b) for a, b in zip(sans_radar.project(G0, [p['foot'] for p in smp[0][1]]), sans_radar.project(Gv, [p['foot'] for p in smp[0][1]]))])
e_ap = np.median([math.dist(a, b) for a, b in zip(sans_radar.project(Gc, [p['foot'] for p in smp[0][1]]), sans_radar.project(Gv, [p['foot'] for p in smp[0][1]]))])
ok(e_ap < 0.05 < e_av, 'sans radar : calage commun retrouve le vrai calage (%.2f m → %.3f m)' % (e_av, e_ap))

# --- sans radar : le vrai ballon parmi de faux ballons plus « confiants » ---
tt = [i * 0.2 for i in range(20)]
vrai = [(20 + 1.5 * i, 30) for i in range(20)]                              # ballon qui roule à 7,5 m/s
cc = [[(vrai[i][0], vrai[i][1], 0.4), ((5, 60) if i % 2 else (90, 8)) + (0.6,)] for i in range(20)]   # leurres qui sautent
pth = sans_radar.ball_path(cc, tt)
bons = sum(1 for p, v in zip(pth, vrai) if p and math.dist(p, v) < 0.5)
ok(bons >= 18, 'sans radar : chemin cohérent du ballon malgré des leurres plus confiants (%d / 20 justes)' % bons)

# --- sans radar : calage du terrain par clics (caler.py) ---
import caler  # noqa: E402
rp = caler.reperes(longueur=90, largeur=55, surface=(13, 32), but=(4, 15))
ok(abs(rp[0][1] - 52.5) < 1e-9 and abs(rp[0][2] - 34) < 1e-9 and max(x for _, x, _ in rp) <= 105.001,
   'calage par clics : repères d\'un terrain 90 x 55 ramenés au repère du radar 105 x 68')
cl = [(n, tuple(sans_radar.project(Gi, [(x, y)])[0] + (0.5 if j == 3 else 0)), (x, y)) for j, (n, x, y) in enumerate(rp[:10])]
Gk, ec = caler.calculer(cl)
e = max(math.dist(a, b) for a, b in zip(sans_radar.project(Gk, [p['foot'] for p in smp[0][1]]), sans_radar.project(Gv, [p['foot'] for p in smp[0][1]])))
ok(e < 0.3 and len(ec) == 10, 'calage par clics : 10 repères retrouvent le calage (écart max %.2f m)' % e)
ok(caler.calculer(cl[:3])[0] is None, 'calage par clics : moins de 4 repères → pas de calage')

# --- auto-contrôle (mesures sans vérité) : lignes du terrain dessinées sur une pelouse de synthèse ---
import autocontrole  # noqa: E402
img = np.full((1080, 1920, 3), (100, 150, 90), np.uint8)                    # pelouse (BGR)
Lm = caler.lignes()
for pl in Lm:
    q = sans_radar.project(Gi, pl)
    cv2.polylines(img, [np.int32(q).reshape(-1, 1, 2)], False, (245, 245, 245), 3)
cv2.line(img, (0, 900), (1900, 700), (140, 40, 20), 3)                       # ligne BLEUE (foot à 8) : à ignorer
bl, zo = autocontrole.masques(img)
r_bon, n_bon = autocontrole.recouvrement(Gv, bl, zo, Lm)
r_mal, _ = autocontrole.recouvrement(np.array([[1, 0, 3], [0, 1, 0], [0, 0, 1.]]) @ Gv, bl, zo, Lm)
ok(n_bon > 100 and r_bon > 0.9 and r_mal < 0.5,
   'auto-contrôle : lignes du bon calage sur le blanc (%.2f), calage décalé de 3 m (%.2f)' % (r_bon, r_mal))
img2 = np.full((1080, 1920, 3), (100, 150, 90), np.uint8)
cv2.line(img2, (0, 900), (1900, 700), (245, 245, 245), 3)                    # la même, en blanc : vue
ok(not bl[395:406, 470:481].any() and autocontrole.masques(img2)[0][395:406, 470:481].any(),
   'auto-contrôle : ligne bleue ignorée, la même en blanc est vue')            # (950, 800) sur la ligne
vu, sauts = autocontrole.ballon([(10, 10), None, (12, 10), (90, 60)], [0, 0.2, 0.4, 0.6])
ok(abs(vu - 0.75) < 1e-9 and abs(sauts - 0.5) < 1e-9, 'auto-contrôle : ballon vu 75 %, 1 saut impossible sur 2')

# --- équipes trouvées seules (equipes.py) : jaunes au soleil ET à l'ombre, bleu marine, un arbitre ---
import equipes  # noqa: E402
rng = np.random.default_rng(0)


def _feat(L, a, b):
    return [L - 10, a - 3, b - 6, L, a, b, L + 10, a + 3, b + 6]


frs = [dict(players=[]) for _ in range(5)]
vrai = []
for i in range(60):
    soleil = i % 2 == 0
    if i < 25:
        f = _feat(200 if soleil else 110, 128 + rng.normal(0, 3), 128 + (65 if soleil else 45) + rng.normal(0, 4)); t = 'jaune'
    elif i < 55:
        f = _feat(60 if soleil else 35, 128 + rng.normal(0, 3), 128 - 22 + rng.normal(0, 4)); t = 'noir'
    else:
        f = _feat(180, 128 - 45, 128 + 50); t = 'arbitre'
    frs[i % 5]['players'].append(dict(team='?', feat=f)); vrai.append((frs[i % 5]['players'][-1], t))
info = equipes.assigner(frs, nous='jaune')
bons = sum(p['team'] == t for p, t in vrai if t != 'arbitre')
ok(info['ok'] and bons == 55, 'équipes : jaunes soleil + ombre et bleu marine bien séparés (%d / 55)' % bons)
ok(sans_radar.plausible(np.eye(3)) and not sans_radar.plausible(np.diag([20, 20, 1.0]))
   and not sans_radar.plausible(np.array([[1, 0, 0], [0, 1, 0], [-0.001, 0, 1.0]])),
   'décor : liens invraisemblables refusés (zoom × 20, image retournée)')

print('\n' + ('TOUT EST OK' if not FAIL else '%d ÉCHEC(S)' % len(FAIL)))
print('match_ia de test :', os.path.join(tmp, 'out', 'match_ia.json'))
sys.exit(1 if FAIL else 0)
