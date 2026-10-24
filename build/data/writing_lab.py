# Writing Lab — Grade 10, built on Mr Mohamed's own method (fixed templates + colour code of the linkers).
# Three tracks: CH (Writing 1: describe a bar chart, /5), IE (informal e-mail, /10), FE (formal e-mail, /10).
# A sentence = [linker, text, role, slot].  Roles: FIX fixed phrase · PARA order linker · EX example · ADD addition · CON contrast
#                                                  · RES result · CONC conclusion/overall · FOL "This was followed by" · PLAIN detail
import json, os, re

H = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(H, 'w10')
J = lambda f: json.load(open(os.path.join(SRC, f), encoding='utf-8'))

def sents(p): return [s for s in re.split(r'(?<=[.!?])\s+', p.strip()) if s]

# ------------------------------------------------------------------------------------------------ charts
WORKED = dict(id='W1', title='Favourite Book Genres of Grade 10 Students in Oman', ylabel='Number of students', unit='',
    categories=['Adventure', 'Fantasy', 'Horror', 'Poetry', 'Science fiction'],
    series=[dict(name='Boys', values=[35, 30, 25, 10, 5]), dict(name='Girls', values=[30, 15, 20, 5, 25])],
    model=("The bar chart illustrates the favourite book genres of Grade 10 boys and girls in Oman. Overall, adventure was the most popular book genre for both boys and girls.\n"
           "Firstly, the most popular book genre for boys was adventure, with 35 students. This was followed by fantasy (30), horror (25) and poetry (10). However, the least popular book genre for boys was science fiction, with only 5 students.\n"
           "Similarly, the most popular book genre for girls was adventure, with 30 students. This was followed by science fiction (25), horror (20) and fantasy (15). However, the least popular book genre for girls was poetry, with only 5 students.\n"
           "To summarize, both boys and girls liked adventure. However, the biggest difference was in science fiction, where 5 boys chose it, whereas 25 girls did."))

def load_charts():
    """-> list of chart dicts (id, title, ylabel, unit, categories, series, model, src, clues?)"""
    out = [dict(WORKED, src='Worked example (Mr Mohamed\'s handout)')]
    pd = J('partd.json')
    for c in pd['charts']:
        out.append(dict(id='P%02d' % c['n'], title=c['title'], ylabel=c.get('ylabel', ''), unit=c.get('unit', ''), categories=c['categories'], series=c['series'],
                        model=c['model'], clues=c.get('clues'), src='Chart practice %02d' % c['n']))
    for c in J('past_chart.json'):
        m = re.search(r'(Sem I{1,2}) (1st|2nd) Session (\d{4}-\d{4})(?: \((\w)\))?', c['session'])
        lab = f"Past exam {m.group(3)} · {m.group(1)} · {m.group(2)} session" + (f' ({m.group(4)})' if m.group(4) else '') if m else c['session']
        out.append(dict(id=c['id'], title=c['title'], ylabel=c.get('ylabel', ''), unit=c.get('unit', ''), categories=c['categories'], series=c['series'], model=c['model'], src=lab))
    for n in range(1, 11):
        x = J('exam%02d.json' % n)['chart']
        out.append(dict(id='X%02d' % n, title=x['title'], ylabel=x.get('ylabel', ''), unit=x.get('unit', ''), categories=x['categories'], series=x['series'], model=x['model'], src='Model exam %d' % n))
    for c in out: c['model'] = c['model'].replace('\n\n', '\n')
    return out

CHART_LK = {'Overall,': ('CONC', 'Overall'), 'Firstly,': ('PARA', 'Highest'), 'In contrast,': ('PARA', 'Highest'), 'Similarly,': ('PARA', 'Highest'),
            'However,': ('CON', 'Lowest'), 'To summarize,': ('CONC', 'Both liked')}
def parse_chart(c):
    """model text -> paragraphs [{name, ar, s:[[lk, tx, role, slot]]}]"""
    ps = [p for p in c['model'].split('\n') if p.strip()]
    two = len(c['series']) == 2
    names = ['Introduction'] + ([c['series'][0]['name'], c['series'][1]['name']] if two and len(ps) == 4 else [f'Body {i}' for i in range(1, len(ps) - 1)]) + ['Conclusion']
    ars = ['المقدمة'] + (['المجموعة الأولى', 'المجموعة الثانية'] if two and len(ps) == 4 else ['فقرة ' + str(i) for i in range(1, len(ps) - 1)]) + ['الخاتمة']
    out = []
    for pi, p in enumerate(ps):
        S = []
        for s in sents(p):
            m = re.match(r'(Overall,|Firstly,|In contrast,|Similarly,|However,|To summarize,)\s+(.*)', s)
            if s.startswith(('The bar chart', 'The pie chart')): S.append(['', s, 'FIX', 'What the chart shows'])
            elif s.startswith('This was followed by'): S.append(['', s, 'FOL', 'Followed by'])
            elif m:
                role, slot = CHART_LK[m.group(1)]
                if m.group(1) == 'However,' and re.search(r'biggest|difference', s): slot = 'Biggest difference'
                elif m.group(1) == 'However,' and pi == len(ps) - 1: slot = 'Biggest difference'
                elif m.group(1) in ('Similarly,', 'In contrast,', 'Firstly,') and 0 < pi < len(ps) - 1 and any(x[3] == 'Highest' for x in S): slot = 'More detail'
                S.append([m.group(1), m.group(2), role, slot])
            else: S.append(['', s, 'PLAIN', 'Detail'])
        out.append(dict(name=names[pi], ar=ars[pi], s=S))
    return out

# ------------------------------------------------------------------------------------------------ e-mails
ROLE = {'For example,': 'EX', 'For instance,': 'EX', 'However,': 'CON', 'Therefore,': 'RES', 'Moreover,': 'ADD', 'In addition,': 'ADD', 'Furthermore,': 'ADD'}
SLOT = {'EX': 'Example', 'CON': 'Contrast', 'RES': 'Result', 'ADD': 'Addition'}

def fix_model(m):
    m = m.strip()
    m = re.sub(r'\s+ls$', '', m)   # stray characters in the source of one practice model
    if '\n\n' in m and not re.search(r'\n(Best wishes|Yours \w+),\s*\n\w', m):
        pass
    m = re.sub(r'(That\'s all[^\n]*?soon\.|Please let me know[^\n]*?\.)\s+((?:Best wishes|Yours \w+),)\s+(\w+)$', r'\1\n\n\2\n\3', m)
    return m

def parse_email(e, formal):
    ps = [p.strip() for p in fix_model(e['model']).split('\n\n') if p.strip()]
    dear, intro, *body, closing, sign = ps
    i1 = sents(intro)
    pur = next(i for i, s in enumerate(i1) if s.startswith('I am writing'))
    greet = ' '.join(i1[:pur]); purpose = ' '.join(i1[pur:])
    out = [dict(name='Opening', ar='البداية الثابتة', s=[['', dear, 'FIX', 'Dear + ' + ('Mr / Ms + name' if formal else 'name')],
                                                      ['', greet, 'FIX', 'Fixed greeting'], ['', purpose, 'FIX', 'Purpose']])]
    for i, b in enumerate(body):
        S = []
        for k, s in enumerate(sents(b)):
            m = re.match(r'(First,|Second,|Third,|For example,|For instance,|However,|Therefore,|Moreover,|In addition,|Furthermore,)\s+(.*)', s)
            if m and m.group(1) in ('First,', 'Second,', 'Third,'): S.append([m.group(1), m.group(2), 'PARA', 'Idea ' + '①②③'[i]])
            elif m: S.append([m.group(1), m.group(2), ROLE[m.group(1)], SLOT[ROLE[m.group(1)]]])
            else: S.append(['', s, 'PLAIN', 'Detail'])
        out.append(dict(name=f'Body {i + 1}', ar=['الفقرة الأولى', 'الفقرة الثانية', 'الفقرة الثالثة'][i], s=S))
    out.append(dict(name='Closing', ar='الخاتمة الثابتة', s=[['', closing, 'FIX', 'Fixed closing'], ['', ' '.join(sign.split('\n')), 'FIX', 'Sign-off + name']]))
    return out

def email_prompt(sit, task, bullets):
    b = '; '.join(f'({i + 1}) {x.rstrip(".")}' for i, x in enumerate(bullets))
    return ((sit.strip() + ' ') if sit else '') + task.strip() + ' ' + b + '.'

def short_title(text):
    t = re.split(r'(?<=[.!?])\s', text.strip())[0].rstrip('.')
    t = re.sub(r'^Imagine you are [A-Za-z/]+(, [^.]*?)?\.\s*', '', t)
    return t if len(t) <= 95 else t[:92] + '…'

def load_emails():
    """-> list of dicts(id, formal, prompt, label, src, model, words)"""
    out = []
    pd = J('partd.json')
    for e in pd['emails']:
        out.append(dict(id='P%02d' % e['n'], formal=e['formal'], prompt=email_prompt('', e['task'], e['bullets']), label=short_title(e['task']),
                        src='E-mail practice %02d' % e['n'], model=e['model']))
    for e in J('past_email.json'):
        m = re.search(r'(1st|2nd) Session (\d{4}-\d{4})', e['session'])
        src = f'Past exam {m.group(2)} · {m.group(1)} session' if m else 'Past exam paper'
        out.append(dict(id=e['id'], formal=e['formal'], prompt=email_prompt(e.get('situation', ''), e['task'], e['bullets']),
                        label=short_title(e.get('situation') or e['task']), src=src, model=e['model']))
    for n in range(1, 11):
        e = J('exam%02d.json' % n)['email']
        out.append(dict(id='X%02d' % n, formal=e['formal'], prompt=email_prompt(e.get('situation', ''), e['task'], e['bullets']),
                        label=short_title(e.get('situation') or e['task']), src='Model exam %d' % n, model=e['model']))
    return out

# ------------------------------------------------------------------------------------------------ extra topics (the export also adds every past-exam question)
TOPICS = {
 'IE': ['Imagine you are Ali. Your cousin Rashid is going to start Grade 10 next week. Write an email to Rashid. In your email, write about: (1) how he can make new friends at school; (2) how he can do well in his lessons.',
        'Imagine you are Hamad. Your friend Majid lives in another country and wants to know about Oman. Write an email to Majid. In your email, write about: (1) a traditional Omani food you like; (2) a place in Oman he should visit.',
        'Imagine you are Salma. Your friend Noor cannot stop using her phone. Write an email to Noor. In your email, write about: (1) why too much phone use is a problem; (2) what she can do instead.',
        'Imagine you are Yousef. Your school has a recycling competition. Write an email to your friend Sultan. In your email, write about: (1) what the competition is; (2) why he should join your team.',
        'Imagine you are Aisha. You saw a very interesting documentary about renewable energy. Write an email to your friend Huda. In your email, write about: (1) what the documentary was about; (2) what you learnt from it.',
        'Imagine you are Khalid. Your grandfather took you to an old fort last weekend. Write an email to your friend Tom. In your email, write about: (1) what you saw there; (2) why you enjoyed the visit.'],
 'FE': ['Imagine you are Salim/Salma. Write a formal email to your principal, Mr Hamad, asking him to organise a Climate Change Day. In your email, write about: (1) why the day is important; (2) what activities students can do.',
        'Imagine you are Salim/Salma. Write a formal email to your teacher, Ms Fatma, asking for her advice about using social media safely. In your email, write about: (1) the dangers of social media; (2) how students can stay safe online.',
        'Imagine you are Salim/Salma. Write a formal email to the manager of a local company asking him to give a talk at your school about renewable energy. In your email, write about: (1) why the talk will be useful; (2) when and where it can be held.',
        'Imagine you are Salim/Salma. Write a formal email to your principal, Mr Nasser, suggesting a school trip to a historical place. In your email, write about: (1) why students will enjoy the trip; (2) what they can learn there.',
        'Imagine you are Salim/Salma. Write a formal email to your teacher, Mr Hilal, asking him to help students start a school website. In your email, write about: (1) why a website is useful; (2) what students can put on it.'],
}

# ------------------------------------------------------------------------------------------------ Stage 6 samples — [[wrong=>right|type]] marks a mistake, {{text|why}} marks a strength
SAMPLE_CHART = 'P01'   # Favourite School Subjects of Grade 10 Students in 2024
SAMPLES = {
 'CH': dict(topic='Favourite School Subjects of Grade 10 Students in 2024', chart=SAMPLE_CHART,
   weak=["The bar chart [[show=>illustrates|vocabulary]] [[subjects=>the favourite school subjects of Grade 10 boys and girls in 2024|incomplete]]. [[I think boys like=>Overall, boys preferred|opinion]] maths [[and=>, whereas|linker]] girls [[like=>preferred|vocabulary]] [[sciense=>science|spelling]].",
         "[[boys maths=>Firstly, the most popular subject for boys was maths, with|missing template]] 40 students. [[English 30.=>This was followed by English (30), science (25) and Arabic (15).|missing items]] [[art 15.=>However, the least popular subject for boys was art, with only 5 students.|wrong number]]",
         "[[girls=>In contrast, the most popular subject for girls was|missing template]] science, 40 students. [[English 35.=>This was followed by English (35), Arabic (25) and maths (20).|missing items]] [[art 5.=>However, the least popular subject for girls was art, with only 15 students.|wrong number]]",
         "[[I like maths too.=>To summarize, both boys and girls liked English. However, the biggest difference was in maths, where 40 boys chose it, whereas 20 girls did.|opinion]]"],
   avg=["The bar chart illustrates the favourite school subjects of Grade 10 boys and girls in 2024. Overall, boys preferred maths, whereas girls preferred science.",
        "Firstly, the most popular subject for boys was maths, with 40 students. This was followed by English (30), science (25) and Arabic (15). However, the least popular subject for boys was art, with only [[15=>5|wrong number]] students.",
        "In contrast, the most popular subject for girls was science, with 40 students. This was followed by English (35), Arabic (25) and maths (20). However, the least popular subject for girls [[were=>was|grammar]] art, with only 15 students.",
        "To summarize, both boys and girls liked English. However, the biggest difference was in maths, where 40 boys chose it, whereas 20 girls did."],
   exc=["{{The bar chart illustrates the favourite school subjects of Grade 10 boys and girls in 2024.|fixed opening}} {{Overall, boys preferred maths, whereas girls preferred science.|clear overall comparison}}",
        "{{Firstly, the most popular subject for boys was maths, with 40 students.|highest first}} This was followed by English (30), science (25) and Arabic (15). However, the least popular subject for boys was art, with only 5 students.",
        "In contrast, the most popular subject for girls was science, with 40 students. This was followed by English (35), Arabic (25) and maths (20). {{However, the least popular subject for girls was art, with only 15 students.|every number correct}}",
        "{{To summarize, both boys and girls liked English.|clue 5: both liked}} However, {{the biggest difference was in maths, where 40 boys chose it, whereas 20 girls did.|clue 6: biggest difference}}"]),
 'IE': dict(topic='Imagine you are Ali. Your cousin Rashid is going to start Grade 10 next week. Write an email to Rashid. In your email, write about: (1) how he can make new friends at school; (2) how he can do well in his lessons.',
   weak=["[[dear=>Dear|capital]] Rashid, how are you.",
         "You must [[make=>make new|vocabulary]] friends. [[talk=>Talk to your classmates.|punctuation]] Study [[hard=>hard too.|task]]",
         "[[Bye=>That's all I have for now. Please write and tell me your news. I am looking forward to hearing from you soon. Best wishes,|fixed closing]] Ali"],
   avg=["Dear Rashid, Hello, how are you and your family? I hope you are very well. I am very happy to write to you. I am writing this email to give you some advice about Grade 10.",
        "First, you should talk to your classmates. For example, you can ask them to play football at break. [[Moreover you=>Moreover, you|punctuation]] can join a school club.",
        "Second, you should listen to your teachers. [[Therefore you=>Therefore, you|punctuation]] will understand the lessons better.",
        "That's all I have for now. Please write and tell me your news. I am looking forward to [[hear=>hearing|grammar]] from you soon. Best wishes, Ali"],
   exc=["{{Dear Rashid, Hello, how are you and your family? I hope you are very well. I am very happy to write to you.|fixed opening}} I am writing this email to give you some advice about your first week in Grade 10.",
        "First, you should be friendly with your classmates. For example, you can sit with a new person at break and ask him about his hobbies. {{However, do not be shy if someone is quiet.|critical thinking}} Moreover, joining the football team is a great way to meet people.",
        "Second, you should work hard in your lessons. For example, you can write a study timetable and review your notes every evening. Therefore, you will feel confident before the exams.",
        "{{That's all I have for now. Please write and tell me your news. I am looking forward to hearing from you soon.|fixed closing}} Best wishes, Ali"]),
 'FE': dict(topic='Imagine you are Salim. Write a formal email to your principal, Mr Hamad, asking him to organise a Climate Change Day. In your email, write about: (1) why the day is important; (2) what activities students can do.',
   weak=["[[Hi principal=>Dear Mr Hamad,|fixed opening]]",
         "[[I want=>I am writing this email to ask you to organise|formal]] a day. [[Its=>It is|grammar]] important. Students [[can do=>can plant trees and make posters.|task]]",
         "[[Bye=>Yours sincerely,|fixed closing]] Salim"],
   avg=["Dear Mr Hamad, I hope this email finds you in good health and high spirits. I am writing this email to ask you to organise a Climate Change Day at our school.",
        "First, the day is important because students will learn about climate change. For example, they will see how pollution harms [[our=>the|vocabulary]] planet. [[Moreover=>Moreover,|punctuation]] they will understand how to save energy.",
        "Second, students can do many activities. Therefore, they can plant trees and [[makes=>make|grammar]] posters.",
        "Thank you for your time and attention. I look forward to your response. Please let me know if you need any further information. Yours sincerely, Salim"],
   exc=["{{Dear Mr Hamad, I hope this email finds you in good health and high spirits.|fixed opening}} I am writing this email to ask you to organise a Climate Change Day at our school.",
        "First, the day is important because it teaches students how to protect the environment. For example, they will learn how burning fuel causes global warming. {{However, many students do not know the causes of climate change yet.|critical thinking}} Moreover, they will discover simple ways to save energy at home.",
        "Second, students can take part in many useful activities. For example, they can plant trees in the school garden and make posters about recycling. Therefore, the whole school will become greener.",
        "{{Thank you for your time and attention. I look forward to your response. Please let me know if you need any further information.|fixed closing}} Yours sincerely, Salim"]),
}
