"""Note automatique de l'IA sur le jeu de référence (séquences codées à la main par le coach).

Un dossier par séquence, dans le dossier « references » (hors du dépôt public : ce sont les matchs du club) :
    references/<nom>/radar_brut.json   lecture du radar (produite par analyser.py, dossier resultats_...)
    references/<nom>/codage.json       export de l'onglet Vidéo de l'appli (« Exporter actions + vidéo »)
    references/<nom>/ref.json          {"nous": "noir", "sens": "gauche", "mi_temps": 1}
Le codage doit être calé sur la MÊME vidéo que celle qui a servi à lire le radar.

    python noter.py                         note avec les réglages actuels (jeu.CFG)
    python noter.py --cfg fast=8 min_pass=5 essaie d'autres réglages sans toucher au code
    python noter.py --dossier D:\\refs       autre dossier de références
Chaque note est ajoutée à references/historique.csv (date, version du code, réglages, notes).

Lecture : « IA voit » = part de tes actions que l'IA retrouve ; « IA juste » = part des actions de l'IA que tu
as aussi codées ; note = moyenne des deux (F1), sur 100. Note globale = moyenne des types d'action codés.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import comparer  # noqa: E402
import jeu       # noqa: E402


def load_raw(path):
    raw = json.load(open(path, encoding='utf-8'))
    return [dict(f, rouge=[tuple(p) for p in f['rouge']], noir=[tuple(p) for p in f['noir']],
                 ballon=tuple(f['ballon']) if f.get('ballon') else None) for f in raw]


def run_ref(folder, cfg, tol):
    ref = json.load(open(os.path.join(folder, 'ref.json'), encoding='utf-8'))
    raw = load_raw(os.path.join(folder, 'radar_brut.json'))
    sens = ref.get('sens', 'auto')
    right = None if sens == 'auto' else sens == 'droite'
    frames, _ = jeu.normalize(raw, ref.get('nous', 'noir'), right)
    frames = jeu.fill_ball(frames)
    ia = jeu.actions(frames, half=ref.get('mi_temps', 1), cfg=cfg)
    man, _ = comparer.load(os.path.join(folder, 'codage.json'))
    man = [e for e in man if e.get('video_s') is not None]
    # seulement la partie de la vidéo couverte par le radar
    t0, t1 = raw[0]['t'], raw[-1]['t']
    man = [e for e in man if t0 - 1 <= e['video_s'] <= t1 + 1]
    out = {}
    for name, f in comparer.CATS:
        m = [e for e in man if f(e)]
        i = [e for e in ia if f(e)]
        out[name] = (len(m), len(i), len(comparer.match(m, i, tol)))
    return out


def f1(m, i, c):
    if m == 0 and i == 0:
        return None
    p = c / i if i else 0.0
    r = c / m if m else 0.0
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def version():
    try:
        return subprocess.run(['git', '-C', HERE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ''


def note(dossier, cfg_over=None, tol=4.0, quiet=False, history=True):
    cfg = dict(jeu.CFG)
    for k, v in (cfg_over or {}).items():
        cfg[k] = type(jeu.CFG[k])(v)
    refs = sorted(d for d in os.listdir(dossier) if os.path.isfile(os.path.join(dossier, d, 'ref.json')))
    if not refs:
        raise SystemExit('Aucune référence dans ' + dossier + ' (un dossier par séquence avec ref.json, radar_brut.json, codage.json).')
    tot = {name: [0, 0, 0] for name, _ in comparer.CATS}
    for r in refs:
        res = run_ref(os.path.join(dossier, r), cfg, tol)
        for k, (m, i, c) in res.items():
            tot[k][0] += m
            tot[k][1] += i
            tot[k][2] += c
    scores = {}
    if not quiet:
        print('\n%d séquence(s) : %s' % (len(refs), ', '.join(refs)))
        print('%-36s %6s %5s %8s %8s %8s %6s' % ('Action', 'Toi', 'IA', 'Communes', 'IA voit', 'IA juste', 'Note'))
    for name, _ in comparer.CATS:
        m, i, c = tot[name]
        s = f1(m, i, c)
        scores[name] = s
        if not quiet:
            print('%-36s %6d %5d %8d %8s %8s %6s' % (name, m, i, c, '%d %%' % (100 * c / m) if m else '–',
                                                    '%d %%' % (100 * c / i) if i else '–', '–' if s is None else round(100 * s)))
    coded = [scores[n] for n, _ in comparer.CATS if tot[n][0] > 0]
    glob = round(100 * sum(coded) / len(coded)) if coded else None
    if not quiet:
        print('\nNOTE GLOBALE : %s / 100' % glob)
    if history:
        hp = os.path.join(dossier, 'historique.csv')
        new = not os.path.exists(hp)
        with open(hp, 'a', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh, delimiter=';')
            if new:
                w.writerow(['date', 'version', 'reglages_changes', 'note_globale'] + [n for n, _ in comparer.CATS])
            w.writerow([time.strftime('%Y-%m-%d %H:%M'), version(), ' '.join('%s=%s' % kv for kv in (cfg_over or {}).items()), glob]
                       + ['' if scores[n] is None else round(100 * scores[n]) for n, _ in comparer.CATS])
    return glob, scores


def main():
    ap = argparse.ArgumentParser(description='Note de l\'IA sur les séquences de référence.')
    ap.add_argument('--dossier', default=os.path.join(HERE, 'references'))
    ap.add_argument('--cfg', nargs='*', default=[], help='réglages à essayer, ex. fast=8 min_pass=5')
    ap.add_argument('--tol', type=float, default=4.0)
    ap.add_argument('--sans-historique', action='store_true')
    a = ap.parse_args()
    over = dict(kv.split('=', 1) for kv in a.cfg)
    for k in over:
        if k not in jeu.CFG:
            raise SystemExit('Réglage inconnu : %s (possibles : %s)' % (k, ', '.join(jeu.CFG)))
    note(a.dossier, over, a.tol, history=not a.sans_historique)


if __name__ == '__main__':
    main()
