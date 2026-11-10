"""IA SANS RADAR (prototype, pour le live Veo) — étape 1 : détection dans l'image.

En live il n'y a que l'image de la caméra Veo (qui suit le jeu, pas de vue panoramique). Ce module trouve
les joueurs et le ballon dans l'image ; l'étape 2 (à faire) les placera sur le terrain en mètres, image par
image, et sortira le format radar_brut (t, jaune, noir, ballon) pour que jeu.py reste inchangé.

Détection : YOLO (ultralytics, modèle « personne » + « ballon » pré-entraîné), puis l'équipe par la couleur
du maillot, calculée sur les pixels du joueur (la pelouse dans la boîte est ignorée).
Installation (une fois) :
    py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    py -m pip install ultralytics
    (statistiques anonymes d'ultralytics coupées : from ultralytics import settings; settings.update({'sync': False}))
Essai :
    python sans_radar.py video.mp4 sortie_%d.jpg 2 8 14     → images annotées aux secondes demandées

Mesures (10 nov. 2026, test.mp4, 5 images, modèle yolo11s, imgsz 2880, processeur : ~1,8 s / image) :
  - quasiment tous les joueurs présents à l'image sont trouvés, y compris au fond (25-35 px de haut) ;
  - maillots jaunes / bleu marine (« noir ») bien séparés ; l'arbitre (maillot pâle) est parfois pris pour un noir ;
  - spectateurs derrière la clôture aussi détectés → seront écartés par le passage en mètres (hors terrain) ;
  - ballon souvent trouvé, avec quelques faux.
"""
import sys
import cv2
import numpy as np

YEL = dict(h=(17, 33), s_min=110, v_min=90)          # maillot jaune (Nous)
DARK = dict(h=(102, 140), s_min=50, v_max=120)        # maillot bleu marine (Eux, « noir » sur le radar)
LIME = dict(h=(30, 50), s_min=130, v_min=170)         # arbitre (vert fluo)
GRASS = dict(h=(40, 100), s=(35, 125))               # synthétique : bleu-vert à l'ombre, vert-jaune au soleil


def turf_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s = hsv[:, :, 0].astype(np.int16), hsv[:, :, 1].astype(np.int16)
    return (h >= GRASS['h'][0]) & (h <= GRASS['h'][1]) & (s >= GRASS['s'][0])


def team_of(frame, box):
    """'jaune', 'noir', 'arbitre' ou 'inconnu', d'après le haut du corps (pelouse exclue)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    hh = y1 - y0
    torso = frame[y0 + int(0.12 * hh):y0 + int(0.55 * hh), x0:x1]
    if torso.size == 0:
        return 'inconnu'
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    h, s, v = [hsv[:, :, i].astype(np.int16) for i in range(3)]
    grass = (h >= GRASS['h'][0]) & (h <= GRASS['h'][1]) & (s >= GRASS['s'][0]) & (s <= GRASS['s'][1])
    n = max(1, int((~grass).sum()))
    yel = ((h >= YEL['h'][0]) & (h <= YEL['h'][1]) & (s > YEL['s_min']) & (v > YEL['v_min'])).sum() / n
    lime = ((h >= LIME['h'][0]) & (h <= LIME['h'][1]) & (s > LIME['s_min']) & (v > LIME['v_min'])).sum() / n
    dark = ((((h >= DARK['h'][0]) & (h <= DARK['h'][1]) & (s > DARK['s_min']) & (v < DARK['v_max'])) | (v < 40))
            & ~grass).sum() / n
    if lime > 0.12 and lime > yel:
        return 'arbitre'
    if yel > 0.12 and yel > 0.5 * dark:
        return 'jaune'
    if dark > 0.12 and yel < 0.06:
        return 'noir'
    return 'inconnu'


def on_grass(turf, x0, y0, x1, y1):
    """Les pieds touchent du gazon (écarte les gens devant un mur, un bâtiment...)."""
    H, W = turf.shape
    fy = int(min(H - 1, y1)); w = max(6, int(x1 - x0))
    band = turf[max(0, fy - 2):min(H, fy + 8), max(0, int(x0) - w // 2):min(W, int(x1) + w // 2)]
    return band.size > 0 and band.mean() > 0.35


def detect(model, frame, imgsz=2880, conf=0.12):
    """Renvoie (joueurs, ballons) en pixels. joueur = dict(team, box, foot=(x, y) point au sol, conf)."""
    turf = turf_mask(frame)
    H, W = frame.shape[:2]
    r = model.predict(frame, imgsz=imgsz, conf=conf, classes=[0, 32], verbose=False)[0]
    players, balls = [], []
    for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        x0, y0, x1, y1 = b
        if x1 > W * 0.84 and y1 > H * 0.86:                  # logo Veo
            continue
        if int(c) == 32:
            balls.append(((x0 + x1) / 2, (y0 + y1) / 2, p))
            continue
        if not on_grass(turf, x0, y0, x1, y1):
            continue
        players.append(dict(team=team_of(frame, b), box=(x0, y0, x1, y1), foot=((x0 + x1) / 2, y1), conf=p))
    return players, balls


def main():
    from ultralytics import YOLO
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    model = YOLO('yolo11s.pt')
    cap = cv2.VideoCapture(sys.argv[1])
    col = dict(jaune=(0, 220, 255), noir=(255, 0, 255), arbitre=(0, 255, 0), inconnu=(160, 160, 160))
    for t in [float(a) for a in sys.argv[3:]]:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        P, B = detect(model, fr)
        print('t=%.1f s  %s  ballon %d' % (t, {k: sum(p['team'] == k for p in P) for k in col}, len(B)))
        for p in P:
            x0, y0, x1, y1 = [int(v) for v in p['box']]
            cv2.rectangle(fr, (x0, y0), (x1, y1), col[p['team']], 2)
        for x, y, _ in B:
            cv2.circle(fr, (int(x), int(y)), 14, (0, 0, 255), 3)
        cv2.imwrite(sys.argv[2] % int(t), fr)


if __name__ == '__main__':
    main()
