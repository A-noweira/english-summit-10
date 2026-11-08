#!/usr/bin/env python3
"""Validate new content files. usage: python3 build/validate_new.py FILE.json [...]
Kinds by name: models/examNN.json (full exam) · mock/LNN.json (listening) · mock/GNN.json · mock/RNN.json · mock/WNN.json"""
import json, re, sys, os
errs = []
def E(f, m): errs.append(f'{os.path.basename(f)}: {m}')
wc = lambda s: len(s.split())
def mcq(f, items, n, tag, k=3):
    if len(items) != n: E(f, f'{tag}: need {n} items, got {len(items)}')
    for i in items:
        if len(i['options']) != k: E(f, f'{tag} q{i.get("n")}: need {k} options')
        if not isinstance(i['answer'], int) or not 0 <= i['answer'] < len(i['options']): E(f, f'{tag} q{i.get("n")}: bad answer index')
        if len(set(i['options'])) != len(i['options']): E(f, f'{tag} q{i.get("n")}: duplicate options')
    pos = [i['answer'] for i in items]
    if len(items) >= 6 and max(pos.count(x) for x in set(pos)) > len(items) * 0.55: E(f, f'{tag}: answer positions unbalanced {pos}')
def script(f, sc, tag, lo, hi, multi):
    w = sum(wc(s['text']) for s in sc)
    if not lo <= w <= hi: E(f, f'{tag}: script {w} words (want {lo}-{hi})')
    sp = {s['speaker'] for s in sc}
    if multi and len(sp) != 2: E(f, f'{tag}: conversation needs exactly 2 speakers')
    if not multi and len(sp) != 1: E(f, f'{tag}: talk needs 1 speaker')
    for s in sc:
        if s['gender'] not in 'fm' or not s['text'].strip(): E(f, f'{tag}: bad line {s}')
    if multi and len({(s['speaker'], s['gender']) for s in sc}) != 2: E(f, f'{tag}: speakers must be different (and keep a fixed gender)')
    if re.search(r'\d', ' '.join(s['text'] for s in sc)): E(f, f'{tag}: write numbers/years as words in scripts (e.g. eighteen eighty-two)')
def l1(f, d):
    mcq(f, d['items'], 7, 'L1'); script(f, d['script'], 'L1', 280, 460, True)
    if not d['context'].startswith('You are going to hear'): E(f, 'L1 context wording')
def l2(f, d):
    if len(d['short']) != 4 or len(d['tf']) != 4: E(f, 'L2 needs 4 short + 4 tf')
    for s in d['short']:
        if max(wc(re.sub(r'\(.*?\)', '', a)) for a in s['answer'].split('/')) > 4: E(f, f'L2 short answer too long: {s["answer"]}')
    script(f, d['script'], 'L2', 260, 440, False)
    t = [x['answer'] for x in d['tf']]
    if all(t) or not any(t): E(f, 'L2 tf must mix True and False')
def gram(f, d):
    txt = ' '.join(l['text'] for l in d['lines'])
    if sorted(re.findall(r'\[\[(\d)\]\]', txt)) != list('12345'): E(f, 'grammar needs [[1]]..[[5]] once each')
    if len(d['items']) != 5: E(f, 'grammar needs 5 items')
    for i in d['items']:
        if len(i['options']) != 2 or i['answer'] not in (0, 1): E(f, f'grammar item {i["n"]} needs 2 options')
    if {l['speaker'] for l in d['lines']} != {'Speaker A', 'Speaker B'}: E(f, 'grammar speakers must be Speaker A / Speaker B')
def vocab(f, d):
    if sorted(re.findall(r'\((\d)\)_+', d['passage'])) != list('12345'): E(f, 'vocab needs (1)_____..(5)_____')
    mcq(f, d['items'], 5, 'vocab', 4)
    if not 70 <= wc(d['passage']) <= 140: E(f, f'vocab passage {wc(d["passage"])} words')
def r1(f, d):
    mcq(f, d['mcq'], 6, 'R1 mcq'); 
    if len(d['completion']) != 4: E(f, 'R1 needs 4 completion')
    for c in d['completion']:
        if '________' not in c['q'] or wc(c['answer']) > 2: E(f, f'R1 completion bad: {c}')
        if c['answer'].lower() not in ' '.join(d['passage']).lower(): E(f, f'R1 completion answer not in text: {c["answer"]}')
    w = sum(wc(p) for p in d['passage'])
    if not 330 <= w <= 470: E(f, f'R1 passage {w} words (want 330-470)')
def r2(f, d):
    if len(d['short']) != 6 or len(d['tf']) != 4: E(f, 'R2 needs 6 short + 4 tf')
    t = [x['answer'] for x in d['tf']]
    if all(t) or not any(t): E(f, 'R2 tf must mix True and False')
    w = sum(wc(p) for p in d['passage'])
    if not 330 <= w <= 470: E(f, f'R2 passage {w} words (want 330-470)')
def chart(f, c):
    if len(c['series']) != 2 or not 4 <= len(c['categories']) <= 5: E(f, 'chart: 2 series, 4-5 categories')
    for s in c['series']:
        if len(s['values']) != len(c['categories']): E(f, 'chart: values/categories mismatch')
        if len(set(s['values'])) != len(s['values']): E(f, f'chart: series {s["name"]} has tied values (avoid ties)')
    m = c['model']
    for s in c['series']:
        for v in s['values']:
            if not re.search(rf'(?<!\d){v}(?!\d)', m): E(f, f'chart model misses number {v}')
    if not m.startswith('The bar chart shows'): E(f, 'chart model must start "The bar chart shows"')
    if wc(m) < 110: E(f, 'chart model too short')
def email(f, e):
    if len(e['bullets']) != 3 or not isinstance(e['formal'], bool): E(f, 'email: 3 bullets + formal bool')
    if wc(e['model']) < 105: E(f, f'email model {wc(e["model"])} words (<105)')
    if not e['model'].startswith(('Dear', 'To ')): E(f, 'email model must start with Dear ...')
def one(f):
    d = json.load(open(f, encoding='utf-8')); b = os.path.basename(f)
    if 'listening1' in d: l1(f, d['listening1']); l2(f, d['listening2'])
    if 'grammar' in d: gram(f, d['grammar']); vocab(f, d['vocab'])
    if 'reading1' in d: r1(f, d['reading1']); r2(f, d['reading2'])
    if 'chart' in d: chart(f, d['chart']); email(f, d['email'])
    need = {'exam': ('id', 'title', 'listening1', 'listening2', 'grammar', 'vocab', 'reading1', 'reading2', 'chart', 'email'), 'L': ('id', 'title', 'listening1', 'listening2'), 'G': ('id', 'title', 'grammar', 'vocab'), 'R': ('id', 'title', 'reading1', 'reading2'), 'W': ('id', 'title', 'chart', 'email')}
    k = 'exam' if b.startswith('exam') else b[0]
    for key in need[k]:
        if key not in d: E(f, f'missing {key}')
for f in sys.argv[1:]:
    try: one(f)
    except Exception as ex: E(f, f'EXCEPTION {type(ex).__name__}: {ex}')
print('\n'.join(errs) or 'OK'); sys.exit(1 if errs else 0)
