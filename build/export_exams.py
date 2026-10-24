"""Exams exporter (Grade 10): model exams (kind 'model', MT-01..10) + past-paper practice sets from /home/claude/es10/data.
Fills D['exams'] (appends; other modules may add kind 'theme' entries in the same shape), D['listen'] = [] (unused), D['examKeys'].

Exam entry shape (everything optional except id/label/kind):
  id, label, kind ('model' | 'past' | 'gv' | 'theme'), part ('L' | 'G' | 'R' for practice sets), session
  l1  {intro, items [[q, opts, ans]], script [[speaker, text]], audio 'audio/examNN_part1.mp3'}
  l2  {intro, p1 [[question + hint, answer]], p2 [[statement, bool]], script, audio}
  grm {lines [[speaker, 'text with {a|b} gaps']], ans [0/1 ...]}
  vcb {body 'text with {1}..{5}', opts [[4 options] ...], ans [..]}
  r1  {title, text [paras], mcq [[q, opts, ans]], comp [[q with ________, answer]]}
  r2  {title, text [paras], short [[q, answer]], tf [[statement, bool]]}
  w1 chart {id,title,ylabel,unit,categories,series,model} + w1topic (prompt text sent to AI) + w1type 'CH'
  w2 email {id,formal,situation,task,bullets,model} + w2topic + w2type 'FE' | 'IE'
Numbering: L1 1-7 · L2 8-15 · grammar 16-20 · vocabulary 21-25 · R1 26-35 · R2 36-45 · writing 1 (/5) + 2 (/10)."""
import json, os, re, glob

SRC = '/home/claude/es10/data'
J = lambda p: json.load(open(os.path.join(SRC, p), encoding='utf-8'))


def gram(lines, items):
    ans = []; it = {i['n']: i for i in items}
    def rep(t):
        def r(m):
            i = it[int(m.group(1))]; ans.append(i['answer'])
            return '{' + '|'.join(i['options']) + '}'
        return re.sub(r'\[\[(\d)\]\]', r, t)
    out = [[l['speaker'], rep(l['text'])] for l in lines]
    ans_by_n = [it[k]['answer'] for k in sorted(it)]
    assert len(ans) == len(items) == 5, (len(ans), len(items))
    return dict(lines=out, ans=ans_by_n)


def vocab(passage, items):
    return dict(body=re.sub(r'\((\d)\)_+', r'{\1}', passage), opts=[i['options'] for i in items], ans=[i['answer'] for i in items])


def mcq(items): return [[i['q'], i['options'], i['answer']] for i in items]
def shorts(items): return [[(i['q'] + (' ' + i['hint'] if i.get('hint') else '')).strip(), i['answer']] for i in items]
def tfs(items): return [[i['statement'], bool(i['answer'])] for i in items]
def comp(items): return [[i['q'], i['answer']] for i in items]


def r1(d): return dict(title=d.get('title', ''), text=d['passage'], mcq=mcq(d['mcq']), comp=comp(d['completion']))
def r2(d): return dict(title=d.get('title', ''), text=d['passage'], short=shorts(d['short']), tf=tfs(d['tf']))


def chart_topic(c):
    ser = '; '.join(f"{s['name']}: " + ', '.join(f"{k} {v}" for k, v in zip(c['categories'], s['values'])) for s in c['series'])
    return f"Describe the bar chart: {c['title']} ({c.get('ylabel', '')}). Data ({c.get('unit', '')}) - {ser}"[:590]


def email_topic(e):
    return f"{e['situation']} {e['task']} Include: " + ' '.join(f"({i + 1}) {b}" for i, b in enumerate(e['bullets']))


def script(sc): return [[s['speaker'], s['text']] for s in sc]


def keys_rows(x):
    """Answer key rows [[part, n, answer]] for the keys page."""
    rows = []; n = 0
    if x.get('l1'):
        for q, o, a in x['l1']['items']: n += 1; rows.append(['Listening 1', n, o[a]])
    if x.get('l2'):
        for q, a in x['l2']['p1']: n += 1; rows.append(['Listening 2 · short', n, a])
        for q, a in x['l2']['p2']: n += 1; rows.append(['Listening 2 · T/F', n, 'True' if a else 'False'])
    n = max(n, 15) if (x.get('grm') or x.get('vcb')) else n
    if x.get('grm'):
        for k, a in enumerate(x['grm']['ans']):
            n += 1; rows.append(['Grammar', n, re.findall(r'\{([^{}]+)\}', ' '.join(t for _, t in x['grm']['lines']))[k].split('|')[a]])
    if x.get('vcb'):
        n = max(n, 20)
        for o, a in zip(x['vcb']['opts'], x['vcb']['ans']): n += 1; rows.append(['Vocabulary', n, o[a]])
    if x.get('r1') or x.get('r2'): n = max(n, 25)
    if x.get('r1'):
        for q, o, a in x['r1']['mcq']: n += 1; rows.append(['Reading 1 · MCQ', n, o[a]])
        for q, a in x['r1']['comp']: n += 1; rows.append(['Reading 1 · completion', n, a])
    if x.get('r2'):
        for q, a in x['r2']['short']: n += 1; rows.append(['Reading 2 · short', n, a])
        for q, a in x['r2']['tf']: n += 1; rows.append(['Reading 2 · T/F', n, 'True' if a else 'False'])
    return rows


def build(D):
    exams = D.setdefault('exams', [])
    D['listen'] = []
    # ---------------------------------------------------------------- 10 model exams (real recordings)
    for n in range(1, 11):
        m = J(f'models/exam{n:02d}.json')
        c, e = m['chart'], m['email']
        a1 = f'audio/exam{n:02d}_part1.mp3'; a2 = f'audio/exam{n:02d}_part2.mp3'
        exams.append(dict(
            id=f'MT-{n:02d}', label=f'Model Exam {n}', kind='model',
            l1=dict(intro=m['listening1']['context'], items=mcq(m['listening1']['items']), script=script(m['listening1']['script']), audio=a1),
            l2=dict(intro=m['listening2']['context'], p1=shorts(m['listening2']['short']), p2=tfs(m['listening2']['tf']), script=script(m['listening2']['script']), audio=a2),
            grm=gram(m['grammar']['lines'], m['grammar']['items']), vcb=vocab(m['vocab']['passage'], m['vocab']['items']),
            r1=r1(m['reading1']), r2=r2(m['reading2']),
            w1=c, w1topic=chart_topic(c), w1type='CH', w2=e, w2topic=email_topic(e), w2type='FE' if e.get('formal') else 'IE'))
    # ---------------------------------------------------------------- past papers (questions of the previous final exams)
    L1, L2 = J('past/listening_t1.json'), J('past/listening_t2.json')
    R1, R2 = J('past/read1.json'), J('past/read2.json')
    V, G = J('past/vocab.json'), J('past/grammar.json')
    def lab(s):
        mm = re.search(r'(1st|2nd) Session (\d{4})-(\d{4})(?: \((\w)\))?', s)
        if not mm: return s
        return f"{mm.group(2)}–{mm.group(3)[2:]} · Session {mm.group(1)[0]}" + (f' ({mm.group(4)})' if mm.group(4) else '')
    for i, (a, b) in enumerate(zip(L1, L2), 1):
        exams.append(dict(id=f'EX-L{i:02d}', label=f'Listening {i:02d} · {lab(a["session"])}', kind='past', part='L', session=a['session'], noaudio=True,
            l1=dict(intro=a['context'], items=mcq(a['items']), script=None, audio=None),
            l2=dict(intro=b['context'], p1=shorts(b['short']), p2=tfs(b['tf']), script=None, audio=None)))
    for i, (a, b) in enumerate(zip(R1, R2), 1):
        exams.append(dict(id=f'EX-R{i:02d}', label=f'Reading {i:02d} · {lab(b["session"])}', kind='past', part='R', session=b['session'], r1=r1(a), r2=r2(b)))
    # grammar & vocabulary sets: pair the grammar dialogue and the vocabulary text of the same session
    clean = lambda s: re.sub(r'^G\. 10 ', '', s)
    vmap = {clean(v['session']): v for v in V}; used = set(); sets = []
    for g in G:
        v = vmap.get(clean(g['session']))
        if v: used.add(v['id'])
        sets.append((g, v))
    sets += [(None, v) for v in V if v['id'] not in used]
    for i, (g, v) in enumerate(sets, 1):
        s = (g or v)['session']; d = dict(id=f'GV-{i:02d}', kind='gv', part='G', session=s)
        if g and v: d['label'] = f'Grammar & Vocabulary {i:02d} · {lab(clean(s))}'
        elif g: d['label'] = f'Grammar only {i:02d} · {lab(clean(s))}'
        else: d['label'] = f'Vocabulary only {i:02d} · {lab(clean(s))}'
        if g: d['grm'] = gram(g['lines'], g['items'])
        if v: d['vcb'] = vocab(v['passage'], v['items'])
        exams.append(d)
    # writing tasks of the past papers (listed only; the Writing Lab owns practice and marking)
    D['pastWriting'] = dict(
        charts=[dict(id=c['id'], session=c['session'], title=c['title'], topic=chart_topic(c)) for c in J('past/chart.json')],
        emails=[dict(id=e['id'], session=e['session'], formal=bool(e['formal']), topic=email_topic(e)) for e in J('past/email.json')])
    # answer keys page
    D['examKeys'] = [[x['label'], x['kind'], [[p, n, str(a)] for p, n, a in keys_rows(x)]] for x in exams if x['kind'] in ('model', 'past', 'gv')]
    print('exams', len(exams), 'keys', len(D['examKeys']))


if __name__ == '__main__':
    D = {}; build(D); print(json.dumps(D['examKeys'][0], ensure_ascii=False)[:600])
