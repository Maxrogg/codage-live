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
# Le ballon du radar Veo est lissé : ses déplacements sont propres, alors que les joueurs sont placés à quelques
# mètres près. On part donc du BALLON : chaque « transfert » (ballon rapide sur au moins 5 m, dans une même
# direction) est une passe (ou une frappe) ; l'équipe qui a le ballon avant / après dit si elle est réussie.
CFG = dict(
    radius=4.0,       # m : un joueur à moins de ça du ballon peut en être le porteur
    contest=1.5,      # m : les deux équipes à moins de ça d'écart de distance → ballon disputé
    fast=8.5,         # m/s : au-dessus, le ballon voyage (passe, frappe) ; en dessous, il est au pied
    turn=50,          # degrés : changement de direction qui coupe deux transferts
    min_pass=4.0,     # m : déplacement minimal d'un transfert
    look=1.5,         # s : on cherche le porteur jusqu'à ça avant / après le transfert
    deseq=3,          # adversaires éliminés pour une passe de déséquilibre
    deseq_carry=2,    # adversaires éliminés pour une conduite de déséquilibre
    carry_min=10.0,   # m : conduite = le ballon avance d'au moins ça au pied de la même équipe
    shot_zone=35.0,   # m : frappe = transfert vers le but adverse qui part à moins de ça du but
    duel_s=3.0,       # s : changement d'équipe sans transfert, en moins de ça → duel
)


def _nearest(pts, b):
    best = None
    for p in pts:
        d = math.dist(p, b)
        if best is None or d < best[0]:
            best = (d, p)
    return best


def holder(f, cfg=CFG):
    """Équipe qui a le ballon sur cette image : 'N', 'E', 'duel' (disputé) ou None (personne à moins de radius)."""
    b = f['ballon']
    if not b:
        return None
    n, e = _nearest(f['N'], b), _nearest(f['E'], b)
    dn = n[0] if n else 99
    de = e[0] if e else 99
    if min(dn, de) > cfg['radius']:
        return None
    if dn <= cfg['radius'] and de <= cfg['radius'] and abs(dn - de) < cfg['contest'] and min(dn, de) >= 0.8:
        return 'duel'
    return 'N' if dn < de else 'E'


def transfers(frames, cfg=CFG):
    """Moments où le ballon voyage : liste de (i0, i1) = image de départ et d'arrivée."""
    out, cur = [], None
    H = [holder(f, cfg) for f in frames]
    for i in range(1, len(frames)):
        a, b = frames[i - 1]['ballon'], frames[i]['ballon']
        dt = frames[i]['t'] - frames[i - 1]['t']
        fast = bool(a and b and dt > 0 and math.dist(a, b) / dt >= cfg['fast'])
        if fast:
            head = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            if cur and (i - 1 == cur['i1'] or i - 2 == cur['i1']) and abs((head - cur['head'] + 180) % 360 - 180) <= cfg['turn']:
                cur['i1'] = i
            else:
                if cur:
                    out.append(cur)
                cur = dict(i0=i - 1, i1=i, head=head)
        elif cur and (i - cur['i1'] > 1 or H[i] in ('N', 'E')):
            # une image lente est tolérée dans un transfert, sauf si un joueur a le ballon (il l'a touché)
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [(c['i0'], c['i1']) for c in out
            if frames[c['i0']]['ballon'] and frames[c['i1']]['ballon']
            and math.dist(frames[c['i0']]['ballon'], frames[c['i1']]['ballon']) >= cfg['min_pass']]


def goal_side(f, team, bx):
    """Adversaires de `team` placés entre le ballon et leur but (sans leur gardien s'il est dans sa surface)."""
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
    """Actions au format de l'appli. Chaque action garde `video_s` (seconde de la vidéo) pour la vérifier dans
    l'onglet Vidéo, et `elim` (adversaires éliminés) pour les passes et conduites."""
    ev = []
    start = 0 if half == 1 else 45 * 60000
    H = [holder(f, cfg) for f in frames]

    def mk(kind, team, i, **kw):
        t = frames[i]['t']
        e = dict(kind=kind, team=team, t=int(round((t - k1) * 1000)) + start, half=half, src='ia', video_s=round(t, 1))
        e.update({k: (round(v, 1) if isinstance(v, float) else v) for k, v in kw.items()})
        ev.append(e)

    def ball(i):
        return frames[i]['ballon']

    def who(i, step, lo, hi):
        """Premier porteur net (N / E) en partant de l'image i dans le sens step, sans sortir de [lo, hi]
        ni dépasser `look` secondes."""
        t0, k = frames[i]['t'], i
        while lo <= k <= hi and abs(frames[k]['t'] - t0) <= cfg['look']:
            if H[k] in ('N', 'E'):
                return H[k], k
            k += step
        return None, None

    tr = transfers(frames, cfg)
    bounds = [-1] + [x for t in tr for x in t] + [len(frames)]
    # 1. transferts : passes réussies / ratées, frappes
    for n, (i0, i1) in enumerate(tr):
        lo = tr[n - 1][1] if n else 0
        hi = tr[n + 1][0] if n + 1 < len(tr) else len(frames) - 1
        team, _ = who(i0, -1, lo, i0)
        if team is None:                                  # personne au départ : le plus proche du ballon, à 8 m
            f = frames[i0]
            n_, e_ = _nearest(f['N'], ball(i0)), _nearest(f['E'], ball(i0))
            cands = [(d[0], t) for d, t in ((n_, 'N'), (e_, 'E')) if d and d[0] <= 8]
            team = min(cands)[1] if cands else None
        if team is None:
            continue
        after, _ = who(i1, 1, i1, hi)
        b0, b1 = ball(i0), ball(i1)
        gx = L if team == 'N' else 0.0
        toward = _fwd(team, b0, b1) > 0 and abs(b1[1] - b0[1]) <= 1.2 * abs(b1[0] - b0[0])
        end_goal = abs(b1[0] - gx) <= 8 and 20 <= b1[1] <= 48
        if toward and math.dist(b0, (gx, W / 2)) <= cfg['shot_zone'] and (end_goal or after is None):
            mk('shot', team, i0, x=b0[0], y=b0[1], res='hors')   # cadrée ou non : invisible sur le radar → à corriger
            continue
        el = eliminated(frames, i0, i1, team, b0, b1)
        if after == team:
            kind = 'pass_deseq' if el >= cfg['deseq'] and _fwd(team, b0, b1) > 0 else 'pass'
            mk(kind, team, i0, x=b0[0], y=b0[1], x2=b1[0], y2=b1[1], ok=True, elim=el)
        elif after is not None or b1[1] <= 2 or b1[1] >= W - 2 or b1[0] <= 1 or b1[0] >= L - 1:
            # récupérée par l'adversaire, ou ballon sorti du terrain : passe ratée
            mk('pass', team, i0, x=b0[0], y=b0[1], x2=b1[0], y2=b1[1], ok=False, elim=el)

    # 2. entre deux transferts (ballon au pied) : conduites et duels
    for n in range(len(bounds) // 2):
        lo, hi = bounds[2 * n] + 1, bounds[2 * n + 1] - 1
        if hi - lo < 1:
            continue
        held = [(k, H[k]) for k in range(lo, hi + 1) if H[k] in ('N', 'E')]
        # conduite : même équipe du début à la fin, le ballon avance
        if held and all(h == held[0][1] for _, h in held):
            team = held[0][1]
            b0, b1 = ball(held[0][0]), ball(held[-1][0])
            if _fwd(team, b0, b1) >= cfg['carry_min']:
                el = eliminated(frames, held[0][0], held[-1][0], team, b0, b1)
                if el >= cfg['deseq_carry']:
                    mk('carry_deseq', team, held[0][0], x=b0[0], y=b0[1], x2=b1[0], y2=b1[1], ok=True, elim=el)
        # duel : l'équipe change au pied (2 images de suite pour chaque équipe)
        runs = []
        for k, h in held:
            if runs and runs[-1][0] == h:
                runs[-1][2] = k
                runs[-1][3] += 1
            else:
                runs.append([h, k, k, 1])
        runs = [r for r in runs if r[3] >= 2]
        for a, b in zip(runs, runs[1:]):
            if a[0] != b[0] and frames[b[1]]['t'] - frames[a[2]]['t'] <= cfg['duel_s']:
                mk('recup' if b[0] == 'N' else 'perte', 'N', b[1], x=ball(b[1])[0], y=ball(b[1])[1])

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
