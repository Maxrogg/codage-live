"""Analyse automatique d'une vidéo Veo enregistrée avec le radar 2D affiché.

Usage (Windows, dans le dossier ia) :
    python analyser.py "C:\\chemin\\match.mp4" --nous noir
Options :
    --nous noir|rouge   marques du radar qui sont Nous (ronds noirs ou triangles rouges). Défaut : noir.
    --fps 5             images analysées par seconde (5 suffit).
    --k1 0              seconde de la vidéo où le chrono de l'appli vaut 00:00 (voir onglet Vidéo de l'appli).
    --mi-temps 1        mi-temps de la vidéo (1 ou 2).
    --sens auto|droite|gauche   sens d'attaque de Nous sur le radar (auto = repéré grâce au gardien).
Sortie (dossier « resultats_<nom de la vidéo> ») :
    positions.json      positions image par image (repère de l'appli)
    resume.json         blocs des deux équipes, possession, zones du ballon
    match_ia.json       à importer dans l'appli (Matchs > Importer une sauvegarde) : actions détectées
    rapport.png         image de synthèse
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
        events=evs, seq=len(evs), meta=dict(half=half, elapsed=0, flip=False, video=dict(name=name, k1=k1 if half == 1 else None, k2=k1 if half == 2 else None)),
        upd=int(time.time() * 1000))])


def rapport(path, frames, poss, summ, titre):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('(matplotlib absent : pas d\'image de rapport — pip install matplotlib)')
        return
    NC, EC = '#2563eb', '#ea580c'
    fig = plt.figure(figsize=(12, 7.2), dpi=110)
    ax = fig.add_axes([0.04, 0.30, 0.6, 0.62])
    ax.set_xlim(-2, 107); ax.set_ylim(70, -2); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(plt.Rectangle((0, 0), 105, 68, color='#e8f0e4', zorder=0))
    for args in [((0, 0), 105, 68), ((0, 13.84), 16.5, 40.32), ((88.5, 13.84), 16.5, 40.32)]:
        ax.add_patch(plt.Rectangle(*args, fill=False, ec='#9aa59a', lw=1.2))
    ax.plot([52.5, 52.5], [0, 68], c='#9aa59a', lw=1.2); ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, ec='#9aa59a', lw=1.2))
    for team, col in (('N', NC), ('E', EC)):
        pts = [p for f in frames for p in f[team]]
        if pts:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=7, c=col, alpha=0.12, lw=0)
    b = [f['ballon'] for f in frames if f['ballon']]
    if b:                                               # trajet du ballon, coupé quand il n'est pas vu
        xs, ys = [], []
        for f in frames:
            xs.append(f['ballon'][0] if f['ballon'] else float('nan'))
            ys.append(f['ballon'][1] if f['ballon'] else float('nan'))
        ax.plot(xs, ys, c='#111', lw=1.2, alpha=0.7)
        ax.scatter([b[-1][0]], [b[-1][1]], c='#facc15', ec='#111', s=40, zorder=5)
    ax.annotate('', xy=(70, 72), xytext=(35, 72), arrowprops=dict(arrowstyle='->', color=NC), annotation_clip=False)
    ax.text(52.5, 75, 'Nous attaquons →', ha='center', color=NC, fontsize=9)
    ax.set_title(titre + ' — présence des joueurs (bleu = Nous, orange = Eux) et trajet du ballon', fontsize=10, loc='left')
    # possession dans le temps
    ax2 = fig.add_axes([0.04, 0.10, 0.6, 0.08])
    for t, team, _, _ in poss:
        if team:
            ax2.axvspan(t, t + 0.2, color=NC if team == 'N' else EC, lw=0)
    ax2.set_yticks([]); ax2.set_xlabel('secondes de vidéo'); ax2.set_title('Possession (bleu Nous, orange Eux, blanc = inconnue)', fontsize=9, loc='left')
    ax2.set_xlim(frames[0]['t'], frames[-1]['t'] + 0.2)
    # chiffres
    ax3 = fig.add_axes([0.68, 0.08, 0.3, 0.84]); ax3.axis('off')
    bn, be = summ['blocs']['N'], summ['blocs']['E']
    lignes = [('Possession', '%s %%' % summ['possession_pct']['N'], '%s %%' % summ['possession_pct']['E']),
              ('Hauteur du bloc (m)', bn['hauteur'], be['hauteur']),
              ('Ligne défensive (m)', bn['ligne_def'], be['ligne_def']),
              ('Largeur (m)', bn['largeur'], be['largeur']),
              ('Longueur (m)', bn['longueur'], be['longueur']),
              ('Surface occupée (m²)', bn['surface'], be['surface'])]
    y = 0.95
    ax3.text(0, y, 'Moyennes de la séquence', fontsize=11, weight='bold'); y -= 0.06
    ax3.text(0.62, y, 'Nous', color=NC, weight='bold'); ax3.text(0.84, y, 'Eux', color=EC, weight='bold'); y -= 0.05
    for l, a, c in lignes:
        ax3.text(0, y, l, fontsize=9.5); ax3.text(0.62, y, str(a), fontsize=9.5); ax3.text(0.84, y, str(c), fontsize=9.5); y -= 0.05
    y -= 0.03
    t = summ['ballon_par_tiers_pct']
    ax3.text(0, y, 'Ballon : notre tiers %s %% · milieu %s %% · tiers adverse %s %%' % (t['notre_tiers'], t['milieu'], t['tiers_adverse']), fontsize=9); y -= 0.05
    ax3.text(0, y, 'Ballon vu sur %s %% des images · %s s analysées' % (summ['ballon_vu_pct'], summ['duree_s']), fontsize=8.5, color='#666'); y -= 0.06
    ax3.text(0, y, 'Hauteur / ligne défensive : distance à son propre but.\nPositions lues sur le radar Veo : approximatif.', fontsize=8, color='#666')
    fig.savefig(path)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description='Analyse automatique d\'une vidéo Veo (radar 2D).')
    ap.add_argument('video')
    ap.add_argument('--nous', default='noir', choices=['noir', 'rouge'])
    ap.add_argument('--fps', type=float, default=5)
    ap.add_argument('--k1', type=float, default=0)
    ap.add_argument('--mi-temps', dest='half', type=int, default=1, choices=[1, 2])
    ap.add_argument('--sens', default='auto', choices=['auto', 'droite', 'gauche'])
    ap.add_argument('--sortie', default=None)
    a = ap.parse_args()

    name = os.path.splitext(os.path.basename(a.video))[0]
    outdir = a.sortie or os.path.join(os.path.dirname(os.path.abspath(a.video)), 'resultats_' + name)
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    last = [0]
    def prog(r):
        if r - last[0] >= 0.05:
            last[0] = r
            print('  lecture : %d %%' % (100 * r), end='\r', flush=True)
    raw = radar.read_video(a.video, fps=a.fps, progress=prog)
    print()
    if not raw:
        raise SystemExit('Radar Veo introuvable : enregistre la vidéo avec le radar 2D affiché en haut à droite.')
    right = None if a.sens == 'auto' else (a.sens == 'droite')
    frames, right = jeu.normalize(raw, a.nous, right)
    frames = jeu.fill_ball(frames)
    poss = jeu.possession(frames)
    evs = jeu.actions(poss, k1=a.k1, half=a.half)
    summ = jeu.summary(frames, poss)
    summ['sens_radar'] = 'Nous attaque vers la ' + ('droite' if right else 'gauche') + ' du radar'
    summ['actions'] = {'recup': sum(1 for e in evs if e['kind'] == 'recup'), 'pass': sum(1 for e in evs if e['kind'] == 'pass')}

    json.dump(frames, open(os.path.join(outdir, 'positions.json'), 'w', encoding='utf-8'))
    json.dump(summ, open(os.path.join(outdir, 'resume.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(app_match(name, evs, a.k1, a.half), open(os.path.join(outdir, 'match_ia.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    rapport(os.path.join(outdir, 'rapport.png'), frames, poss, summ, name)
    print('Terminé en %.0f s → %s' % (time.time() - t0, outdir))
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
