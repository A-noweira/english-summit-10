"""Guided Training (GT-x) + How-to-Answer (HOW-x) data for Grade 10 -> D['gt'].
Everything is DERIVED from the existing question banks in D['exams'] (so run after export_exams):
  evidence sentence  = the passage / transcript sentence that best matches the answer + question words
  keywords           = content words of the question (or the words around a gap)
  wrong-option reason= generic code by overlap with the passage (nm not mentioned / dd other detail / tw twisted / num number)
  answer type / rule = deterministic lexicon (who -> person, has|have -> have/has/had ...), null when unsure (the step is skipped)
The only hand-authored text is build/data/g10/gt_types.json (Arabic + English strategy per question type).
Item shape (compact): {x exam id, i index in its section, ev [para, sentence], k [keywords], r [reason code per option],
                       t answer type, u grammar rule, w word type, l dialogue line (grammar)}.  The client rebuilds the question from D.exams."""
import json, os, re

H = os.path.dirname(os.path.abspath(__file__))
SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"“‘\'])')      # the same regular expression is used in hub_src.html (gtSents)
STOP = set('''a an the of in on at to for from with by about as is are was were be been am do does did has have had will would can could should
must may might shall it its this that these those he she they we you i me him her them us my your his their our and or but if so than then
what who whom whose which when where why how many much more most some any not no yes there here also very too just only into out up down
over under after before during between each every other another one two three four five six seven eight nine ten first second third
said say says tell tells told like get gets got go goes went make makes made take takes took'''.split())
CAP = 60          # items kept per question type


def sents(paras):
    out = []
    for p, t in enumerate(paras):
        for s, x in enumerate(SPLIT.split(t.strip())):
            if x.strip(): out.append((p, s, x.strip()))
    return out


def toks(t): return re.findall(r"[A-Za-z0-9']+", t.lower())


def stem(w):
    w = w.strip("'")
    for suf in ('ing', 'ed', 'es', 's', 'ly'):
        if w.endswith(suf) and len(w) - len(suf) >= 3: w = w[:-len(suf)]; break
    return w[:-1] if w.endswith('e') and len(w) > 3 else w


def content(t): return [w for w in toks(t) if w not in STOP and (len(w) > 2 or w.isdigit())]
def stems(t): return {stem(w) for w in content(t)}


def best_sentence(S, qs, aset=None, ans_text=None):
    """-> (index into S, score, margin)"""
    sc = []
    for p, s, x in S:
        st = stems(x); v = 2 * len(qs & st)
        if aset: v += 3 * len(aset & st)
        if ans_text:
            a = ' '.join(toks(ans_text)); xs = ' ' + ' '.join(toks(x)) + ' '
            if a and (' ' + a + ' ') in xs: v += 6
        sc.append(v)
    order = sorted(range(len(S)), key=lambda i: -sc[i])
    if not order: return None, 0, 0
    b = order[0]
    return b, sc[b], sc[b] - (sc[order[1]] if len(order) > 1 else 0)


def reason(opt, S, ev, ans_has_num):
    ost = stems(opt)
    allst = set().union(*[stems(x) for _, _, x in S]) if S else set()
    evst = stems(S[ev][2]) if ev is not None else set()
    nums = set(re.findall(r'\d+', opt))
    if nums and not nums <= set(re.findall(r'\d+', S[ev][2])): return 'num'
    if not ost: return 'nm'
    if len(ost & allst) / len(ost) < .5: return 'nm'
    if len(ost & evst) / len(ost) >= .5: return 'tw'
    return 'dd'


WH = [(r'\bhow (many|much)\b|\bnumber\b|\bpercentage\b|\bhow old\b', 'num'), (r'\bwho\b|\bwhom\b|\bwhose\b|\bwhich (person|student|teacher|boy|girl)\b', 'per'),
      (r'\bwhere\b|\(country\)|\(city\)|\(place\)|\bwhich (country|city|place)\b', 'plc'),
      (r'\bwhen\b|\bwhat time\b|\bwhat day\b|\bwhich (year|day|month|season)\b|\(year\)|\(day\)|\bhow long\b|\bhow often\b|\bhow soon\b|\(time\)|\bwhat year\b', 'tim'),
      (r'\bwhy\b|\bwhat is the reason\b|\bwhat was the reason\b', 'why'), (r'\bhow\b', 'way')]


def ans_type(q, a, sa_kind):
    ql = q.lower()
    for rx, c in WH:
        if re.search(rx, ql): return c
    if re.fullmatch(r'\d[\d,.:%]*', a.strip()): return 'num'
    return 'thg' if (ql.startswith('what') or ql.startswith('which')) else None


def vocab_rule(correct, opts):
    def cls(w):
        w = w.lower().split()[-1] if w else ''
        if w.endswith('ly') and len(w) > 4: return 'adv'
        if re.search(r'(tion|sion|ment|ness|ity|ance|ence|ship)s?$', w): return 'nou'
        if re.search(r'(ful|less|ous|ive|able|ible)$', w): return 'adj'
        return None
    c = cls(correct)
    if not c: return None
    # the type is shown only when at least one wrong option clearly belongs to another class
    others = [cls(o) for o in opts if o != correct]
    return c if any(o and o != c for o in others) else None


LEX = [('forsince', {'for', 'since'}), ('art', {'a', 'an', 'the'}), ('be', {'is', 'are', 'was', 'were', 'am', "isn't", "aren't", "wasn't", "weren't"}),
       ('have', {'has', 'have', 'had', "hasn't", "haven't"}), ('do', {'do', 'does', 'did', "don't", "doesn't", "didn't"}),
       ('modal', {'can', 'could', 'should', 'must', 'may', 'might', "can't", "shouldn't", "mustn't", "couldn't"}),
       ('rel', {'who', 'whose', 'which', 'that', 'whom'}), ('qw', {'what', 'when', 'where', 'why', 'how'}),
       ('prep', {'in', 'on', 'at', 'to', 'from', 'of', 'with', 'by', 'about', 'into', 'during', 'between', 'under', 'over', 'through', 'across'}),
       ('quant', {'much', 'many', 'few', 'little', 'some', 'any', 'enough', 'too', 'very', 'a lot of', 'lots of'}),
       ('pron', {'he', 'she', 'they', 'him', 'her', 'them', 'his', 'their', 'its', 'my', 'your', 'our', 'we', 'i', 'you', 'me', 'us', 'myself', 'himself', 'herself', 'themselves', 'yourself', 'mine', 'yours', 'hers', 'theirs'}),
       ('link', {'because', 'so', 'but', 'although', 'though', 'however', 'and', 'or', 'unless', 'while', 'whereas', 'therefore', 'if', 'when', 'since'}),
       ('comp', {'than', 'as', 'more', 'most', 'less', 'least'})]


def gram_rule(correct, opts):
    c = correct.lower(); w = c.split()
    if len(w) >= 2 and w[0] in ('has', 'have'): return 'pp'
    if len(w) >= 2 and w[0] == 'had': return 'pap'
    if len(w) >= 2 and w[0] in ('will', "won't", 'would'): return 'fut'
    if len(w) >= 2 and w[0] in ('am', 'is', 'are') and w[-1].endswith('ing'): return 'prc'
    if len(w) >= 2 and w[0] in ('was', 'were') and w[-1].endswith('ing'): return 'pac'
    if len(w) >= 2 and w[0] in ('am', 'is', 'are', 'was', 'were', 'be', 'been') and (w[-1].endswith('ed')): return 'pas'
    if len(w) >= 2 and w[0] in ('to',): return 'inf'
    if len(w) == 1:
        if w[0].endswith('ing') and len(w[0]) > 5: return 'ger'
        for code, S in LEX:
            if w[0] in S: return code
        if w[0].endswith('ed') and len(w[0]) > 4: return 'pas'
        if w[0].endswith('s') and not w[0].endswith('ss') and len(w[0]) > 3 and any(o.lower().rstrip('s') == w[0].rstrip('s') or True for o in opts): return None
    else:
        for code, S in LEX:
            if c in S: return code
    return None


CLUE = {'yesterday', 'last', 'ago', 'since', 'for', 'now', 'always', 'usually', 'already', 'yet', 'just', 'every', 'tomorrow', 'next', 'never', 'ever', 'when', 'while',
        'if', 'because', 'who', 'whose', 'which', 'than', 'as', 'at', 'on', 'in', 'recently', 'soon', 'often', 'sometimes', 'today', 'tonight', 'once', 'twice', 'then', 'before', 'after', 'so', 'but', 'although'}


def gap_kw(text_before, text_after, subj_n=3):
    """words around a gap: the clue words of the line + the neighbours"""
    b = toks(text_before)[-subj_n:]; a = toks(text_after)[:2]
    near = [w for w in b + a if w not in ('a', 'an', 'the')]
    cl = [w for w in toks(text_before + ' ' + text_after) if w in CLUE]
    out = []
    for w in cl + near:
        if w not in out: out.append(w)
    return out[:6]


# ----------------------------------------------------------------------------------------------------- builders per type
def mk(D, X, t, mode, skill):
    return D['types'].setdefault(t, dict(skill=skill, mode=mode, items=[], n=0))


def add_mc(T, x, sect, i, q, opts, ans, S, rid, aud):
    qs = stems(q); a_set = stems(opts[ans])
    b, sc, mg = best_sentence(S, qs, a_set)
    if b is None or sc < 4 or mg < 1: return
    kw = [w for w in content(q)][:5]
    if not kw: return
    ev = [S[b][0], S[b][1]]
    r = [None if k == ans else reason(o, S, b, False) for k, o in enumerate(opts)]
    T['items'].append(dict(x=x, i=i, ev=ev, k=kw, r=r, sc=sc + mg))


def add_sa(T, x, i, q, a, S, kind):
    qs = stems(re.sub(r'\([^)]*\)|_+', ' ', q)); aset = stems(a)
    b, sc, mg = best_sentence(S, qs, aset, a)
    if b is None or sc < 4 or mg < 1: return
    kw = content(re.sub(r'\([^)]*\)|_+', ' ', q))[:5]
    if not kw: return
    it = dict(x=x, i=i, ev=[S[b][0], S[b][1]], k=kw, sc=sc + mg); t = ans_type(q, a, kind)
    if t: it['t'] = t
    T['items'].append(it)


def add_tf(T, x, i, q, a, S):
    qs = stems(q); b, sc, mg = best_sentence(S, qs)
    if b is None or sc < 4 or mg < 1: return
    kw = content(q)[:5]
    if not kw: return
    T['items'].append(dict(x=x, i=i, ev=[S[b][0], S[b][1]], k=kw, sc=sc + mg))


def build(D):
    X = D['exams']; G = dict(types={}, how={}, ex={})
    TYPES = {}
    order = lambda x: (0 if x['kind'] == 'mock' else 1 if x['kind'] == 'model' else 2, x['id'])
    for x in sorted(X, key=order):
        e = x['id']
        if x.get('l1') and x['l1'].get('script'):
            S = sents([l[1] for l in x['l1']['script']])
            T = mk(G, X, 'L1', 'mc', 'L')
            for i, (q, o, a) in enumerate(x['l1']['items']): add_mc(T, e, 'l1', i, q, o, a, S, e, True)
        if x.get('l2') and x['l2'].get('script'):
            S = sents([l[1] for l in x['l2']['script']])
            T = mk(G, X, 'L2A', 'sa', 'L')
            for i, (q, a) in enumerate(x['l2']['p1']): add_sa(T, e, i, q, a, S, 'l')
            T = mk(G, X, 'L2B', 'tf', 'L')
            for i, (q, a) in enumerate(x['l2']['p2']): add_tf(T, e, i, q, a, S)
        if x.get('grm'):
            T = mk(G, X, 'GRM', 'gap', 'G'); gi = 0
            for li, (sp, t) in enumerate(x['grm']['lines']):
                for m in re.finditer(r'\{([^{}]+\|[^{}]+)\}', t):
                    o = m.group(1).split('|'); a = x['grm']['ans'][gi]
                    it = dict(x=e, i=gi, l=li, ev=[li, 0], k=gap_kw(t[:m.start()], t[m.end():]), sc=5)
                    ru = gram_rule(o[a], o)
                    if ru: it['u'] = ru
                    if it['k']: T['items'].append(it)
                    gi += 1
        if x.get('vcb'):
            T = mk(G, X, 'VCB', 'gap', 'G')
            S = sents([x['vcb']['body']])
            for i, o in enumerate(x['vcb']['opts']):
                a = x['vcb']['ans'][i]; tag = '{%d}' % (i + 1)
                si = next((k for k, (p, s, tx) in enumerate(S) if tag in tx), None)
                if si is None: continue
                tx = S[si][2]; j = tx.index(tag)
                it = dict(x=e, i=i, ev=[S[si][0], S[si][1]], k=gap_kw(tx[:j], tx[j + 3:], 3), sc=5)
                w = vocab_rule(o[a], o)
                if w: it['w'] = w
                if it['k']: T['items'].append(it)
        if x.get('r1'):
            S = sents(x['r1']['text']); r = x['r1']
            T = mk(G, X, 'R1A', 'mc', 'R')
            for i, (q, o, a) in enumerate(r['mcq']): add_mc(T, e, 'r1m', i, q, o, a, S, e, False)
            T = mk(G, X, 'R1B', 'sa', 'R')
            for i, (q, a) in enumerate(r['comp']): add_sa(T, e, i, q, a, S, 'c')
        if x.get('r2'):
            S = sents(x['r2']['text']); r = x['r2']
            T = mk(G, X, 'R2A', 'sa', 'R')
            for i, (q, a) in enumerate(r['short']): add_sa(T, e, i, q, a, S, 's')
            T = mk(G, X, 'R2B', 'tf', 'R')
            for i, (q, a) in enumerate(r['tf']): add_tf(T, e, i, q, a, S)
    # ---- keep CAP items per type: mock tasks first, then model exams, then past papers (round-robin over exams); examples = best mock items
    for code, T in G['types'].items():
        its = T['items']; seen = {}; keep = []
        for it in its:
            seen.setdefault(it['x'], []).append(it)
        rr = []
        while any(seen.values()) and len(rr) < 9999:
            for k in list(seen):
                if seen[k]: rr.append(seen[k].pop(0))
        mock = [i for i in rr if i['x'].startswith('MK-')]
        rest = [i for i in rr if not i['x'].startswith('MK-')]
        keep = (mock + rest)[:CAP]
        ex = sorted([i for i in mock], key=lambda i: -i['sc'])
        exs = []; used = set()
        for i in ex:
            if i['x'] not in used: exs.append(i); used.add(i['x'])
            if len(exs) == 3: break
        for i in keep:
            i.pop('sc', None)
        for i in exs: i['sc'] = 1
        T['items'] = keep
        T['ex'] = [(i['x'], i['i']) for i in exs]
        # make sure the examples are inside the kept list
        for i in exs:
            if not any(k['x'] == i['x'] and k['i'] == i['i'] for k in keep):
                i.pop('sc', None); keep.append(i)
        for i in keep: i.pop('sc', None)
        T['n'] = len(keep)
    # ---- writing: examples (model answers of the first mock task of each kind)
    mw = [x for x in X if x['id'].startswith('MK-W')]
    G['wex'] = dict(WC=mw[0]['id'], WI=next(x['id'] for x in mw if not x['w2'].get('formal')), WF=next(x['id'] for x in mw if x['w2'].get('formal')))
    txt = json.load(open(os.path.join(H, 'data', 'g10', 'gt_types.json'), encoding='utf-8'))
    G['txt'] = txt
    for t in list(G['types']):
        assert t in txt['types'], 'gt_types.json misses ' + t
    for t in txt['types']:
        if t not in G['types']: G['types'][t] = dict(skill=txt['types'][t]['skill'], mode='w', items=[], n=0, ex=[])
    D['gt'] = G
    print('gt', {k: v['n'] for k, v in G['types'].items()})


if __name__ == '__main__':
    import export_exams
    D = {}; export_exams.build(D); build(D)
