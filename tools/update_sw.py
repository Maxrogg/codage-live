#!/usr/bin/env python3
"""Recalcule sw.js (liste des fichiers + numéro de version) après toute modification du code.
Sans ça, l'application installée garde les anciens fichiers en cache. Usage : python3 tools/update_sw.py"""
import hashlib, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = ('sw.js', 'README.md', 'CLAUDE.md', '.nojekyll')
files = []
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('tools', 'tests', 'node_modules', 'ia')]
    for n in names:
        p = os.path.relpath(os.path.join(base, n), ROOT).replace(os.sep, '/')
        if p not in SKIP and not n.startswith('.') and not p.endswith('.zip'): files.append(p)
files.sort()
h = hashlib.sha256(b''.join(open(os.path.join(ROOT, p), 'rb').read() for p in files)).hexdigest()[:10]
sw = open(os.path.join(ROOT, 'sw.js'), encoding='utf-8').read()
sw = re.sub(r"Version \w+\.", 'Version %s.' % h, sw, count=1)
sw = re.sub(r"const V = '[^']*';", "const V = 'codage-live-%s';" % h, sw, count=1)
sw = re.sub(r"const FILES = \[.*?\];", lambda m: 'const FILES = %s;' % json.dumps(['./'] + files), sw, count=1, flags=re.S)
open(os.path.join(ROOT, 'sw.js'), 'w', encoding='utf-8').write(sw)
print('sw.js : version', h, '-', len(files), 'fichiers')
