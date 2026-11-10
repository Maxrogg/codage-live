# IA vidéo — où on en est (passage de claude.ai à Claude Code, 10 nov. 2026)

## Fait
- Lecture du radar 2D Veo sur un enregistrement d'écran (`radar.py`) : positions des marques + ballon, sans carte graphique.
- Détection des actions du codage manuel (`jeu.py`) : passes réussies / ratées (à partir des déplacements du ballon), passes et conduites de déséquilibre (adversaires éliminés), duels Z / E, frappes. Réglages : `CFG`.
- `analyser.py` (+ `analyser.bat`) : vidéo ou `radar_brut.json` → `match_ia.json` importable dans l'appli, `rapport.png`, `resume.json`.
- `comparer.py` (+ `.bat`) : IA vs codage manuel du même match. `noter.py` : note sur le jeu de référence + historique.
- Onglet Vidéo dans l'appli (en ligne) : calage du codage sur la vidéo, export « actions + vidéo ».

## Seule séquence testée
- OFF_PLACEE (30 s, U14, Nous = ronds noirs, Nous attaque vers la gauche de la caméra) : 7 passes réussies + 1 ratée (sortie) pour Nous, 1 touche adverse interceptée. Pas encore vérifié par le coach : PAS de vérité de référence pour l'instant.

## Prochaines étapes (dans l'ordre)
1. Le coach libère de la place sur son disque, installe Python (`ia/installer.bat`).
2. Première référence : le coach code OFF_PLACEE dans l'onglet Vidéo et exporte → dossier `ia/references/off_placee/` (`radar_brut.json`, `codage.json`, `ref.json` = `{"nous": "noir", "sens": "gauche", "mi_temps": 1}`), puis `python ia/noter.py`.
3. Une mi-temps entière enregistrée avec le radar + codée en live → 2e référence, puis réglage de `CFG` en suivant la note (avant / après, voir CLAUDE.md).
4. Plus tard (sur demande du coach) : CPA ; puis le live (flux du téléphone vers le PC, détection sur la RTX 4050).

## Rappels
- Les références ne vont JAMAIS dans ce dépôt public (`ia/references/` est ignoré par git).
- Le coach valide chaque étape avant qu'on la lance.
