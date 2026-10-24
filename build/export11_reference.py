"""Builds build/hub_data.json — all Grade 11 content for the platform.
Sources (build/data): platform_data.json (vocabulary, past papers, model exams), t1–t4.py (book vocabulary practice),
grammar.py (book grammar lessons), tests.py + tt_gv.py (theme tests), writing_lab.py."""
import json, re, random, sys, os, html
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, 'data'))
import importlib
from grammar import GRAMMAR, TLCHECK
from tests import TESTS
from tt_gv import TT_GV
import writing_lab as WL

P = json.load(open(os.path.join(H, 'data', 'platform_data.json')))
e = lambda s: html.escape(str(s), quote=False)

def balanced(n, k, seed):
    base = [i % k for i in range(n)]; r = random.Random(seed); r.shuffle(base)
    for _ in range(200):
        bad = [i for i in range(2, n) if base[i] == base[i-1] == base[i-2]]
        if not bad: break
        i = bad[0]; j = r.randrange(n); base[i], base[j] = base[j], base[i]
    return base
def place(a, ds, p): o = list(ds); o.insert(p, a); return o

TN = {1: 'Communication', 2: 'Those Teenage Things', 3: 'Travellers and Tourists', 4: 'Innovation'}
D = {'vocab': [], 'grammar': [], 'found': [], 'listen': [], 'pages': {}, 'themeKeys': [], 'tn': TN}

# ------------------------------------------------------------------ vocabulary
def norm(s): return re.sub(r'[^a-z ]', '', s.lower()).strip()
def matches(word, ans):
    w, a = norm(word.split('=')[0]), norm(ans)
    w = re.sub(r'^(a|an|the) ', '', w); a = re.sub(r'^(a|an|the) ', '', a)
    return bool(w) and (a == w or a.startswith(w) or w.startswith(a) and len(a) > 3 or (len(w) > 4 and w in a))
for n in range(1, 5):
    T = P['vocab'][n - 1]; mod = importlib.import_module(f't{n}'); ln = 0
    for ui, u in enumerate(T['units']):
        for li, words in enumerate(u['lessons']):
            ex = mod.LESSONS[ln]; ln += 1
            mcq = ex['mcq']; nn = len(mcq) + len(ex['cloze'][1]); pos = balanced(nn, 4, n * 100 + ln)
            items = [[s, place(a, ds, pos[i]), pos[i]] for i, (s, a, *ds) in enumerate(mcq)]
            W = []
            for w in words:
                d = (w[2] or '').strip() or mod.DEFS.get(w[0], '')
                exs = next((s.replace('____', f'**{a}**') for s, a, *ds in mcq if matches(w[0], a)), '')
                W.append(dict(w=w[0], p='', ar=w[1], d=d, ex=exs or (d[0].upper() + d[1:] + '.' if d else ''), s=bool(w[3])))
            part = f' ({li + 1})' if len(u['lessons']) > 1 else ''
            D['vocab'].append(dict(code=f'T{n}-V{ln}', theme=n, tname=TN[n], title=u['name'] + part, ar=u['ar'], words=W, mcq=items,
                                   cloze=[ex['cloze'][0], [[place(a, ds, pos[len(mcq) + k]), pos[len(mcq) + k]] for k, (a, *ds) in enumerate(ex['cloze'][1])]],
                                   extras={k: u.get(k, []) for k in ('verbs', 'preps', 'exprs', 'derivs') if u.get(k) and li == len(u['lessons']) - 1}))
irr = {}
for T in P['vocab']:
    for u in T['units']:
        for v in u.get('verbs', []):
            if v[0].replace('skimed', 'skimmed') not in irr and ' ' not in v[0]: irr[v[0]] = [v[0], v[1].replace('skimed', 'skimmed'), v[2].replace('skimed', 'skimmed'), v[3]]
D['irreg'] = list(irr.values())

# ------------------------------------------------------------------ grammar (with the timeline drawings)
W_, H_, AX, X0, X1 = 600, 78, 46, 24, 576
px = lambda p: X0 + p * (X1 - X0)
def lab(x, y, t, a='middle', s=11): return f'<text x="{x}" y="{y}" text-anchor="{a}" font-size="{s}" font-weight="700" fill="currentColor">{e(t)}</text>'
def cross(x, s=6): return f'<path d="M{x-s},{AX-s}L{x+s},{AX+s}M{x-s},{AX+s}L{x+s},{AX-s}" stroke="currentColor" stroke-width="2.6"/>'
def tl_svg(marks, uid):
    o = [f'<svg viewBox="0 0 {W_} {H_}" style="width:100%;height:auto;display:block;max-width:720px;color:var(--ink)">',
         f'<defs><marker id="ah{uid}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0L8,4L0,8z" fill="currentColor"/></marker>'
         f'<pattern id="hp{uid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--t2)" stroke-width="2.6"/></pattern></defs>',
         f'<line x1="{X0}" y1="{AX}" x2="{X1}" y2="{AX}" stroke="currentColor" stroke-width="1.6" marker-end="url(#ah{uid})"/>',
         f'<line x1="{px(.5)}" y1="{AX-30}" x2="{px(.5)}" y2="{AX+14}" stroke="var(--t1)" stroke-width="1.6" stroke-dasharray="3 3"/>',
         lab(X0 + 2, AX + 26, 'PAST', 'start', 10), lab(px(.5), AX + 26, 'NOW', 'middle', 10), lab(X1 - 2, AX + 26, 'FUTURE', 'end', 10)]
    for m in marks:
        k = m[0]
        if k == 'x': o.append(cross(px(m[1]))); o.append(lab(px(m[1]), AX - 14, m[2], 'middle', 10.5) if m[2] else '')
        elif k == 'xs':
            o += [cross(px(p), 5) for p in m[1]]; o.append(lab(px(sum(m[1]) / len(m[1])), AX - 16, m[2], 'middle', 10.5) if m[2] else '')
        elif k == 'band':
            a, b = px(m[1]), px(m[2]); o.append(f'<rect x="{a}" y="{AX-7}" width="{b-a}" height="14" fill="url(#hp{uid})" stroke="currentColor" stroke-width="1.4" rx="3"/>')
            o.append(lab((a + b) / 2, AX - 14, m[3], 'middle', 10.5) if m[3] else '')
        elif k == 'arrow':
            a, b = px(m[1]), px(m[2]); mid = (a + b) / 2
            o.append(f'<path d="M{a},{AX-6} Q{mid},{AX-34} {b-2},{AX-8}" fill="none" stroke="var(--t2)" stroke-width="2" marker-end="url(#ah{uid})"/>')
            o.append(lab(mid, AX - 30, m[3], 'middle', 10) if m[3] else '')
        elif k == 'int':
            a, b, x = px(m[1]), px(m[2]), px(m[3])
            o.append(f'<rect x="{a}" y="{AX-7}" width="{b-a}" height="14" fill="url(#hp{uid})" stroke="currentColor" stroke-width="1.4" rx="3"/>')
            o.append(f'<path d="M{x},{AX-26}L{x},{AX-9}" stroke="var(--t1)" stroke-width="2" marker-end="url(#ah{uid})"/><circle cx="{x}" cy="{AX}" r="7" fill="var(--t1)"/>')
            o.append(lab(a, AX - 13, 'was / were + -ing', 'start', 9.5)); o.append(lab(x + 6, AX - 28, f'{m[4]} + V2 (short action)', 'start', 9.5))
    return ''.join(o) + '</svg>'

old = {g['title']: g for g in P['grammar']}
OLD_OF = {'Past Participles & The Past Passive': 'The Past Passive', 'Indirect Questions': 'Questions & Indirect Questions'}
uid = 0
for n in range(1, 5):
    for gi, g in enumerate(GRAMMAR[n], 1):
        code = f'T{n}-G{gi}'
        pos = balanced(len(g['mcq']), 4, 500 + n * 10 + gi)
        items = [[s, place(a, ds, pos[i]), pos[i]] for i, (s, a, *ds) in enumerate(g['mcq'])]
        o = old.get(OLD_OF.get(g['title'], g['title']))
        if o: items += [[q, opts, a] for q, opts, a, *_ in o['ex']]
        chk = TLCHECK.get(g['title'], [])
        letters = ['Timeline ' + 'ABC'[i] for i in range(len(g['timelines']))]
        items += [[f'Which timeline? “{s}”', letters, k] for s, k in chk]
        comp = [[s, a.replace(' … ', ' ')] for s, a in g['onew'] + g['verb']]
        # summary: intro, timelines, form, use, signal words, mistakes, tip
        S = [f'<p>{e(g["intro"][0])}</p><p class="ar">{e(g["intro"][1])}</p>']
        for i, (cap, arcap, marks, exm) in enumerate(g['timelines']):
            uid += 1
            S.append(f'<div class="tlb"><div class="k">Timeline {"ABC"[i]}</div>{tl_svg(marks, uid)}<div class="tlc"><span><b>{e(cap)}</b><br><i>{e(exm)}</i></span><span class="ar">{e(arcap)}</span></div></div>')
        if g.get('qwords'):
            S.append('<table class="k">' + ''.join(f'<tr><td><b>{e(w)}</b></td><td class="ar">{e(a)}</td><td><i>{e(x)}</i></td></tr>' for w, a, x in g['qwords']) + '</table>')
        f = g['form']
        S.append('<h4>Form <span class="ar">التكوين</span></h4><table class="k"><tr>' + ''.join(f'<th>{c}</th>' for c in f[0]) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in f[1:]) + '</table>')
        if g.get('tags'): S.append('<h4>Question tags</h4><p>' + ' · '.join(f'{e(a)} <b>{e(b)}</b>' for a, b in g['tags']) + '</p>')
        if g.get('ppart'): S.append('<h4>Irregular V3</h4><p>' + ' · '.join(f'{e(a)} → <b>{e(b)}</b>' for a, b in g['ppart']) + '</p>')
        if g.get('uses'): S.append('<h4>Use <span class="ar">الاستخدام</span></h4><table class="k">' + ''.join(f'<tr><td>{e(u)}</td><td class="ar">{e(a)}</td><td><i>{e(x)}</i></td></tr>' for u, a, x in g['uses']) + '</table>')
        if g.get('signals'): S.append('<h4>Signal words <span class="ar">الكلمات الدالة</span></h4>' + ''.join(f'<p><b>{e(k)}:</b> ' + ' · '.join(e(w) for w in ws) + '</p>' for k, ws in g['signals']))
        S.append('<h4>Common mistakes <span class="ar">أخطاء شائعة</span></h4><p>' + '<br>'.join(f'<s>✗ {e(a)}</s> → <b>✓ {e(b)}</b>' for a, b in g['mistakes']) + '</p>')
        S.append(f'<div class="tip"><b>Exam tip:</b> {e(g["tip"][0])}<br><span class="ar">{e(g["tip"][1])}</span></div>')
        D['grammar'].append(dict(code=code, theme=n, title=g['title'], ar=g['ar'], summary=''.join(S), items=items, complete=comp))

# ------------------------------------------------------------------ exams
def p3(items, seed):
    pos = balanced(len(items), 3, seed)
    return [[s, place(a, ds[:2], pos[i]), pos[i]] for i, (s, a, *ds) in enumerate(items)]
def grm_from_braces(lines, seed):
    pos = balanced(sum(t.count('{') for _, t in lines), 2, seed); k = [0]; ans = []
    def rep(m):
        a, b = m.group(1).split('|'); p = pos[k[0]]; k[0] += 1; o = [a, b] if p == 0 else [b, a]; ans.append(p); return '{' + '|'.join(o) + '}'
    return dict(lines=[[sp, re.sub(r'\{([^{}|]+\|[^{}|]+)\}', rep, t)] for sp, t in lines], ans=ans)
def vcb_from(v, seed):
    pos = balanced(len(v['opts']), 3, seed)
    return dict(body=v['body'], opts=[place(o[0], o[1:], pos[i]) for i, o in enumerate(v['opts'])], ans=pos)
def paras(t): return [x.strip() for x in re.split(r'\n\s*\n|\n', t) if x.strip()]
def wsit(w): return f"Situation: {w['sit']}\nTask: {w['task']}" if isinstance(w, dict) else w

D['exams'] = []
# 10 model exams
for m in P['models']:
    g = m['g']; lines, ans = [], []
    for row in g['d']:
        if len(row) > 2: sp, t, (o1, o2, a) = row; lines.append([sp, t.replace('____', '{' + o1 + '|' + o2 + '}')]); ans.append(a)
        else: lines.append(row)
    v = m['v']
    D['exams'].append(dict(id=f"MT-{m['n']:02d}", label=f"Model Exam {m['n']}", kind='model',
        l1=dict(intro=m['l1']['intro'], items=m['l1']['q'], script=m['l1']['script']),
        l2=dict(intro=m['l2']['intro'], p1=[[q, x[2] if len(x) > 2 else ' / '.join(x[1])] for x in m['l2']['sa'] for q in [x[0]]], p2=m['l2']['q'], script=m['l2']['script']),
        grm=dict(lines=lines, ans=ans), vcb=dict(body=re.sub(r'\((\d)\)____', r'{\1}', v['t']), opts=[q[0] for q in v['q']], ans=[q[1] for q in v['q']]),
        r1=[list(x) for x in m['r1']], r2=dict(inst='Read the text. Then choose the correct option.', title=m['r2']['t'], text=paras(m['r2']['text']), items=m['r2']['q']),
        r3=dict(title=m['r3']['t'], text=paras(m['r3']['text']), wh=[[x[0], x[2] if len(x) > 2 else ' / '.join(x[1])] for x in m['r3']['sa']], mcq=m['r3']['q']),
        w1=m['w1'], w2=wsit(m['w2']), w1type='EN' if re.search(r'danger|negative|problem|disadvantage', m['w1'], re.I) else 'EP',
        w2type='FE' if m['w2'].get('type') == 'formal' else 'IE'))
# 4 theme tests
for n in range(1, 5):
    T = TESTS[n]; s = 9000 + n * 10
    D['exams'].append(dict(id=f'TT-{n}', label=T['title'], kind='theme',
        l1=dict(intro=T['l1']['intro'].replace('**', ''), items=p3(T['l1']['q'], s + 1), script=T['l1']['script']),
        l2=dict(intro=T['l2']['intro'].replace('**', ''), p1=[list(x) for x in T['l2']['sa']], p2=p3(T['l2']['q'], s + 2), script=T['l2']['script']),
        grm=grm_from_braces(TT_GV[n]['grm'], s + 3), vcb=vcb_from(TT_GV[n]['vcb'], s + 4),
        r1=[list(x) for x in T['r1']], r2=dict(inst='Read the text. Then choose the correct option.', title=T['r2']['t'], text=paras(T['r2']['text']), items=p3(T['r2']['q'], s + 5)),
        r3=dict(title=T['r3']['t'], text=paras(T['r3']['text']), wh=[list(x) for x in T['r3']['sa']], mcq=p3(T['r3']['q'], s + 6)),
        w1=T['w1'], w2=wsit(T['w2']), w1type='EP', w2type='FE' if re.search(r'manager|principal|company', T['w2']['task'], re.I) else 'IE'))
# past papers (booklet), newest first
PS = P['past']; S = {}
def sess(s):
    m = re.match(r'Sem I (1st|2nd) Session (\d{2})(\d{2})-(\d{2})(\d{2})\s*(?:\((\w)\))?', s)
    return m
for x in PS['l1']: S.setdefault(x['s'], {})['l1'] = dict(intro=x['intro'], items=x['q'], url=x.get('url'))
for x in PS['l2']: S.setdefault(x['s'], {})['l2'] = dict(intro=x['intro'], p1=[[q[0], q[2] if len(q) > 2 else ' / '.join(q[1])] for q in x['sa']], p2=x['q'], url=x.get('url'))
for x in PS['r1']: S.setdefault(x['s'], {})['r1'] = [list(q) for q in x['q']]
for x in PS['r2']:
    d = S.setdefault(x['s'], {}); key = 'r2b' if 'r2' in d else 'r2'
    d[key] = dict(inst='Read the text. Then choose the correct option.', title=x['t'], text=paras(x['text']), items=x['q'])
for x in PS['r3']: S.setdefault(x['s'], {})['r3'] = dict(title=x['t'], text=paras(x['text']), wh=[[q[0], q[2] if len(q) > 2 else ' / '.join(q[1])] for q in x['sa']], mcq=x['q'])
for s_, t in PS['w']['essay']: S.setdefault(s_, {})['w1'] = t
for s_, sit, task, typ in PS['w']['email']: S.setdefault(s_, {}).update(w2=f'Situation: {sit}\nTask: {task}', w2type='FE' if typ == 'formal' else 'IE')
past = []
for s_, d in S.items():
    m = sess(s_); n1 = 1 if m.group(1) == '1st' else 2; v = m.group(6) or ''
    d.update(id=f'EX-{m.group(3)}{m.group(5)}-{n1}{v}', label=f'{m.group(2)}{m.group(3)}-{m.group(4)}{m.group(5)} · Session {n1}' + (f' ({v})' if v else ''), kind='past',
             sort=(-int(m.group(2) + m.group(3)), n1, {'': 0, 'M': 1, 'E': 2}[v]))
    if 'w1' in d: d['w1type'] = 'EN' if re.search(r'danger|negative|problem', d['w1'], re.I) else 'EP'
    if d.get('l1', {}).get('url'): d['audio'] = d['l1']['url']
    past.append(d)
# re-sit and school mock (reading and writing; listening answers are not available)
try:
    from extra_past import RESIT, BALI
    for X, pid, lab_, srt in [(RESIT, 'EX-2324-RS', '2023-2024 · Re-sit exam', (-2023, 3, 0)), (BALI, 'EX-2324-BA', '2023-2024 · School mock (B. B. Ali)', (-2023, 4, 0))]:
        past.append(dict(id=pid, label=lab_, kind='past', sort=srt, r1=[list(x) for x in X['r1']],
            r2=dict(inst='Read the text. Then choose the correct option.', title=X['r2']['t'], text=paras(X['r2']['text']), items=[[q, o, a] for q, o, a in X['r2']['q']]),
            r3=dict(title=X['r3']['t'], text=paras(X['r3']['text']), wh=[list(x) for x in X['r3']['sa']], mcq=[[q, o, a] for q, o, a in X['r3']['q']])))
except ImportError as e:
    print('extra_past missing', e)
past.sort(key=lambda d: d['sort'])
for d in past: d.pop('sort', None)
D['exams'] += past
# grammar & vocabulary sets from the booklet (new exam form)
for gx, vx in zip(PS['g'], PS['v']):
    lines, ans = [], []
    for sp, t in gx['d']:
        def rep(mm):
            a, b, k = mm.group(1).split('/'); ans.append(int(k)); return '{' + a + '|' + b + '}'
        lines.append([sp, re.sub(r'\[\[([^\]]+)\]\]', rep, t)])
    D['exams'].append(dict(id=f"GV-{gx['n']:02d}", label=f"Grammar & Vocabulary · Set {gx['n']}", kind='gv',
        grm=dict(lines=lines, ans=ans), vcb=dict(body=re.sub(r'\((\d)\)____', r'{\1}', vx['t']), opts=[q[0] for q in vx['q']], ans=[q[1] for q in vx['q']])))

# ------------------------------------------------------------------ writing lab + topic bank
D['wlab'] = dict(models=WL.LAB, samples=WL.SAMPLES)
KW = {1: r'phone|internet|e-?mail|social media|communicat|message|blog|body language|english|speak|magazine',
      2: r'teen|friend|parent|school|grade|stud|exam|problem|club|classmate|free time|good at|forget|advice',
      3: r'travel|tour|trip|visit|holiday|city|country|place|historical|national day|hotel|desert|summer',
      4: r'invent|smart|robot|online|shop|product|refund|computer|technolog|device|dvd|cd|headphone|internet company'}
def theme_of(t):
    best = (0, 0)
    for k, rx in KW.items():
        c = len(re.findall(rx, t, re.I))
        if c > best[0]: best = (c, k)
    return best[1]
WT = {k: {} for k in ('EP', 'EN', 'IE', 'FE')}
def add(T, t, src):
    t = re.sub(r'\s+', ' ', t).strip()
    if t and not any(x['t'] == t for g in WT[T].values() for x in g): WT[T].setdefault(str(theme_of(t)), []).append(dict(t=t, src=src))
for x in D['exams']:
    if x.get('w1'): add(x.get('w1type', 'EP'), x['w1'], x['label'])
    if x.get('w2'): add(x.get('w2type', 'IE'), x['w2'].replace('\n', ' '), x['label'])
for T, l in WL.TOPICS.items():
    for t in l: add(T, t, 'English Summit 11')
for T, l in WL.LAB.items():
    for m in l: add(T, m['frame_topic'], 'Writing Lab')
D['wtopics'] = WT

json.dump(D, open(os.path.join(H, 'hub_data.json'), 'w'), ensure_ascii=False)
print({k: len(v) for k, v in D.items() if isinstance(v, (list, dict))})
print('exams', [(x['id'], x['kind']) for x in D['exams']][:40])
print({T: {k: len(v) for k, v in g.items()} for T, g in WT.items()})
