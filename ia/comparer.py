"""Compare l'IA à ton codage manuel du même match, action par action.

1. Dans l'appli : onglet Vidéo → ouvrir la vidéo, caler les mi-temps → « Exporter actions + vidéo (JSON) ».
2. Analyser la même vidéo (analyser.bat) → match_ia.json.
3. Glisser les DEUX fichiers sur comparer.bat, ou :
       python comparer.py actions_video_....json resultats_.../match_ia.json
Pour chaque type d'action : combien tu en as codé, combien l'IA en a trouvé, combien se correspondent
(même équipe, même type, à moins de --tol secondes d'écart dans la vidéo).
Résultat : tableau à l'écran + comparaison.csv (chaque action, trouvée ou non, avec sa seconde vidéo pour vérifier).
"""
import argparse
import csv
import json
import os

CATS = [
    ('Passes réussies (dont déséq.)', lambda e: e['kind'] in ('pass', 'pass_deseq') and e.get('ok')),
    ('Passes ratées', lambda e: e['kind'] in ('pass', 'pass_deseq') and not e.get('ok')),
    ('Déséquilibres (passes + conduites)', lambda e: e['kind'] in ('pass_deseq', 'carry_deseq') and e.get('ok')),
    ('Duels gagnés (Z)', lambda e: e['kind'] == 'recup' and e['team'] == 'N'),
    ('Duels perdus (E)', lambda e: e['kind'] == 'perte' and e['team'] == 'N'),
    ('Frappes', lambda e: e['kind'] == 'shot'),
]


def load(path):
    d = json.load(open(path, encoding='utf-8'))
    if d.get('format') == 'codage-live/actions-video':
        return d['actions'], 'manuel'
    if 'matches' in d:
        return d['matches'][0]['events'], ('ia' if d['matches'][0]['id'].startswith('ia-') else 'manuel')
    if 'events' in d:
        return d['events'], 'manuel'
    raise SystemExit('Format de fichier inconnu : ' + path)


def match(man, ia, tol):
    """Appariement glouton par écart de temps (même équipe). Renvoie la liste des paires (i_man, i_ia)."""
    pairs, used = [], set()
    cand = []
    for i, a in enumerate(man):
        for j, b in enumerate(ia):
            if a['team'] == b['team']:
                dt = abs(a['video_s'] - b['video_s'])
                if dt <= tol:
                    cand.append((dt, i, j))
    taken = set()
    for dt, i, j in sorted(cand):
        if i not in taken and j not in used:
            taken.add(i)
            used.add(j)
            pairs.append((i, j))
    return pairs


def main():
    ap = argparse.ArgumentParser(description='Compare l\'IA au codage manuel.')
    ap.add_argument('fichiers', nargs=2)
    ap.add_argument('--tol', type=float, default=4.0, help='écart de temps accepté (s)')
    a = ap.parse_args()
    loaded = [load(p) for p in a.fichiers]
    man = next((ev for ev, k in loaded if k == 'manuel'), None)
    ia = next((ev for ev, k in loaded if k == 'ia'), None)
    if man is None or ia is None:
        raise SystemExit('Il faut un export de l\'onglet Vidéo (ton codage) ET un match_ia.json.')
    man = [e for e in man if e.get('video_s') is not None]
    ia = [e for e in ia if e.get('video_s') is not None]
    if not man:
        raise SystemExit('Ton export n\'a pas de temps vidéo : cale les mi-temps dans l\'onglet Vidéo avant d\'exporter.')

    out_rows = []
    print('\n%-36s %7s %5s %8s %10s %8s' % ('Action', 'Toi', 'IA', 'Communes', 'IA juste', 'IA voit'))
    for name, f in CATS:
        m = [e for e in man if f(e)]
        i = [e for e in ia if f(e)]
        pairs = match(m, i, a.tol)
        prec = '%d %%' % round(100 * len(pairs) / len(i)) if i else '–'
        rec = '%d %%' % round(100 * len(pairs) / len(m)) if m else '–'
        print('%-36s %7d %5d %8d %10s %8s' % (name, len(m), len(i), len(pairs), prec, rec))
        pm = {p[0] for p in pairs}
        pi = {p[1] for p in pairs}
        for k, e in enumerate(m):
            out_rows.append([name, 'toi', e['team'], e['kind'], e['video_s'], 'oui' if k in pm else 'NON (IA l\'a ratée)'])
        for k, e in enumerate(i):
            if k not in pi:
                out_rows.append([name, 'IA', e['team'], e['kind'], e['video_s'], 'NON (en trop ?)'])
    print('\nIA juste = parmi ce que l\'IA a trouvé, la part que tu as aussi codée.')
    print('IA voit  = parmi ce que tu as codé, la part que l\'IA a trouvée.')
    print('Écart de temps accepté : %.0f s. Détail action par action : comparaison.csv' % a.tol)
    dest = os.path.join(os.path.dirname(os.path.abspath(a.fichiers[1])), 'comparaison.csv')
    with open(dest, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['type', 'source', 'equipe', 'action', 'seconde_video', 'trouvee_des_deux_cotes'])
        out_rows.sort(key=lambda r: r[4])
        w.writerows(out_rows)
    print(dest)
    return dest


if __name__ == '__main__':
    main()
