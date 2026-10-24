"""Builds ../site/index.html from hub_src.html + hub_data.json (run export.py first)."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(H, 'hub_data.json')))
src = open(os.path.join(H, 'hub_src.html')).read().replace('/*DATA*/null', json.dumps(D, ensure_ascii=False).replace('</', '<\\/'))
head = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<meta name="theme-color" content="#5A6B2E"><meta name="description" content="English Summit 10 — Grade 10 English platform: themes, grammar, exam practice, writing lab.">'
        '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>\n')
open(os.path.join(H, '..', 'site', 'index.html'), 'w').write(head + src + '\n</body></html>\n')
print('site/index.html', len(src) // 1024, 'KB')
