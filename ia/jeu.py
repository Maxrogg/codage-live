"""Du radar (positions image par image) aux indicateurs de jeu et aux actions de l'application.

Entrée : liste de dict(t, rouge=[(x,y)], noir=[(x,y)], ballon=(x,y)|None) en mètres (repère du radar Veo).
Sortie : repère de l'application (105 x 68, Nous attaque vers la droite), indicateurs collectifs,
possession, et actions (récupérations, pertes, passes) au format JSON de l'appli (src = 'ia').
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
    """Vrai si Nous attaque vers la droite du radar.
    Repère le gardien le plus évident : la marque (des deux couleurs) qui reste le plus près d'une ligne de but.
    Attention : Veo colore les gardiens selon leur maillot ; un gardien peut avoir la couleur de l'autre équipe.
    On garde donc la plus petite des 4 distances médianes (Nous/Eux x but gauche/droit)."""
    other = OTHER[nous]
    d = {}
    for team in (nous, other):
        lft, rgt = [], []
        for f in frames:
            p = f[team]
            if len(p) >= 5:
                xs = [x for x, _ in p]
                lft.append(min(xs))
                rgt.append(L - max(xs))
        if lft:
            d[(team, 'g')] = _median(lft)
            d[(team, 'd')] = _median(rgt)
    if not d:
        return True
    team, side = min(d, key=d.get)
    defends_left = (side == 'g') == (team == nous)       # côté défendu par Nous
    return defends_left


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


def _hull_area(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return 0.0
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    h = lo[:-1] + hi[:-1]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2


def shape(pts, team):
    """Bloc d'une équipe sur une image (sans le gardien = la marque la plus proche de son but)."""
    if len(pts) < 5:
        return None
    own = 0.0 if team == 'N' else L                        # but défendu
    gk = min(pts, key=lambda p: abs(p[0] - own))
    out = [p for p in pts if p is not gk] if in_box(gk, team) else list(pts)   # gardien retiré s'il est dans sa surface
    xs = sorted(p[0] for p in out)
    ys = [p[1] for p in out]
    depth = (lambda x: x) if team == 'N' else (lambda x: L - x)   # distance à son propre but
    d = sorted(depth(x) for x in xs)
    return dict(hauteur=round(sum(d) / len(d), 1),          # hauteur moyenne du bloc (m depuis son but)
                ligne_def=round(d[1] if len(d) > 3 else d[0], 1),  # 2e joueur le plus bas (le 1er peut être isolé)
                largeur=round(max(ys) - min(ys), 1),
                longueur=round(d[-1] - d[0], 1),
                surface=round(_hull_area(out)))


def possession(frames, radius=4.0, min_frames=2):
    """Équipe en possession à chaque image : marque la plus proche du ballon à moins de `radius` m,
    confirmée sur `min_frames` images de suite. Renvoie la liste (t, équipe|None, joueur (x,y)|None, ballon)."""
    raw = []
    for f in frames:
        b, best = f['ballon'], None
        if b:
            for team in ('N', 'E'):
                for p in f[team]:
                    d = math.dist(p, b)
                    if d <= radius and (best is None or d < best[0]):
                        best = (d, team, p)
        raw.append((f['t'], best[1] if best else None, best[2] if best else None, b))
    out, cur, run = [], None, 0
    for i, (t, team, p, b) in enumerate(raw):
        if team and team != cur:
            nxt = [r[1] for r in raw[i:i + min_frames]]
            if len(nxt) == min_frames and all(x == team for x in nxt):
                cur = team
        out.append((t, cur, p if team == cur else None, b))
    return out


def actions(poss, k1=0.0, half=1, min_pass=6.0):
    """Actions au format de l'appli à partir de la possession.
    - changement d'équipe en possession → récupération de la nouvelle équipe (+ perte de l'autre, déduite par l'appli)
    - même équipe, porteur à plus de `min_pass` m du précédent → passe réussie (départ → arrivée)
    t = chrono de l'appli en ms (vidéo - k1), video_s = seconde dans la vidéo."""
    ev, last_team, last_p, last_t = [], None, None, None
    start = 0 if half == 1 else 45 * 60000
    def mk(kind, team, t, **kw):
        e = dict(kind=kind, team=team, t=int(round((t - k1) * 1000)) + start, half=half, src='ia', video_s=round(t, 1))
        e.update(kw)
        ev.append(e)
    for t, team, p, b in poss:
        if not team or not p:
            continue
        if last_team and team != last_team:
            mk('recup', team, t, x=round(b[0], 1), y=round(b[1], 1))
        elif last_team == team and last_p and math.dist(p, last_p) >= min_pass and t - last_t <= 6:
            mk('pass', team, last_t, x=round(last_p[0], 1), y=round(last_p[1], 1), x2=round(p[0], 1), y2=round(p[1], 1), ok=True)
        last_team, last_p, last_t = team, p, t
    return ev


def summary(frames, poss):
    """Moyennes sur la séquence : blocs des deux équipes, possession, zones du ballon."""
    acc = {'N': [], 'E': []}
    for f in frames:
        for team in ('N', 'E'):
            s = shape(f[team], team)
            if s:
                acc[team].append(s)
    def mean(team, k):
        v = [s[k] for s in acc[team]]
        return round(sum(v) / len(v), 1) if v else None
    blocs = {team: {k: mean(team, k) for k in ('hauteur', 'ligne_def', 'largeur', 'longueur', 'surface')} for team in ('N', 'E')}
    known = [p[1] for p in poss if p[1]]
    pos = {team: round(100 * known.count(team) / len(known)) if known else None for team in ('N', 'E')}
    balls = [f['ballon'] for f in frames if f['ballon']]
    tiers = [0, 0, 0]
    for x, _ in balls:
        tiers[min(2, int(x / (L / 3)))] += 1
    tot = sum(tiers) or 1
    return dict(images=len(frames), duree_s=round(frames[-1]['t'] - frames[0]['t'], 1) if frames else 0,
                ballon_vu_pct=round(100 * len(balls) / max(1, len(frames))),
                possession_pct=pos, blocs=blocs,
                ballon_par_tiers_pct=dict(notre_tiers=round(100 * tiers[0] / tot), milieu=round(100 * tiers[1] / tot), tiers_adverse=round(100 * tiers[2] / tot)))
