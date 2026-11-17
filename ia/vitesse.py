"""Vitesse de la détection (YOLO) : images / seconde par modèle, résolution, processeur ou carte graphique.

    py vitesse.py video.mp4                       essais par défaut
    py vitesse.py video.mp4 --modeles yolo11s.pt yolo11m.pt --tailles 1920 2880 --n 20

Le live demande au moins 5 images / s. Le décor (ORB, CameraTracker) est mesuré à part.
"""
import argparse
import os
import sys
import time

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sans_radar as sr  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--modeles', nargs='*', default=['yolo11s.pt'])
    ap.add_argument('--tailles', type=int, nargs='*', default=[1280, 1920, 2880])
    ap.add_argument('--n', type=int, default=20, help='images mesurées par essai')
    a = ap.parse_args()
    import torch
    from ultralytics import YOLO
    gpu = torch.cuda.is_available()
    print('torch %s, carte graphique : %s' % (torch.__version__, torch.cuda.get_device_name(0) if gpu else 'NON'))
    cap = cv2.VideoCapture(a.video)
    n_fr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    imgs = []
    for k in range(a.n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(k * n_fr / a.n))
        ok, fr = cap.read()
        if ok:
            imgs.append(fr)
    devs = [('0', False), ('0', True)] if gpu else [('cpu', False)]
    print('%-12s %6s %-14s %10s %8s %8s' % ('modèle', 'taille', 'calcul', 'images/s', 'joueurs', 'ballons'))
    for m in a.modeles:
        model = YOLO(m)
        for sz in a.tailles:
            for dev, half in devs:
                kw = dict(device=dev, half=half)
                sr.detect(model, imgs[0], imgsz=sz, **kw)                # chauffe
                t0 = time.time()
                nP = nB = 0
                for fr in imgs:
                    P, B = sr.detect(model, fr, imgsz=sz, **kw)
                    nP += len(P); nB += len(B)
                ips = len(imgs) / (time.time() - t0)
                print('%-12s %6d %-14s %10.1f %8.1f %8.1f' % (m, sz, ('carte' + (' FP16' if half else '')) if dev != 'cpu' else 'processeur',
                                                           ips, nP / len(imgs), nB / len(imgs)))
    tr = sr.CameraTracker()
    f0 = tr.features(imgs[0], [])
    t0 = time.time()
    for fr in imgs:
        tr.homography(tr.features(fr, []), f0)
    print('décor (ORB + homographie) : %.1f images/s' % (len(imgs) / (time.time() - t0)))


if __name__ == '__main__':
    main()
