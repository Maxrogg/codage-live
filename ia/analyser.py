"""Analyse automatique d'une vidéo Veo enregistrée avec le radar 2D affiché.
Elle détecte les MÊMES actions que le codage manuel : passes réussies / ratées, passes et conduites de déséquilibre,
duels gagnés / perdus (Z / E), frappes. Résultat importable dans l'appli de codage.

Le plus simple (Windows) : glisser la vidéo sur « analyser.bat ».
En ligne de commande :
    python analyser.py "C:\\chemin\\match.mp4" --nous noir
Options :
    --nous noir|rouge   marques du radar qui sont Nous (ronds noirs ou triangles rouges). Sans l'option : question posée.
    --fps 5             images analysées par seconde (5 suffit).
    --k1 0              seconde de la vidéo où le chrono de l'appli vaut 00:00 (voir onglet Vidéo de l'appli).
    --mi-temps 1        mi-temps de la vidéo (1 ou 2).
    --sens auto|droite|gauche   sens d'attaque de Nous sur le radar (auto = repéré grâce aux gardiens).
    --ouvrir            ouvre le dossier des résultats à la fin.
Sortie (dossier « resultats_<nom de la vidéo> », à côté de la vidéo) :
    match_ia.json       à importer dans l'appli (Codage > Données et sauvegardes > Importer une sauvegarde)
    rapport.png         image de synthèse
    resume.json         les comptes
    positions.json      positions image par image (pour vérifier / aller plus loin)
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import radar  # noqa: E402
import jeu    # noqa: E402

NC, EC, KO = '#2563eb', '#ea580c', '#dc2626'


def app_match(name, events, k1, half):
    """Match au format de sauvegarde de l'appli (importable tel quel)."""
    evs = []
    for i, e in enumerate(events, 1):
        e = dict(e)
        e['id'] = i
        evs.append(e)
    mid = 'ia-' + ''.join(c if c.isalnum() else '-' for c in name)[:40]
    return dict(version=2, matches=[dict(
        id=mid, info=dict(adv='IA – ' + name, date=time.strftime('%Y-%m-%d'), sn=None, se=None),
        events=evs, seq=len(evs),
        meta=dict(half=half, elapsed=0, flip=False, video=dict(name=name, k1=k1 if half == 1 else None, k2=k1 if half == 2 else None)),
        upd=int(time.time() * 1000))])


def _pitch(ax, plt):
    ax.set_xlim(-2, 107); ax.set_ylim(70, -2); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(plt.Rectangle((0, 0), 105, 68, color='#e8f0e4', zorder=0))
    for args in [((0, 0), 105, 68), ((0, 13.84), 16.5, 40.32), ((88.5, 13.84), 16.5, 40.32)]:
        ax.add_patch(plt.Rectangle(*args, fill=False, ec='#9aa59a', lw=1))
    ax.plot([52.5, 52.5], [0, 68], c='#9aa59a', lw=1)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, ec='#9aa59a', lw=1))


def _draw(ax, e):
    col = NC if e['team'] == 'N' else EC
    k = e['kind']
    if k in ('pass', 'pass_deseq', 'carry_deseq'):
        c = col if e['ok'] else KO
        lw = 2.4 if k != 'pass' else 1.1
        ax.annotate('', xy=(e['x2'], e['y2']), xytext=(e['x'], e['y']),
                    arrowprops=dict(arrowstyle='->', color=c, lw=lw, ls=':' if k == 'carry_deseq' else '-'))
    elif k == 'recup':
        ax.scatter([e['x']], [e['y']], marker='^', s=60, c=NC, zorder=4)
    elif k == 'perte':
        ax.scatter([e['x']], [e['y']], marker='x', s=60, c=KO, zorder=4, lw=2)
    elif k == 'shot':
        ax.scatter([e['x']], [e['y']], marker='o', s=70, facecolors='none', edgecolors=col, lw=2, zorder=4)


def rapport(path, ev, summ, titre):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('(matplotlib absent : pas d\'image de rapport — pip install matplotlib)')
        return
    fig = plt.figure(figsize=(13, 6.6), dpi=110)
    fig.suptitle(titre + ' — actions détectées automatiquement (à vérifier dans l\'onglet Vidéo)', x=0.02, ha='left', fontsize=11)
    for k, (team, nom) in enumerate((('N', 'Nous'), ('E', 'Eux'))):
        ax = fig.add_axes([0.02 + k * 0.33, 0.2, 0.31, 0.62])
        _pitch(ax, plt)
        for e in ev:
            if (e['team'] == team and e['kind'] not in ('recup', 'perte')) or (team == 'N' and e['kind'] in ('recup', 'perte')):
                _draw(ax, e)
        ax.set_title(nom + (' (+ duels Z / E)' if team == 'N' else ''), color=NC if team == 'N' else EC, fontsize=10, loc='left')
        ax.annotate('', xy=(70, 72), xytext=(35, 72), arrowprops=dict(arrowstyle='->', color=NC), annotation_clip=False)
        ax.text(52.5, 76, 'Nous attaquons →', ha='center', color=NC, fontsize=8)
    leg = fig.add_axes([0.02, 0.02, 0.64, 0.1]); leg.axis('off')
    leg.text(0, 0.6, 'Flèche fine = passe réussie · épaisse = passe de déséquilibre · pointillés épais = conduite de déséquilibre · '
             'rouge = passe ratée · ▲ duel gagné (Z) · ✕ duel perdu (E) · ○ frappe', fontsize=8.5, color='#444')
    ax3 = fig.add_axes([0.70, 0.08, 0.28, 0.8]); ax3.axis('off')
    a = summ['actions']
    rows = [('Passes réussies', 'passes_reussies'), ('Passes ratées', 'passes_ratees'), ('Passes de déséquilibre', 'passes_deseq'),
            ('Conduites de déséquilibre', 'conduites_deseq'), ('Frappes', 'frappes')]
    y = 0.95
    ax3.text(0, y, 'Comptes détectés', fontsize=11, weight='bold'); y -= 0.07
    ax3.text(0.66, y, 'Nous', color=NC, weight='bold'); ax3.text(0.86, y, 'Eux', color=EC, weight='bold'); y -= 0.06
    for lab, key in rows:
        ax3.text(0, y, lab, fontsize=9.5); ax3.text(0.66, y, str(a['N'][key]), fontsize=9.5); ax3.text(0.86, y, str(a['E'][key]), fontsize=9.5); y -= 0.055
    ax3.text(0, y, 'Duels (Z / E)', fontsize=9.5); ax3.text(0.66, y, '%d gagnés / %d perdus' % (a['duels']['gagnes'], a['duels']['perdus']), fontsize=9.5); y -= 0.09
    ax3.text(0, y, 'Ballon vu sur %s %% des images · %s s analysées' % (summ['ballon_vu_pct'], summ['duree_s']), fontsize=8.5, color='#666', va='top'); y -= 0.06
    ax3.text(0, y, 'Lu sur le radar Veo : un pré-codage, pas une vérité.\nFrappes notées « non cadrées » par défaut\n(le radar ne montre pas le cadre).', fontsize=8, color='#666', va='top')
    fig.savefig(path)
    plt.close(fig)


def ask(q, choices, default):
    """Question dans la fenêtre (double-clic). Entrée = valeur par défaut."""
    try:
        r = input('%s [%s] (Entrée = %s) : ' % (q, '/'.join(choices), default)).strip().lower()
    except EOFError:
        return default
    return r if r in choices else default


def main():
    ap = argparse.ArgumentParser(description='Analyse automatique d\'une vidéo Veo (radar 2D).')
    ap.add_argument('video')
    ap.add_argument('--nous', default=None, choices=['noir', 'rouge'])
    ap.add_argument('--fps', type=float, default=5)
    ap.add_argument('--k1', type=float, default=0)
    ap.add_argument('--mi-temps', dest='half', type=int, default=None, choices=[1, 2])
    ap.add_argument('--sens', default='auto', choices=['auto', 'droite', 'gauche'])
    ap.add_argument('--sortie', default=None)
    ap.add_argument('--ouvrir', action='store_true')
    a = ap.parse_args()
    if not os.path.exists(a.video):
        raise SystemExit('Vidéo introuvable : ' + a.video)
    interactive = sys.stdin is not None and sys.stdin.isatty()
    if a.nous is None:
        a.nous = ask('Nous = quelles marques du radar ? noir = ronds noirs, rouge = triangles rouges', ['noir', 'rouge'], 'noir') if interactive else 'noir'
    if a.half is None:
        a.half = int(ask('Quelle mi-temps ?', ['1', '2'], '1')) if interactive else 1

    name = os.path.splitext(os.path.basename(a.video))[0]
    outdir = a.sortie or os.path.join(os.path.dirname(os.path.abspath(a.video)), 'resultats_' + name)
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    last = [0]

    def prog(r):
        if r - last[0] >= 0.02:
            last[0] = r
            print('  lecture de la vidéo : %d %%' % (100 * r), end='\r', flush=True)
    raw = radar.read_video(a.video, fps=a.fps, progress=prog)
    print()
    if not raw:
        raise SystemExit('Radar Veo introuvable : enregistre la vidéo avec le radar 2D affiché en haut à droite.')
    right = None if a.sens == 'auto' else (a.sens == 'droite')
    if right is None:
        guess = jeu.attack_right(raw, a.nous)
        if interactive:
            r = ask('Sens d\'attaque de Nous dans cette vidéo, vu depuis la caméra (vers le but de droite ou de gauche) ?',
                    ['droite', 'gauche'], 'droite' if guess else 'gauche')
            right = r == 'droite'
        else:
            right = guess
    frames, right = jeu.normalize(raw, a.nous, right)
    frames = jeu.fill_ball(frames)
    ev = jeu.actions(frames, k1=a.k1, half=a.half)
    summ = jeu.summary(frames, ev)
    summ['sens_radar'] = 'Nous attaque vers la ' + ('droite' if right else 'gauche') + ' du radar (si c\'est faux : --sens ' + ('gauche' if right else 'droite') + ')'
    summ['nous'] = a.nous

    json.dump(frames, open(os.path.join(outdir, 'positions.json'), 'w', encoding='utf-8'))
    json.dump(summ, open(os.path.join(outdir, 'resume.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(app_match(name, ev, a.k1, a.half), open(os.path.join(outdir, 'match_ia.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    rapport(os.path.join(outdir, 'rapport.png'), ev, summ, name)
    s = summ['actions']
    print('Terminé en %.0f s.' % (time.time() - t0))
    print('  %s' % summ['sens_radar'])
    print('  Nous : %d passes réussies, %d ratées, %d déséquilibres (passes %d, conduites %d), %d frappes' % (
        s['N']['passes_reussies'], s['N']['passes_ratees'], s['N']['passes_deseq'] + s['N']['conduites_deseq'],
        s['N']['passes_deseq'], s['N']['conduites_deseq'], s['N']['frappes']))
    print('  Duels : %d gagnés (Z), %d perdus (E)' % (s['duels']['gagnes'], s['duels']['perdus']))
    print('  Résultats : ' + outdir)
    if a.ouvrir and os.name == 'nt':
        os.startfile(outdir)  # noqa: S606 (Windows)
    return outdir


if __name__ == '__main__':
    main()
