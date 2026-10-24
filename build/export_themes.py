"""Grade 10 themes exporter: vocabulary lessons, spelling bee data, grammar lessons (with visuals), theme tests (TT-n),
Grammar Booster (GB-1..10), irregular verbs (F-03) and phrasal verbs (F-04).  build(D) fills the shared dict D.
Source: /home/claude/es10/data (units/unitN.json + unitN_extra.json, booster.json)."""
import json, os, re, random, html

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'g10')
e = lambda s: html.escape(str(s), quote=False)
TNAMES = {1: 'New Media', 2: 'Climate Change', 3: 'Renewable Energy', 4: 'Civilisation'}
POS = {'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb', 'prep': 'preposition', 'conj': 'conjunction', 'phr': 'phrase',
       'phr v': 'phrasal verb', 'abbr': 'abbreviation', 'n / v': 'noun / verb', 'adj phr': 'adjective phrase'}

def load(p): return json.load(open(os.path.join(SRC, p), encoding='utf-8'))
def blank(s): return re.sub(r'_{3,}', '____', s)

# ------------------------------------------------------------------ word → bold form inside the example
SUF = r'(?:s|es|ed|d|ing|ly|ies|ied|er|ers|est|ation|ations|ment|ments|y|al|ally|ness|ive|ity|ful|able|n|en)?'
def forms(alt):
    alt = alt.strip()
    part = re.split(r'\s*(?:…|\.\.\.)\s*', alt)[0].strip()
    if not part: return []
    ws = part.split(); pats = []
    def wp(w, mode):
        w = re.escape(w)
        if mode == 0: return w
        raw = re.sub(r'\\?(e|y)$', '', w) if len(w) > 4 else w
        d = w[-1:] if len(w) > 2 else ''
        if mode == 1: return raw + SUF
        return w + r'(?:' + d + r')?(?:ed|ing|er|est|es|s)'      # doubled consonant: big → bigger, stop → stopped
    for mode in (0, 1, 2, 3):
        if mode == 3:
            if len(ws) < 2: continue
            pats.append(r'(?<![A-Za-z])' + r'\s+'.join(re.escape(w) if i < len(ws) - 1 else re.escape(w) + SUF for i, w in enumerate(ws)) + r'(?![A-Za-z])'); continue
        pats.append(r'(?<![A-Za-z])' + r'\s+'.join(wp(w, mode) if (mode == 0 or i == 0 or len(ws) == 1) else re.escape(w) for i, w in enumerate(ws)) + r'(?![A-Za-z])')
    return pats

def clean_alts(en):
    paren = re.findall(r'\(([^)]*)\)', en)
    base = re.sub(r'\s*\([^)]*\)', '', en).strip()
    alts = [a.strip() for a in base.split(' / ') if a.strip()]
    for p in paren:
        for x in p.split(','):
            x = x.strip()
            if x and re.match(r'^[a-z]+$', x): alts.append(x)          # (rose, risen) → extra forms; (to) / (MW) skipped
    return base, alts

OVR = {'come across': 'came across', 'hang up': 'hung up', 'run out of': 'ran out of', 'make up': 'made up', 'bring up': 'brought up', 'go up': 'went up',
       'go down': 'went down', 'rise': 'rose', 'considerably more than': 'considerably more', 'be to blame for': 'are to blame for', 'give away': 'gave away',
       'to power': 'powers', 'help with': 'help me with', 'treat equally': 'treats'}
EXFIX = {'public transport': 'Many people use public transport to get to work.'}
def mark(en, ex):
    if en in EXFIX: ex = EXFIX[en]; i = ex.find(en); return ex[:i] + '**' + en + '**' + ex[i + len(en):], True
    if en in OVR:
        i = ex.lower().find(OVR[en].lower())
        if i >= 0: return ex[:i] + '**' + ex[i:i + len(OVR[en])] + '**' + ex[i + len(OVR[en]):], True
    base, alts = clean_alts(en)
    cand = []
    for a in alts: cand += forms(a)
    for mode in range(4):          # exact first, then inflected, then doubled consonant
        for a in alts:
            ps = forms(a)
            if len(ps) > mode:
                m = re.search(ps[mode], ex, re.I)
                if m:
                    return ex[:m.start()] + '**' + m.group(0) + '**' + ex[m.end():], True
    return ex, False

POSD = lambda p: POS.get(p, p)

def build(D):
    TN = TNAMES
    D['tn'] = TN
    D['vocab'], D['grammar'], D['found'], D['tt'] = [], [], [], {}
    D.setdefault('themeKeys', [])
    unmatched = []
    UNITS = {n: load(f'units/unit{n}.json') for n in range(1, 5)}
    EXTRA = {n: load(f'units/unit{n}_extra.json') for n in range(1, 5)}

    # ---------------------------------------------------------------- vocabulary lessons
    for n in range(1, 5):
        U = UNITS[n]; X = EXTRA[n]
        for k, les in enumerate(U['lessons'], 1):
            W = []
            for w in les['words']:
                base, alts = clean_alts(w['en'])
                first = alts[0] if alts else base
                first = first.replace('…', '...').strip()
                ex, ok = mark(w['en'], w['ex'])
                if not ok: unmatched.append((n, k, w['en'], w['ex']))
                W.append(dict(w=first, alt=base, p=POSD(w['pos']), ar=w['ar'], d='', ex=ex, s=bool(w.get('star'))))
            ex2 = X.get(les['id'], {})
            mcq = [[blank(q['q']), q['options'], q['answer']] for q in les['mcq']] + [[blank(q['q']), q['options'], q['answer']] for q in ex2.get('mcq2', [])]
            def clz(c):
                return [re.sub(r'\((\d)\)_+', r'[\1]', c['passage']), [[it['options'], it['answer']] for it in c['items']]]
            cl = clz(les['cloze']); cl2 = clz(ex2['exam']) if ex2.get('exam') else None
            D['vocab'].append(dict(code=f'T{n}-V{k}', theme=n, tname=TN[n], title=les['title'], ar=les['title_ar'], words=W, mcq=mcq, cloze=cl,
                                   cloze2=cl2, extras={}, nmcq1=len(les['mcq'])))
    if unmatched:
        print('UNMATCHED example forms:', len(unmatched))
        for u in unmatched: print('  ', u)

    # ---------------------------------------------------------------- grammar
    def ex_items(g):
        items, comp, dlgs = [], [], []
        for ex in g['exercises']:
            kind = ex['kind']
            if kind == 'choose':
                for it in ex['items']:
                    items.append([re.sub(r'\[\[\d+\]\]', '____', blank(it['q'])), it['options'], it['answer']])
            elif kind == 'fill':
                bank = ex.get('bank')
                for it in ex['items']:
                    q = blank(it['q'])
                    if bank: q += '   [' + ', '.join(bank) + ']'
                    comp.append([q, it['answer']])
            elif kind == 'dialogue':
                by = {it['n']: it for it in ex['items']}
                lines = []
                for ln in ex['lines']:
                    t = re.sub(r'\[\[(\d+)\]\]', lambda m: '{' + '|'.join(by[int(m.group(1))]['options']) + '}', ln['text'])
                    lines.append([ln['speaker'], t])
                ans = [by[i]['answer'] for i in sorted(by)]
                dlgs.append(dict(title=ex['title'], lines=lines, ans=ans))
                # also as single choose-items so the quick "Choose the answer" game covers them
                for i in sorted(by):
                    ln = next(l for l in ex['lines'] if f'[[{i}]]' in l['text'])
                    q = re.sub(r'\[\[(\d+)\]\]', lambda m: '____' if int(m.group(1)) == i else '…', ln['text'])
                    items.append([f"{ln['speaker']}: {q}", by[i]['options'], by[i]['answer']])
        return items, comp, dlgs

    for n in range(1, 5):
        for gi, g in enumerate(UNITS[n]['grammar'], 1):
            items, comp, dlgs = ex_items(g)
            D['grammar'].append(dict(code=f'T{n}-G{gi}', theme=n, title=g['title'], ar=g['title_ar'], summary=summary(g), items=items, complete=comp, dialogues=dlgs, gid=g['id']))
    B = load('booster.json')
    for gi, g in enumerate(B['grammar'], 1):
        items, comp, dlgs = ex_items(g)
        D['found'].append(dict(code=g['id'], title=g['title'], ar=g['title_ar'], summary=summary(g), items=items, complete=comp, dialogues=dlgs, gid=g['id']))
    # irregular + phrasal verbs
    seen, irr = set(), []
    for v in B['irregular']:
        if v['base'] in seen: continue
        seen.add(v['base']); irr.append([v['base'], v['past'], v['pp'], v['ar']])
    D['irreg'] = irr
    D['phr'] = [[p['pv'], p['ar'], p['meaning'], p['ex']] for p in B['phrasal']]

    # ---------------------------------------------------------------- theme tests (one per unit, 28 items)
    for n in range(1, 5):
        U = UNITS[n]; X = EXTRA[n]; L = U['lessons']; nl = len(L); rnd = random.Random(1000 + n)
        parts = []
        ia, ib = max(1, round(nl * .25)), min(nl - 1, round(nl * .72))
        if ib == ia: ib = (ia + 2) % nl
        la, lb = L[ia], L[ib]
        def tx(c): return re.sub(r'\((\d)\)_+', r'{\1}', c['passage'])
        parts.append(dict(kind='cloze', sec='vocab', title='Vocabulary · text 1', body=tx(la['cloze']), opts=[it['options'] for it in la['cloze']['items']], ans=[it['answer'] for it in la['cloze']['items']], ref=la['id']))
        parts.append(dict(kind='cloze', sec='vocab', title='Vocabulary · text 2', body=tx(X[lb['id']]['exam']), opts=[it['options'] for it in X[lb['id']]['exam']['items']], ans=[it['answer'] for it in X[lb['id']]['exam']['items']], ref=lb['id']))
        # 8 MCQ from eight different lessons (mix of the first and the second set)
        order = [i for i in range(nl) if i not in (ia, ib)]
        rnd.shuffle(order); pick = sorted(order[:8]); mq = []
        for j, i in enumerate(pick):
            pool = L[i]['mcq'] if j % 2 == 0 else X[L[i]['id']]['mcq2']
            q = rnd.choice(pool); mq.append([blank(q['q']), q['options'], q['answer'], L[i]['id']])
        parts.append(dict(kind='mcq', sec='vocab', title='Vocabulary · choose the correct word', items=mq))
        # 2 grammar dialogues
        gl = U['grammar']; gpick = {1: [0, 1], 2: [0, 1], 3: [1, 3], 4: [0, 1]}[n]
        for gidx in gpick:
            g = gl[gidx]; dl = next(x for x in g['exercises'] if x['kind'] == 'dialogue'); by = {it['n']: it for it in dl['items']}
            lines = [[ln['speaker'], re.sub(r'\[\[(\d+)\]\]', lambda m: '{' + '|'.join(by[int(m.group(1))]['options']) + '}', ln['text'])] for ln in dl['lines']]
            parts.append(dict(kind='dlg', sec='grammar', title='Grammar · ' + g['title'].split(':')[0].split('(')[0].strip(), gcode=f'T{n}-G{gidx + 1}', lines=lines, ans=[by[i]['answer'] for i in sorted(by)]))
        total = 10 + len(mq) + sum(len(p['ans']) for p in parts if p['kind'] == 'dlg')
        D['tt'][f'TT-{n}'] = dict(id=f'TT-{n}', theme=n, label=f'Theme {n} test · {TN[n]}', parts=parts, total=total)
        # answer keys for the "Answer keys" page
        rows, q = [], 0
        for p in parts:
            if p['kind'] == 'mcq':
                for it in p['items']: q += 1; rows.append([q, it[1][it[2]]])
            else:
                for i, a in enumerate(p['ans']):
                    q += 1
                    if p['kind'] == 'cloze': rows.append([q, p['opts'][i][a]])
                    else:
                        gl_ = re.findall(r'\{([^{}]+)\}', ' '.join(t for _, t in p['lines']))
                        rows.append([q, gl_[i].split('|')[a]])
        D['themeKeys'][:] = [x for x in D['themeKeys'] if x[0] != f'Theme {n} test · {TN[n]}']
        D['themeKeys'].append([f'Theme {n} test · {TN[n]}', rows])
    print('themes: vocab lessons', len(D['vocab']), '· grammar', len(D['grammar']), '· booster', len(D['found']), '· irregular', len(irr), '· phrasal', len(D['phr']),
          '· tests', {k: v['total'] for k, v in D['tt'].items()})

# ------------------------------------------------------------------ grammar summary (rule / table / examples / tip + visuals)
def row(cells):
    return ''.join(f'<td class="{"ar" if re.search(r"[؀-ۿ]", c) and not re.search(r"[A-Za-z]", c) else ""}">{e(c)}</td>' for c in cells)
def summary(g):
    S, shown = [], False
    for b in g['explain']:
        t = b['t']
        if t == 'rule':
            S.append(f'<p>{e(b["en"])}</p><p class="ar">{e(b["ar"])}</p>')
            if not shown:
                shown = True; S.append(VIS.get(g['id'], lambda: '')())
        elif t == 'table':
            S.append((f'<h4>{e(b["title"])}</h4>' if b.get('title') else '') + '<div style="overflow-x:auto"><table class="k"><tr>' + ''.join(f'<th>{e(h)}</th>' for h in b['headers']) + '</tr>' + ''.join('<tr>' + row(r) + '</tr>' for r in b['rows']) + '</table></div>')
        elif t == 'examples':
            S.append('<h4>Examples <span class="ar">أمثلة</span></h4><table class="k">' + ''.join(f'<tr><td><i>{e(x["en"])}</i></td><td class="ar">{e(x["ar"])}</td></tr>' for x in b['items']) + '</table>')
        elif t == 'tip':
            S.append(f'<div class="tip"><b>Watch out:</b> {e(b["en"])}<br><span class="ar">{e(b["ar"])}</span></div>')
    return ''.join(S)

# ---- visuals (CSS classes .gv .lad .fx .fa live in hub_src.html)
def gv(title, ar, inner): return f'<div class="gv"><div class="k">{e(title)} <span class="ar">{e(ar)}</span></div>{inner}</div>'
def fx(t, c='var(--t2)', small=''): return f'<span class="fx" style="--c:{c}">{e(t)}{f"<small>{e(small)}</small>" if small else ""}</span>'
def fa(label, rev=False): return f'<span class="fa{" rv" if rev else ""}">{e(label)}</span>'
def vis_ladder():
    def lad(rows):
        out = ''
        for a, b, c in rows:
            out += '<div class="lad">' + ''.join(f'<div style="height:{h}%;--p:{p}%"><span>{e(x)}<small>{e(s)}</small></span></div>' for (x, s), h, p in zip(((a, 'basic · الأصل'), (b, 'two things · شيئان'), (c, '3 or more · ثلاثة فأكثر')), (34, 64, 100), (14, 34, 62))) + '</div>'
        return out
    return gv('The comparison ladder', 'سلّم المقارنة', lad([('tall', 'taller than', 'the tallest')]) + '<div style="height:10px"></div>' + lad([('expensive', 'more expensive than', 'the most expensive')]))
def vis_asas():
    def bar(name, w, t, c='var(--t2)'):
        return f'<div class="asr"><span class="asn">{e(name)}</span><span class="asb"><i style="width:{w}%;--c:{c}"></i></span><span class="ast">{e(t)}</span></div>'
    return gv('Equal or lower?', 'متساوٍ أم أقل؟',
        bar('Ali', 100, '1.70 m') + bar('Salim', 100, '1.70 m') + bar('Huda', 80, '1.36 m', 'var(--t1)') +
        '<p style="margin:8px 0 2px"><b>Ali is as tall as Salim.</b> <span class="muted small">( = )</span><br><b>Huda is not as tall as Ali.</b> <span class="muted small">( &lt; )</span></p>')
def flow(a, la, b, rev=False):
    return '<div class="flow">' + fx(a[0], a[1], a[2]) + fa(la, rev) + fx(b[0], b[1], b[2]) + '</div>'
def vis_cause(sentenceA='The planet is getting warmer', sentenceB='the ice is melting', second=True):
    C, R = 'var(--t1)', 'var(--t2)'
    inner = ('<div class="legend2">' + fx('Cause · السبب', C) + fx('Effect · النتيجة', R) + '</div>' +
        flow((sentenceA, C, ''), 'so', (sentenceB, R, '')) +
        flow((sentenceB, R, ''), 'because', (sentenceA.lower() if False else sentenceA, C, ''), rev=True) +
        flow((sentenceA, C, ''), 'Therefore,', (sentenceB, R, '')))
    return gv('Cause → effect', 'السبب ← النتيجة', inner)
def vis_cause_solar():
    C, R = 'var(--t1)', 'var(--t2)'
    return gv('Reason → result', 'السبب ← النتيجة', '<div class="legend2">' + fx('Reason · السبب', C) + fx('Result · النتيجة', R) + '</div>' +
        flow(('Sunlight is free', C, ''), 'so', ('we use solar panels', R, '')) +
        flow(('We use solar panels', R, ''), 'because', ('sunlight is free', C, ''), rev=True) +
        flow(('Sunlight is free', C, ''), 'Therefore,', ('we use solar panels', R, '')))
def vis_will():
    return gv('Will = the future', 'will للمستقبل', '<div class="flow">' + fx('NOW · الآن', 'var(--t1)') + fa('will + verb') + fx('FUTURE · المستقبل', 'var(--t2)', 'tomorrow · soon · next year · in the future') + '</div>'
        '<p style="margin:8px 0 2px"><b>It will rain tomorrow.</b> &nbsp; <b>I won\'t be late.</b> <span class="muted small">( won\'t = will not )</span></p>')
def vis_add():
    return gv('Adding one more point', 'إضافة فكرة', '<div class="flow">' + fx('Solar power is clean.', 'var(--t1)') + '<span class="fp">+</span>' + fx('also / In addition, / Moreover,', 'var(--t2)') + '<span class="fp">+</span>' + fx('It is free.', 'var(--t1)') + '</div>')
def vis_contrast():
    return gv('Two different ideas', 'فكرتان متعارضتان', '<div class="flow">' + fx('Solar panels are expensive', 'var(--t1)') + '<span class="fp">⚖</span>' + fx('they save money later', 'var(--t1)') + '</div>'
        '<div class="flow" style="margin-top:8px">' + fx('but', 'var(--t2)', ', before it') + fx('However,', 'var(--t2)', 'new sentence') + fx('although', 'var(--t2)', 'at the start') + fx('On the other hand,', 'var(--t2)', 'new sentence') + '</div>')
def vis_ending():
    return gv('-ing or -ed?', 'الصفة المنتهية بـ ing أم ed؟', '<div class="flow">' + fx('a boring film', 'var(--t1)', '-ing: the thing causes the feeling · الشيء') + fx('a bored student', 'var(--t2)', '-ed: the person has the feeling · الشخص') + '</div>')
def vis_passive():
    A, V, O = 'var(--t1)', 'var(--t2)', 'var(--wr)'
    return gv('Active → passive', 'من المبني للمعلوم إلى المبني للمجهول',
        '<div class="flow"><b class="small muted" style="width:56px">Active</b>' + fx('The Egyptians', A, 'subject · الفاعل') + fx('built', V, 'past simple') + fx('the pyramids', O, 'object · المفعول') + '</div>'
        '<div style="text-align:center;font-size:22px;color:var(--t2)">⇅</div>'
        '<div class="flow"><b class="small muted" style="width:56px">Passive</b>' + fx('The pyramids', O, 'new subject') + fx('were built', V, 'was / were + V3') + fx('by the Egyptians', A, 'agent · by + الفاعل') + '</div>')
def vis_cond():
    return gv('Imaginary situation', 'موقف خيالي أو غير محتمل', '<div class="flow">' + fx('If + past simple', 'var(--t1)', 'If I lived in ancient Egypt,') + '<span class="fp">,</span>' + fx('would + infinitive', 'var(--t2)', 'I would see the pyramids.') + '</div>')
def vis_adjprep():
    return gv('Adjective + preposition', 'صفة + حرف جر', '<div class="flow">' + fx('famous', 'var(--t1)', 'adjective') + '<span class="fp">+</span>' + fx('for', 'var(--t2)', 'preposition') + '<span class="fp">+</span>' + fx('its frankincense', 'var(--wr)', 'noun / pronoun / -ing') + '</div>')
VIS = {'U1-G1': vis_ladder, 'U1-G2': vis_asas, 'U2-G1': vis_cause, 'U2-G2': vis_will, 'U3-G1': vis_add, 'U3-G2': vis_contrast,
       'U3-G3': vis_cause_solar, 'U3-G5': vis_ending, 'U4-G1': vis_passive, 'U4-G2': vis_cond, 'U4-G3': vis_adjprep}

if __name__ == '__main__':
    D = {}; build(D); print(len(json.dumps(D)) // 1024, 'KB')
