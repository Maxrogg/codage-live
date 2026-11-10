# Graph Report - codage-live  (2026-11-10)

## Corpus Check
- 46 files · ~35,151 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 3, .bat 3, .css 1)

## Summary
- 385 nodes · 681 edges · 26 communities (19 shown, 7 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `95f1ed60`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- t3.js
- ui.js
- analyser.py
- jeu.py
- stats.js
- ref
- test_ia.py
- viz.js
- input.js
- js/video.js
- events.js
- backup.js
- Analyse automatique des vidéos Veo
- js/sync.js
- Codage live — application de match
- Codage live — consignes pour Claude
- momentum.js
- chart.js
- sw.js
- tests/README.md
- Codage live — consignes pour tout assistant de code (Claude, Aider, OpenCode, Continue…)

## God Nodes (most connected - your core abstractions)
1. `main()` - 15 edges
2. `init()` - 15 edges
3. `summary()` - 14 edges
4. `initButtons()` - 13 edges
5. `actions()` - 13 edges
6. `teamInsights()` - 12 edges
7. `init()` - 10 edges
8. `run_ref()` - 9 edges
9. `Analyse automatique des vidéos Veo` - 9 edges
10. `refresh()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `actions()`  [EXTRACTED]
  ia/analyser.py → ia/jeu.py
- `main()` --calls--> `attack_right()`  [EXTRACTED]
  ia/analyser.py → ia/jeu.py
- `main()` --calls--> `normalize()`  [EXTRACTED]
  ia/analyser.py → ia/jeu.py
- `main()` --calls--> `read_video()`  [EXTRACTED]
  ia/analyser.py → ia/radar.py
- `run_ref()` --calls--> `actions()`  [EXTRACTED]
  ia/noter.py → ia/jeu.py

## Import Cycles
- None detected.

## Communities (26 total, 7 thin omitted)

### Community 0 - "t3.js"
Cohesion: 0.05
Nodes (32): assert, e, ev, far, fs, pen, s, six (+24 more)

### Community 1 - "ui.js"
Cohesion: 0.16
Nodes (33): avg(), badge(), bilanText(), buildPanels(), copy(), describe(), el(), fillMatchCard() (+25 more)

### Community 2 - "analyser.py"
Cohesion: 0.09
Nodes (17): app_match(), ask(), _draw(), main(), _pitch(), rapport(), load(), main() (+9 more)

### Community 3 - "jeu.py"
Cohesion: 0.11
Nodes (12): actions(), attack_right(), eliminated(), fix_keepers(), _fwd(), goal_side(), holder(), in_box() (+4 more)

### Community 4 - "stats.js"
Cohesion: 0.15
Nodes (31): bilan(), byResult(), cellName(), cpaList(), cpaType(), derived(), derivedOf(), entries() (+23 more)

### Community 5 - "ref"
Cohesion: 0.06
Nodes (14): { chromium }, { chromium }, { chromium }, { chromium }, { chromium }, { chromium }, { chromium }, { chromium } (+6 more)

### Community 6 - "test_ia.py"
Cohesion: 0.14
Nodes (7): _blobs(), find_radar(), read_frame(), read_video(), frame(), m2px(), seq()

### Community 7 - "viz.js"
Cohesion: 0.22
Nodes (19): arrow(), colorOf(), cross(), css(), density(), diverging(), drawAnalysis(), drawEvent() (+11 more)

### Community 8 - "input.js"
Cohesion: 0.26
Nodes (18): add(), autoStart(), clearSpace(), commit(), dist(), drop(), flip(), goal() (+10 more)

### Community 9 - "js/video.js"
Cohesion: 0.31
Nodes (17): exportObj(), fmt(), init(), kickoff(), nudge(), player(), render(), renderList() (+9 more)

### Community 10 - "events.js"
Cohesion: 0.25
Nodes (12): blank(), emit(), goals(), m(), norm(), resultOf(), saveIndex(), saveLocal() (+4 more)

### Community 11 - "backup.js"
Cohesion: 0.40
Nodes (9): drop(), dropOldest(), list(), purgeAuto(), readIdx(), remove(), snap(), tick() (+1 more)

### Community 12 - "Analyse automatique des vidéos Veo"
Cohesion: 0.20
Nodes (9): Analyse automatique des vidéos Veo, Analyser, Comment l'IA décide, Comparer l'IA à ton codage, Enregistrer la vidéo, Installation (une seule fois, Windows), Jeu de référence et note automatique (pour régler l'IA), Limites connues (+1 more)

### Community 13 - "js/sync.js"
Cohesion: 0.50
Nodes (6): clone(), flush(), init(), limit(), schedule(), wait()

### Community 14 - "Codage live — application de match"
Cohesion: 0.33
Nodes (5): Codage live — application de match, Données, Modifier le code (avec Claude), Publier sur GitHub Pages, Utiliser

### Community 15 - "Codage live — consignes pour Claude"
Cohesion: 0.25
Nodes (7): Autres assistants, Carte du code (Graphify), Codage live — consignes pour Claude, IA vidéo (dossier ia/) — règles, Outils et tests (dans ce dépôt), Règles, Structure (aucune compilation, scripts simples sur l'espace de noms global `FC`)

### Community 16 - "momentum.js"
Cohesion: 0.60
Nodes (4): compute(), fmt(), summary(), weightOf()

### Community 18 - "chart.js"
Cohesion: 0.83
Nodes (3): bars(), esc(), momentum()

### Community 25 - "Codage live — consignes pour tout assistant de code (Claude, Aider, OpenCode, Continue…)"
Cohesion: 0.29
Nodes (6): Carte du code (Graphify), Codage live — consignes pour tout assistant de code (Claude, Aider, OpenCode, Continue…), IA vidéo (dossier ia/) — règles, Outils et tests (dans ce dépôt), Règles, Structure (aucune compilation, scripts simples sur l'espace de noms global `FC`)

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `analyser.py` to `jeu.py`, `test_ia.py`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `init()` (e.g. with `describe()` and `flash()`) actually correct?**
  _`init()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `t3.js` be split into smaller, more focused modules?**
  _Cohesion score 0.05226480836236934 - nodes in this community are weakly interconnected._
- **Why does `actions()` connect `jeu.py` to `analyser.py`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Should `analyser.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08502415458937199 - nodes in this community are weakly interconnected._
- **Why does `run_ref()` connect `analyser.py` to `jeu.py`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Should `jeu.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11375661375661375 - nodes in this community are weakly interconnected._