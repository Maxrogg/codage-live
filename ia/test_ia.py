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

# --- possession et actions ---
seq = []
car = [(60, 30)] * 5 + [(75, 40)] * 5 + [(80, 20)] * 5          # Nous : porteur 1, passe vers porteur 2 ; puis Eux récupère
for i, b in enumerate(car):
    n = [(5, 34), (60, 30), (75, 40), (40, 20), (40, 50)]
    e = [(100, 34), (80, 20), (90, 30), (90, 40), (85, 50)]
    seq.append(dict(t=round(i * 0.2, 2), N=n, E=e, ballon=b))
po = jeu.possession(seq)
ok(po[2][1] == 'N' and po[-1][1] == 'E', 'possession : Nous puis Eux')
ev = jeu.actions(po, k1=0.5)
kinds = [(e['kind'], e['team']) for e in ev]
ok(kinds == [('pass', 'N'), ('recup', 'E')], 'actions : passe de Nous puis récup d\'Eux %s' % kinds)
ok(ev[0]['x'] == 60 and ev[0]['x2'] == 75 and ev[0]['ok'] is True, 'passe : départ / arrivée corrects')
ok(ev[1]['t'] == int(round((ev[1]['video_s'] - 0.5) * 1000)), 'temps appli = (vidéo - k1) en ms')
s = jeu.shape(seq[0]['N'], 'N')
ok(s and s['largeur'] == 30 and s['ligne_def'] == 40, 'bloc : largeur %s, ligne déf. %s (gardien retiré)' % (s['largeur'], s['ligne_def']))

# --- chaîne complète sur une petite vidéo fabriquée ---
tmp = tempfile.mkdtemp()
vp = os.path.join(tmp, 'essai.mp4')
vw = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*'mp4v'), 25, (1920, 1080))
for i in range(100):                                      # 4 s : le ballon passe d'un noir à l'autre
    bx = 50 + (65 - 50) * min(1, max(0, (i - 30) / 30))
    vw.write(frame(R, N, (bx, 30 if i < 45 else 22)))
vw.release()
sys.argv = ['analyser.py', vp, '--nous', 'noir', '--sortie', os.path.join(tmp, 'out')]
analyser.main()
m = json.load(open(os.path.join(tmp, 'out', 'match_ia.json'), encoding='utf-8'))
ok(m['version'] == 2 and m['matches'][0]['events'], 'match_ia.json au format sauvegarde de l\'appli (%d actions)' % len(m['matches'][0]['events']))
ok(all(e['src'] == 'ia' and 'id' in e for e in m['matches'][0]['events']), 'actions marquées src = ia, avec id')
ok(os.path.exists(os.path.join(tmp, 'out', 'rapport.png')), 'rapport.png créé')
print('\n' + ('TOUT EST OK' if not FAIL else '%d ÉCHEC(S)' % len(FAIL)))
print('match_ia de test :', os.path.join(tmp, 'out', 'match_ia.json'))
sys.exit(1 if FAIL else 0)
