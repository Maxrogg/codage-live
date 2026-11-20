"""BANC DE TEST de l'IA sans radar : une commande, toutes les séquences, un historique.

    py banc.py                  passe toutes les séquences de references/banc.json
    py banc.py --seq cascol_10  une seule séquence
    py banc.py --refaire        relance YOLO + décor (sinon cache)

references/banc.json (HORS dépôt, chemins des vidéos du club) :
    {"terrains": {"club": "references/terrain_club"},              dossier avec terrain.json (G) + reference.jpg
     "sequences": [
        {"nom": "off_placee", "video": "C:/.../test.mp4", "debut": 0, "duree": 32, "fps": 5, "terrain": "club",
         "radar": "off_placee", "decalage": 13.84},                 radar + codage : mesures avec vérité
        {"nom": "cascol_10", "video": "C:/.../vs-cascol.mp4", "debut": 600, "duree": 120, "fps": 2, "terrain": "club",
         "codage": "references/cascol/codage.json", "mi_temps": 1}]}    codage du coach (facultatif) : note des actions

Pour chaque séquence : détection + décor (mis en cache dans references/banc_cache/, refait si le code de détection
change), puis
  - SANS vérité (toujours, voir autocontrole.py) : images reliées, lignes, joueurs par équipe, ballon ;
  - AVEC vérité (si radar / codage) : erreur des joueurs et du ballon, note de noter.py ;
  - vitesse (s / image).
Chaque passage est ajouté à references/banc_historique.csv (date, version git). Une mesure qui se dégrade par
rapport au passage précédent est signalée (BAISSE) : à ne pas garder sans l'accord du coach.
"""
import argparse
import csv
import hashlib
import inspect
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autocontrole as ac   # noqa: E402
import caler                # noqa: E402
import mesure_vision as mv  # noqa: E402
import noter                # noqa: E402
import sans_radar as sr     # noqa: E402

REF = os.path.join(HERE, 'references')
MASQUE_TOUS = 5              # un masque de lignes toutes les 5 images analysées
# (mesure, sens : +1 plus haut = mieux / -1 plus bas = mieux / 0 information, écart toléré avant « BAISSE »)
MESURES = [
    ('reliees', +1, 0.02), ('lignes', +1, 0.02), ('dans_terrain', +1, 0.03), ('jaune', 0, 0), ('noir', 0, 0), ('trop_11', -1, 0.03),
    ('ballon_vu', +1, 0.03), ('ballon_sauts', -1, 0.02), ('err_joueurs_m', -1, 0.05), ('err_ballon_m', -1, 0.2),
    ('equipes_ok', +1, 0.03), ('note', +1, 5), ('s_image', -1, 0.3),
]


def version_detection():
    src = ''.join(inspect.getsource(f) for f in (sr.detect, sr.team_of, sr.turf_mask, sr.on_grass, sr.descripteur,
                                                  sr.CameraTracker, sr.plausible, ac.masques))
    src += repr((sr.GRASS, sr.YEL, sr.DARK, sr.LIME))      # réglages des couleurs (19 nov. : oubliés → cache pas refait)
    return hashlib.sha1(src.encode()).hexdigest()[:10]


def charger_terrain(dossier):
    d = dossier if os.path.isabs(dossier) else os.path.join(HERE, dossier)
    T = json.load(open(os.path.join(d, 'terrain.json'), encoding='utf-8'))
    img = cv2.imread(os.path.join(d, 'reference.jpg'))
    if img is None:
        raise SystemExit('reference.jpg introuvable dans ' + d)
    return T, img


def temps(seq, radar):
    """Instants analysés (temps de la VIDÉO) ; avec radar, ceux du radar (vérité au même instant)."""
    if radar is not None:
        dec = seq.get('decalage', 0.0)
        return [round(f['t'] - dec, 3) for f in radar if seq['debut'] <= f['t'] - dec <= seq['debut'] + seq['duree']]
    n = int(seq['duree'] * seq['fps'])
    return [round(seq['debut'] + k / seq['fps'], 3) for k in range(n)]


def construire(seq, ref_img, ts, imgsz=2880, model_name='yolo11s.pt', T=None, dossier=None, ballon='yolo'):
    """T avec "vues" (calage par vue, caler_vues.py) : H de chaque image = image → mètres (G = identité ensuite)."""
    from ultralytics import YOLO
    import suivi
    model = YOLO(model_name)
    mballon = None if ballon == 'yolo' else YOLO(os.path.join(HERE, 'modeles', 'ballon_club.pt' if ballon == 'club'
                                                             else 'football-ball-detection.pt'))
    tr = sr.CameraTracker()
    f_ref = tr.features(ref_img, [])
    refs = suivi.references(tr, T, ref_img, dossier) if T and T.get('vues') else None
    cap = cv2.VideoCapture(seq['video'])
    if not cap.isOpened():
        raise SystemExit('Vidéo illisible : ' + seq['video'])
    frames, masques, prev = [], {}, None
    t0 = time.time()
    for k, t in enumerate(ts):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        P, B = sr.detect(model, fr, imgsz=imgsz)
        if mballon is not None:                         # ballon par le modèle football (seul, ou avec celui de YOLO)
            Bf = sr.ballons_foot(mballon, fr)
            B = Bf if ballon in ('foot', 'club') else B + [b for b in Bf if all(abs(b[0] - o[0]) > 12 or abs(b[1] - o[1]) > 12 for o in B)]
        boxes = [p['box'] for p in P]
        fe = tr.features(fr, boxes)
        H = suivi.relier(tr, fe, refs) if refs else tr.homography(fe, f_ref)
        if H is None and prev is not None and prev[1] is not None:          # de proche en proche
            Hp = tr.homography(fe, prev[0])
            H = prev[1] @ Hp if Hp is not None else None
        prev = (fe, H)
        frames.append(dict(t=t, players=[dict(p, box=list(p['box']), foot=list(p['foot'])) for p in P],
                           balls=[list(b) for b in B], H=H.tolist() if H is not None else None))
        if k % MASQUE_TOUS == 0:
            b, z = ac.masques(fr, boxes)
            i = len(frames) - 1
            masques['b%d' % i], masques['z%d' % i] = np.packbits(b), np.packbits(z)
            masques['shape'] = np.array(b.shape)
        print('\r  %s : %d / %d images (%.2f s / image)' % (seq['nom'], k + 1, len(ts), (time.time() - t0) / (k + 1)),
              end='', flush=True)
    print()
    return dict(nom=seq['nom'], version=version_detection(), model=model_name, imgsz=imgsz,
                s_image=(time.time() - t0) / max(1, len(frames)), frames=frames), masques


def charger_masques(npz):
    if 'shape' not in npz.files:
        return {}
    shape = tuple(npz['shape'])
    n = int(np.prod(shape))
    out = {}
    for k in npz.files:
        if k[0] == 'b':
            i = int(k[1:])
            out[i] = (np.unpackbits(npz['b%d' % i])[:n].reshape(shape).astype(bool),
                      np.unpackbits(npz['z%d' % i])[:n].reshape(shape).astype(bool))
    return out


def mesurer(seq, cache, masques, G, dims, radar, suivi=False):
    fr = cache['frames']
    rel = [f for f in fr if f['H'] is not None]
    res = dict(reliees=len(rel) / max(1, len(fr)), s_image=cache['s_image'])
    L = caler.lignes(**dims)
    rec = [ac.recouvrement(G @ np.array(fr[i]['H']), b, z, L)[0] for i, (b, z) in masques.items() if fr[i]['H'] is not None]
    rec = [r for r in rec if r is not None]
    res['lignes'] = float(np.mean(rec)) if rec else None
    # garde-fou : pieds des joueurs dans le terrain (un faux calage peut tromper la mesure des lignes)
    n = ok = 0
    for f in rel:
        if f['players']:
            q = sr.project(G @ np.array(f['H']), [p['foot'] for p in f['players']])
            n += len(q)
            ok += int(((q[:, 0] > -2) & (q[:, 0] < 107) & (q[:, 1] > -2) & (q[:, 1] < 70)).sum())
    res['dans_terrain'] = ok / n if n else None
    # positions en mètres (format radar_brut) + ballon cohérent
    cands = [sr.ball_candidates(f['balls'], G @ np.array(f['H'])) for f in rel]
    path = sr.ball_path(cands, [f['t'] for f in rel])
    if suivi:                                    # joueurs par pistes (suivi.py) : équipe = majorité de la piste
        import suivi as sv
        brut, pistes = sv.brut_suivi(G, rel, path)
        res.update({'pistes_' + k: v for k, v in sv.controle(pistes).items()})
        rel = sv.reetiqueter(rel, G, pistes)
    else:
        brut = mv.vision_brut(G, rel, path)
    med, trop = ac.joueurs(brut)
    res.update(jaune=med['jaune'], noir=med['noir'], trop_11=trop)
    res['ballon_vu'], res['ballon_sauts'] = ac.ballon(path, [f['t'] for f in rel])
    if radar is not None:
        dec = seq.get('decalage', 0.0)
        rad = mv.radar_at(radar)
        fr_r = [dict(f, t=round(f['t'] + dec, 2)) for f in rel]
        e = [d for _, d in mv.player_errors(G, fr_r, rad)]
        res['err_joueurs_m'] = float(np.median(e)) if e else None
        res['equipes_ok'] = equipes_justes(G, fr_r, rad)
        eb = []
        for f, p in zip(fr_r, path):
            q = rad[round(f['t'], 2)].get('ballon')
            if p and q:
                eb.append(float(np.hypot(p[0] - q[0], p[1] - q[1])))
        res['err_ballon_m'] = float(np.median(eb)) if eb else None
        dossier = os.path.join(REF, seq['radar'])
        if os.path.exists(os.path.join(dossier, 'codage.json')):
            brut_r = [dict(b, t=round(b['t'] + dec, 2)) for b in brut]
            res['note'] = mv.note_vision(dossier, brut_r)[0]
    elif seq.get('codage'):
        res['note'] = note_codage(seq, brut)
    return res


def note_codage(seq, brut):
    """Note des actions SANS radar : codage du coach (export « actions + vidéo » de l'onglet Vidéo, calé sur CETTE
    vidéo, temps en secondes de la vidéo) contre les actions tirées des positions vision. Le sens d'attaque est
    trouvé seul (jeu.attack_right)."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, 'seq')
        os.makedirs(d)
        shutil.copy(seq['codage'] if os.path.isabs(seq['codage']) else os.path.join(HERE, seq['codage']),
                    os.path.join(d, 'codage.json'))
        json.dump(dict(nous=seq.get('nous', 'jaune'), sens='auto', mi_temps=seq.get('mi_temps', 1)),
                  open(os.path.join(d, 'ref.json'), 'w', encoding='utf-8'))
        json.dump(brut, open(os.path.join(d, 'radar_brut.json'), 'w', encoding='utf-8'))
        return noter.note(tmp, history=False, quiet=True)[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def equipes_justes(G, frames, rad, tol=2.0):
    """Part des joueurs (placés à moins de tol m d'une marque radar, toutes équipes) dont l'équipe est la bonne."""
    bons = n = 0
    for f in frames:
        r = rad[round(f['t'], 2)]
        R = [(q, t) for t in ('jaune', 'noir') for q in (r.get(t) or [])]
        P = [p for p in f['players'] if p['team'] in ('jaune', 'noir')]
        if not R or not P:
            continue
        Pm = sr.project(G @ np.array(f['H']), [p['foot'] for p in P])
        for a, b, _ in sr.match_one_to_one(Pm, [q for q, _ in R], tol):
            n += 1
            bons += P[a]['team'] == R[b][1]
    return bons / n if n else None


def historique(rows):
    hp = os.path.join(REF, 'banc_historique.csv')
    old = list(csv.DictReader(open(hp, encoding='utf-8-sig'), delimiter=';')) if os.path.exists(hp) else []
    cols = ['date', 'version', 'sequence', 'reglages'] + [m for m, _, _ in MESURES]
    if old and list(old[0].keys()) != cols:                     # colonnes changées : on repart d'un nouveau fichier
        os.replace(hp, hp.replace('.csv', '_%s.csv' % time.strftime('%Y%m%d%H%M')))
        old = []
    with open(hp, 'a', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh, delimiter=';')
        if not old:
            w.writerow(cols)
        for r in rows:
            w.writerow([round(r[c], 3) if isinstance(r.get(c), float) else r.get(c, '') for c in cols])
    return old


def baisses(r, old):
    prev = [o for o in old if o['sequence'] == r['sequence'] and o.get('reglages') == r.get('reglages')]
    if not prev:
        return []
    p, out = prev[-1], []
    for m, sens, tol in MESURES:
        if sens == 0 or r.get(m) is None or p.get(m) in (None, ''):
            continue
        if (r[m] - float(p[m])) * sens < -tol:
            out.append('%s %s → %s' % (m, p[m], round(r[m], 3)))
    return out


def version_git():
    try:
        v = subprocess.run(['git', '-C', HERE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
        sale = subprocess.run(['git', '-C', HERE, 'status', '--porcelain', '--', '.'], capture_output=True, text=True).stdout.strip()
        return v + ('+modifs' if sale else '')
    except Exception:
        return ''


def main():
    ap = argparse.ArgumentParser(description='Banc de test de l\'IA sans radar.')
    ap.add_argument('--config', default=os.path.join(REF, 'banc.json'))
    ap.add_argument('--seq', nargs='*', help='seulement ces séquences')
    ap.add_argument('--refaire', action='store_true')
    ap.add_argument('--equipes', choices=['auto', 'couleurs'], default='couleurs',
                    help='auto = regroupement des maillots (equipes.py) ; couleurs = anciennes couleurs écrites en dur')
    ap.add_argument('--modele', default='yolo11s.pt', help='modèle YOLO (ex. yolo11m.pt)')
    ap.add_argument('--taille', type=int, default=2880, help='résolution donnée à YOLO')
    ap.add_argument('--ballon', choices=['yolo', 'foot', 'les2', 'club'], default='yolo',
                    help='ballon : YOLO général (yolo), modèle football roboflow (foot), les deux, ou entraîné sur nos vidéos (club)')
    ap.add_argument('--suivi', action='store_true', help="joueurs par pistes (suivi.py) au lieu d'image par image")
    ap.add_argument('--terrain', help='autre dossier de terrain pour toutes les séquences (ex. references/terrain_club_auto)')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    os.makedirs(os.path.join(REF, 'banc_cache'), exist_ok=True)
    rows = []
    for seq in cfg['sequences']:
        if a.seq and seq['nom'] not in a.seq:
            continue
        T, ref_img = charger_terrain(cfg['terrains'][seq['terrain']])
        if a.terrain:
            T = json.load(open(os.path.join(a.terrain if os.path.isabs(a.terrain) else os.path.join(HERE, a.terrain),
                                            'terrain.json'), encoding='utf-8'))
        radar = noter.load_raw(os.path.join(REF, seq['radar'], 'radar_brut.json')) if seq.get('radar') else None
        suf = '' if (a.modele, a.taille) == ('yolo11s.pt', 2880) else '_%s_%d' % (a.modele.replace('.pt', ''), a.taille)
        suf += '' if a.ballon == 'yolo' else '_ballon_' + a.ballon
        cp = os.path.join(REF, 'banc_cache', seq['nom'] + suf + '.json')
        mp = os.path.join(REF, 'banc_cache', seq['nom'] + suf + '_lignes.npz')
        cache = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else None
        cle = {k: seq[k] for k in ('video', 'debut', 'duree', 'fps')}
        cle['terrain'] = seq['terrain']
        if a.ballon != 'yolo':
            cle['ballon'] = a.ballon
        perime = (cache is None or cache.get('version') != version_detection() or cache.get('cle') != cle
                  or (cache.get('model'), cache.get('imgsz')) != (a.modele, a.taille))
        if a.refaire or perime:
            cache, masques = construire(seq, ref_img, temps(seq, radar), imgsz=a.taille, model_name=a.modele,
                                        T=T, dossier=cfg['terrains'][seq['terrain']], ballon=a.ballon)
            cache['cle'] = cle
            json.dump(cache, open(cp, 'w', encoding='utf-8'))
            np.savez_compressed(mp, **masques)
        masques = charger_masques(np.load(mp))
        if a.equipes == 'auto':
            import equipes
            info = equipes.assigner(cache['frames'], nous=seq.get('nous', 'jaune'))
            print('  %s équipes : %s' % (seq['nom'], info))
        G = np.eye(3) if T.get('vues') else np.array(T['G'])     # calage par vue : H va déjà jusqu'aux mètres
        res = mesurer(seq, cache, masques, G, T.get('dims', {}), radar, suivi=a.suivi)
        res.update(date=time.strftime('%Y-%m-%d %H:%M'), version=version_git(), sequence=seq['nom'],
                   reglages='equipes=%s%s ballon=%s terrain=%s modele=%s/%d' % (a.equipes, ' suivi' if a.suivi else '', a.ballon, os.path.basename(a.terrain or seq['terrain']),
                                                                     a.modele, a.taille))
        rows.append(res)
    old = historique(rows)
    print('\n%-12s' % 'séquence' + ''.join('%14s' % m for m, _, _ in MESURES))
    for r in rows:
        print('%-12s' % r['sequence'] + ''.join(
            '%14s' % ('–' if r.get(m) is None else ('%.2f' % r[m] if isinstance(r[m], float) else r[m])) for m, _, _ in MESURES))
    for r in rows:
        for b in baisses(r, old):
            print('BAISSE %s : %s' % (r['sequence'], b))


if __name__ == '__main__':
    main()
