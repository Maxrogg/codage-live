"""Tests du module d'analyse (sans vidéo réelle) : python test_ia.py
Fabrique des images de radar façon Veo, puis vérifie lecture, sens, gardien, possession, actions, format appli."""
import json
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
print('\n' + ('TOUT EST OK' if not FAIL else '%d ÉCHEC(S)' % len(FAIL)))
print('match_ia de test :', os.path.join(tmp, 'out', 'match_ia.json'))
sys.exit(1 if FAIL else 0)
