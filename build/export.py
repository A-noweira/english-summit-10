"""Master exporter -> build/hub_data.json (Grade 10 content). Modules (each exposes build(D)):
export_themes.py (vocab/grammar/bee/theme tests/irregular), export_exams.py (past papers + model exams), export_writing.py (writing lab data).
Grade 10 source data: /home/claude/es10/data (units/, past/, models/, booster.json, partd.json).  Reference Grade 11 exporter: export11_reference.py"""
import json, os, sys, importlib
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
TN = {1: 'New Media', 2: 'Climate Change', 3: 'Renewable Energy', 4: 'Civilisation'}
D = {'vocab': [], 'grammar': [], 'found': [], 'listen': [], 'pages': {}, 'themeKeys': [], 'tn': TN, 'exams': []}
for m in ('export_themes', 'export_exams', 'export_writing'):
    if os.path.exists(os.path.join(H, m + '.py')):
        importlib.import_module(m).build(D); print('ok', m)
json.dump(D, open(os.path.join(H, 'hub_data.json'), 'w'), ensure_ascii=False)
print('hub_data.json', os.path.getsize(os.path.join(H, 'hub_data.json')) // 1024, 'KB')
