"""Writing Lab exporter (Grade 10): fills D['wlab'] (models CH/IE/FE for the staged path, samples, charts) and D['wtopics'] (topic bank by theme).
Sources: build/data/writing_lab.py + build/data/w10/*.json (copies of /home/claude/es10/data partd / past chart+email / model exams).
Shapes
  D['wlab'] = {models: {CH:[entry], IE:[entry], FE:[entry]}, samples: {CH,IE,FE}, charts: {id: {id,title,ylabel,unit,categories,series,src}}}
  entry = {id, prompt, label, src, frame_topic, chart (CH only: chart id), paras:[{name, ar, s:[[linker, text, role, slot]]}]}
  D['wtopics'] = {CH|IE|FE: {theme('1'..'4' or '0'): [{t: topic text sent to the AI, src, ch?: chart id}]}}"""
import os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, 'data'))
import writing_lab as WL

KW = {1: r'phone|internet|social media|media|online|app\b|apps\b|video|device|website|blog|screen|digital|news|computer|technolog|laptop|game|film|movie|book genre|drink',
      2: r'climate|rain|weather|recycl|waste|plastic|environment|pollution|reusable|carbon|transport|temperature|green|bins|tree|global warming|rubbish|reduce',
      3: r'solar|wind|renewable|energy|electric|power|hydro|earth heat',
      4: r'histor|ancient|civili[sz]ation|museum|fort|heritage|culture|tradition|trip|visit|holiday|destination|maya|egypt|camp|national day|school subject|hobb|club'}
def theme_of(t):
    best = (0, 0)
    for k, rx in KW.items():
        c = len(re.findall(rx, t, re.I))
        if c > best[0]: best = (c, k)
    return best[1]

def clean_para(models):
    for e in models:
        for p in e['paras']:
            for s in p['s']:
                s[1] = re.sub(r'\s+', ' ', s[1]).strip()

def build(D):
    charts = WL.load_charts(); emails = WL.load_emails()
    models = {'CH': [], 'IE': [], 'FE': []}
    for c in charts:
        if len(c['series']) != 2: continue            # the template is for two groups (boys / girls …)
        paras = WL.parse_chart(c)
        assert len(paras) == 4, (c['id'], len(paras))
        models['CH'].append(dict(id=c['id'], prompt=c['title'], label=c['title'], src=c['src'], frame_topic=c['title'], chart=c['id'], paras=paras))
    for e in emails:
        T = 'FE' if e['formal'] else 'IE'
        paras = WL.parse_email(e, e['formal'])
        models[T].append(dict(id=e['id'], prompt=e['prompt'], label=e['label'], src=e['src'], frame_topic=e['prompt'], paras=paras))
    for T in ('IE', 'FE'):   # make sure the labels in the drop-down are unique
        seen = {}
        for m in models[T]:
            seen[m['label']] = seen.get(m['label'], 0) + 1
            if seen[m['label']] > 1: m['label'] += ' (%d)' % seen[m['label']]
    for l in models.values(): clean_para(l)
    chart_map = {c['id']: {k: c[k] for k in ('id', 'title', 'ylabel', 'unit', 'categories', 'series', 'src')} for c in charts}
    samples = {T: dict(s) for T, s in WL.SAMPLES.items()}
    sc = samples['CH']; sc['chartObj'] = chart_map[sc.pop('chart')]
    D['wlab'] = dict(models=models, samples=samples, charts=chart_map)

    WT = {k: {} for k in ('CH', 'IE', 'FE')}
    def add(T, t, src, ch=None):
        t = re.sub(r'\s+', ' ', t).strip()
        if t and not any(x['t'] == t for g in WT[T].values() for x in g):
            x = dict(t=t, src=src)
            if ch: x['ch'] = ch
            WT[T].setdefault(str(theme_of(t)), []).append(x)
    for c in charts: add('CH', 'Describe the bar chart: ' + c['title'] + (' (' + c['id'] + ')' if any(o['title'] == c['title'] and o is not c for o in charts) else ''), c['src'], c['id'])
    for e in emails: add('FE' if e['formal'] else 'IE', e['prompt'], e['src'])
    for T, l in WL.TOPICS.items():
        for t in l: add(T, t, 'English Summit 10')
    D['wtopics'] = WT
    print('writing:', {T: len(v) for T, v in models.items()}, 'topics', {T: {k: len(v) for k, v in g.items()} for T, g in WT.items()})

if __name__ == '__main__':
    D = {}; build(D)
