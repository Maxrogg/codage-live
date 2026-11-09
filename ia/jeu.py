"""Du radar (positions image par image) aux indicateurs de jeu et aux actions de l'application.

Entrée : liste de dict(t, rouge=[(x,y)], noir=[(x,y)], ballon=(x,y)|None) en mètres (repère du radar Veo).
Sortie : repère de l'application (105 x 68, Nous attaque vers la droite) et les MÊMES actions que le codage
manuel du coach, au format JSON de l'appli (src = 'ia') : passes réussies / ratées, passes et conduites de
déséquilibre, duels gagnés / perdus (Z / E), frappes. Rien d'autre (choix du coach, 9 nov.).
Tout est approximatif : le radar ne dit pas QUI est qui, seulement où sont les marques de chaque couleur.
"""
import math

L, W = 105.0, 68.0
OTHER = {'rouge': 'noir', 'noir': 'rouge'}


def _median(v):
    v = sorted(v)
    n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)


def attack_right(frames, nous):
    """Vrai si Nous attaque vers la droite du radar (= vers le but de droite vu depuis la caméra).
    Chaque équipe passe en moyenne plus de temps dans sa moitié : celle dont les marques sont le plus à gauche
    défend à gauche. Fiable sur une mi-temps, fragile sur un court extrait → toujours vérifiable (--sens).
    (Les gardiens ne servent pas : Veo les colore selon leur maillot, souvent dans la couleur de l'autre équipe.)"""
    xs = {t: [x for f in frames for x, _ in f[t]] for t in (nous, OTHER[nous])}
    if not xs[nous] or not xs[OTHER[nous]]:
        return True
    return _median(xs[nous]) <= _median(xs[OTHER[nous]])


def normalize(frames, nous, right=None):
    """Repère de l'appli : équipes N / E, Nous attaque vers la droite."""
    if right is None:
        right = attack_right(frames, nous)
    def tr(p):
        return (round(p[0], 2), round(p[1], 2)) if right else (round(L - p[0], 2), round(W - p[1], 2))
    out = []
    for f in frames:
        g = dict(t=f['t'], N=[tr(p) for p in f[nous]], E=[tr(p) for p in f[OTHER[nous]]],
                 ballon=tr(f['ballon']) if f.get('ballon') else None)
        fix_keepers(g)
        out.append(g)
    return out, right


def in_box(p, team):
    """Dans la surface de réparation que défend `team` (N défend à gauche, E à droite)."""
    x, y = p
    return 13.84 <= y <= 54.16 and (x <= 16.5 if team == 'N' else x >= L - 16.5)


def fix_keepers(f):
    """Gardien affiché dans la couleur de l'autre équipe (maillot de gardien) : si une équipe n'a personne
    dans sa surface et que l'autre y a une seule marque, cette marque est rendue à l'équipe qui défend."""
    for team, other in (('N', 'E'), ('E', 'N')):
        if any(in_box(p, team) for p in f[team]):
            continue
        cand = [p for p in f[other] if in_box(p, team)]
        if len(cand) == 1:
            f[other] = [p for p in f[other] if p is not cand[0]]
            f[team] = f[team] + [cand[0]]
            f.setdefault('gk_fix', []).append(team)


def fill_ball(frames, max_gap=2.0):
    """Ballon manquant : interpolé entre deux positions connues si le trou dure moins de max_gap secondes."""
    known = [i for i, f in enumerate(frames) if f['ballon']]
    for a, b in zip(known, known[1:]):
        ta, tb = frames[a]['t'], frames[b]['t']
        if b - a > 1 and tb - ta <= max_gap:
            (xa, ya), (xb, yb) = frames[a]['ballon'], frames[b]['ballon']
            for i in range(a + 1, b):
                r = (frames[i]['t'] - ta) / (tb - ta)
                frames[i]['ballon'] = (round(xa + r * (xb - xa), 2), round(ya + r * (yb - ya), 2))
                frames[i]['interp'] = True
    return frames



# ---------------- détection des actions ----------------
CFG = dict(
    radius=4.0,      # m : un joueur à moins de ça du ballon peut en être le porteur
    contest=1.5,     # m : si les deux équipes sont à moins de ça d'écart de distance → ballon disputé (duel)
    fly=11.0,        # m/s : ballon plus rapide = en l'air / en passe, personne ne le porte
    hold=2,          # images de suite (à 5 i/s) pour confirmer un porteur
    min_pass=5.0,    # m : le porteur a changé de place d'au moins ça → passe (même équipe)
    max_pass_s=6.0,  # s : au-delà, on ne relie plus deux possessions par une passe
    deseq=3,         # adversaires éliminés pour une passe de déséquilibre
    deseq_carry=2,   # adversaires éliminés pour une conduite de déséquilibre
    carry_min=10.0,  # m : conduite = le ballon avance d'au moins ça avec la même équipe, sans passe
    shot_speed=12.0, # m/s : frappe = ballon rapide vers le but adverse...
    shot_zone=35.0,  # m : ...partant à moins de ça du but
)


def ball_speed(frames):
    """Vitesse du ballon (m/s) à chaque image, lissée (médiane sur 3 images). None si inconnue."""
    v = [None] * len(frames)
    for i in range(1, len(frames)):
        a, b = frames[i - 1]['ballon'], frames[i]['ballon']
        dt = frames[i]['t'] - frames[i - 1]['t']
        if a and b and dt > 0:
            v[i] = math.dist(a, b) / dt
    out = []
    for i in range(len(v)):
        w = [x for x in v[max(0, i - 1):i + 2] if x is not None]
        out.append(_median(w) if w else None)
    return out


def _nearest(pts, b):
    best = None
    for p in pts:
        d = math.dist(p, b)
        if best is None or d < best[0]:
            best = (d, p)
    return best


def states(frames, cfg=CFG):
    """État du ballon à chaque image : 'N' / 'E' (porté), 'duel', 'vol' (en l'air / passe), 'libre', None (pas vu).
    Renvoie aussi le porteur (position) quand il y en a un."""
    sp = ball_speed(frames)
    out = []
    for f, v in zip(frames, sp):
        b = f['ballon']
        if not b:
            out.append((None, None))
            continue
        n, e = _nearest(f['N'], b), _nearest(f['E'], b)
        dn = n[0] if n else 99
        de = e[0] if e else 99
        if min(dn, de) < 0.8:                             # marque sous la croix : Veo met le ballon sur ce joueur
            out.append(('N', n[1]) if dn < de else ('E', e[1]))
            continue
        if v is not None and v > cfg['fly']:
            out.append(('vol', None))
            continue
        if min(dn, de) > cfg['radius']:
            out.append(('libre', None))
        elif dn <= cfg['radius'] and de <= cfg['radius'] and abs(dn - de) < cfg['contest']:
            out.append(('duel', None))
        else:
            out.append(('N', n[1]) if dn < de else ('E', e[1]))
    return out


def segments(frames, st, cfg=CFG):
    """Moments où une équipe porte le ballon (au moins `hold` images de suite).
    Chaque segment : équipe, première / dernière image, porteur au début / à la fin, et ce qui s'est passé juste avant
    (vol = ballon en l'air, duel = ballon disputé)."""
    segs, i, n = [], 0, len(st)
    while i < n:
        team = st[i][0]
        if team in ('N', 'E'):
            j = i
            while j + 1 < n and st[j + 1][0] == team:
                j += 1
            if j - i + 1 >= cfg['hold']:
                segs.append(dict(team=team, i0=i, i1=j, p0=st[i][1], p1=st[j][1]))
            i = j + 1
        else:
            i += 1
    for a, b in zip(segs, segs[1:]):
        between = [st[k][0] for k in range(a['i1'] + 1, b['i0'])]
        b['avant'] = 'vol' if 'vol' in between else ('duel' if 'duel' in between else ('rien' if not between else 'autre'))
    return segs


def goal_side(f, team, bx):
    """Adversaires de `team` placés entre le ballon et leur but (gardien compris s'il est dans sa surface : on l'enlève)."""
    if team == 'N':
        opp = [p for p in f['E'] if not (in_box(p, 'E') and p[0] > L - 6)]
        return sum(1 for p in opp if p[0] > bx)
    opp = [p for p in f['N'] if not (in_box(p, 'N') and p[0] < 6)]
    return sum(1 for p in opp if p[0] < bx)


def eliminated(frames, i0, i1, team, b0, b1):
    """Adversaires éliminés entre deux moments : devant le ballon avant, derrière après."""
    return goal_side(frames[i0], team, b0[0]) - goal_side(frames[i1], team, b1[0])


def _fwd(team, a, b):
    return (b[0] - a[0]) if team == 'N' else (a[0] - b[0])


def actions(frames, k1=0.0, half=1, cfg=CFG):
    """Actions au format de l'appli, déduites des positions. Chaque action garde `elim` (adversaires éliminés) et
    `video_s` (seconde de la vidéo) pour pouvoir la vérifier dans l'onglet Vidéo."""
    st = states(frames, cfg)
    segs = segments(frames, st, cfg)
    sp = ball_speed(frames)
    ev = []
    start = 0 if half == 1 else 45 * 60000

    def mk(kind, team, i, **kw):
        t = frames[i]['t']
        e = dict(kind=kind, team=team, t=int(round((t - k1) * 1000)) + start, half=half, src='ia', video_s=round(t, 1))
        e.update({k: (round(v, 1) if isinstance(v, float) else v) for k, v in kw.items()})
        ev.append(e)

    def ball(i):
        return frames[i]['ballon']

    # Une possession (« run ») = segments de la même équipe dont le porteur ne change pas (ballon perdu de vue
    # un instant, adversaire proche...). Une passe = changement de porteur entre deux runs de la même équipe.
    def pass_like(r, sg):
        """Passe si, au départ du ballon, un coéquipier attendait déjà près du point d'arrivée.
        Sinon c'est le porteur qui a couru avec le ballon : conduite."""
        ba, bb = ball(r['i1']), ball(sg['i0'])
        d = math.dist(ba, bb)
        if d < cfg['min_pass']:
            return False
        mates = [p for p in frames[r['i1']][r['team']] if math.dist(p, ba) > 2.0]
        return any(math.dist(p, bb) <= max(5.0, 0.4 * d) for p in mates)

    runs = []
    for sg in segs:
        r = runs[-1] if runs else None
        if r and r['team'] == sg['team'] and frames[sg['i0']]['t'] - frames[r['i1']]['t'] <= cfg['max_pass_s'] \
                and (math.dist(r['p1'], sg['p0']) < cfg['min_pass'] or not pass_like(r, sg)):
            r.update(i1=sg['i1'], p1=sg['p1'])
        else:
            runs.append(dict(sg))

    for r in runs:                                        # conduite : le ballon avance avec le même porteur
        b0, b1 = ball(r['i0']), ball(r['i1'])
        if _fwd(r['team'], b0, b1) >= cfg['carry_min']:
            el = eliminated(frames, r['i0'], r['i1'], r['team'], b0, b1)
            if el >= cfg['deseq_carry']:
                mk('carry_deseq', r['team'], r['i0'], x=b0[0], y=b0[1], x2=b1[0], y2=b1[1], ok=True, elim=el)

    for a, b in zip(runs, runs[1:]):
        ba, bb = ball(a['i1']), ball(b['i0'])
        dt = frames[b['i0']]['t'] - frames[a['i1']]['t']
        if a['team'] == b['team']:
            if dt <= cfg['max_pass_s']:
                el = eliminated(frames, a['i1'], b['i0'], a['team'], ba, bb)
                kind = 'pass_deseq' if el >= cfg['deseq'] and _fwd(a['team'], ba, bb) > 0 else 'pass'
                mk(kind, a['team'], a['i1'], x=ba[0], y=ba[1], x2=bb[0], y2=bb[1], ok=True, elim=el)
        elif b.get('avant') == 'vol' and dt <= cfg['max_pass_s']:
            # le ballon a voyagé puis l'adversaire l'a : passe ratée (l'appli en déduit la perte / la récup)
            el = eliminated(frames, a['i1'], b['i0'], a['team'], ba, bb)
            mk('pass', a['team'], a['i1'], x=ba[0], y=ba[1], x2=bb[0], y2=bb[1], ok=False, elim=el)
        elif dt <= 3.0:
            # ballon disputé puis changement d'équipe : duel. Gagné par Nous = Z (recup), perdu = E (perte).
            mk('recup' if b['team'] == 'N' else 'perte', 'N', b['i0'], x=bb[0], y=bb[1])

    # frappes : ballon qui part vite vers le but adverse depuis moins de shot_zone m
    last_shot = -99
    for i in range(1, len(frames)):
        v, b0, b1 = sp[i], ball(i - 1), ball(i)
        if v is None or not b0 or not b1 or v < cfg['shot_speed'] or frames[i]['t'] - last_shot < 3:
            continue
        team = st[i - 1][0] if st[i - 1][0] in ('N', 'E') else None
        if team is None:                                  # tireur : dernière équipe à avoir eu le ballon
            prev = [s for s in segs if s['i1'] < i]
            team = prev[-1]['team'] if prev else None
        if not team:
            continue
        gx = L if team == 'N' else 0.0
        dist_goal = math.dist(b0, (gx, W / 2))
        toward = _fwd(team, b0, b1) > 0 and abs((b1[1] - b0[1]) / max(1e-6, abs(b1[0] - b0[0]))) < 1.2
        if dist_goal <= cfg['shot_zone'] and toward:
            mk('shot', team, i - 1, x=b0[0], y=b0[1], res='hors')   # cadrée ou non : invisible sur le radar → à corriger
            last_shot = frames[i]['t']
    ev.sort(key=lambda e: e['t'])
    return ev


def summary(frames, ev):
    """Comptes des actions détectées, dans les termes de l'appli."""
    def c(team, f):
        return sum(1 for e in ev if e['team'] == team and f(e))
    res = {}
    for team in ('N', 'E'):
        res[team] = dict(
            passes_reussies=c(team, lambda e: e['kind'] in ('pass', 'pass_deseq') and e['ok']),
            passes_ratees=c(team, lambda e: e['kind'] == 'pass' and not e['ok']),
            passes_deseq=c(team, lambda e: e['kind'] == 'pass_deseq'),
            conduites_deseq=c(team, lambda e: e['kind'] == 'carry_deseq'),
            frappes=c(team, lambda e: e['kind'] == 'shot'))
    res['duels'] = dict(gagnes=c('N', lambda e: e['kind'] == 'recup'), perdus=c('N', lambda e: e['kind'] == 'perte'))
    balls = sum(1 for f in frames if f['ballon'])
    return dict(images=len(frames), duree_s=round(frames[-1]['t'] - frames[0]['t'], 1) if frames else 0,
                ballon_vu_pct=round(100 * balls / max(1, len(frames))), actions=res, total=len(ev))
