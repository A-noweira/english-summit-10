# English Summit 10 — notes for Claude

Owner: Mohamed Imam (Senior Teacher of English, Oman). Replies in Arabic. In Arabic school documents write «وزارة التعليم» only.
Grade 10 platform (Semester 1, 2026-27), ported from English Summit 11 (same architecture, accounts and teacher tools — see that repo's CLAUDE.md for the accounts/one-device/teacher-page details; they are unchanged). Palette: sage olive (vocabulary, brand) + warm sand / golden honey (grammar).

## Layout
- Cloudflare **Worker** `english-summit-10` (`wrangler.jsonc`): static `site/` + `src/worker.js` (`/api/*`, SQLite Durable Object `Board`, free Workers AI binding `AI`). Push to `main` → Workers Builds deploys. Live: https://english-summit-10.a-noweira.workers.dev/ · teacher `/#TEACHER`.
- `site/index.html` is generated: edit `build/hub_src.html` + data, then `npm run build` (= `python3 build/export.py && python3 build/make_hub.py`). `site/audio/examNN_part{1,2}.mp3` = the 20 model-exam recordings (QR codes in the printed book point to them).
- Exporters (`build/`): `export.py` (master) → `export_themes.py`, `export_exams.py`, `export_writing.py`; data in `build/data/` (`w10/` writing JSON, `writing_lab.py`). The Grade-10 source content (units, past exams, model exams) is authored in `/home/claude/es10/data` (book project) and is read by the exporters from there — copy it into `build/data/` if that path is missing.
- Teacher password: only `TEACHER_HASH = sha256("ES10-TEACHER:" + password)` is in `src/worker.js`. Never commit passwords or student lists.

## Platform
- Themes = 4 units (1 New Media, 2 Climate Change, 3 Renewable Energy, 4 Civilisation): vocabulary lessons `T{n}-V{k}` (53, with ★ words, games, 18 MCQ, 2 text gaps), spelling bee `SB-n`, grammar `T{n}-G{k}` (12), theme test `TT-n`; Grammar Booster `#GB` (GB-1..10), irregular verbs `#F-03`, phrasal verbs `#F-04`.
- Exam spec (60 marks): L1 7 MCQ | L2 4 short + 4 T/F (items 8–15) | grammar dialogue 5×2 (16–20) | vocabulary text 5×4 (21–25) | R1 6 MCQ + 4 completion (26–35) | R2 6 short + 4 T/F (36–45) | Writing 1 bar chart ≥100 words /5 | Writing 2 e-mail ≥100 words /10.
- Exam Practice: past papers (EX-L01..09 questions only, no recordings; EX-R01..09; GV-01..17), Exams `MT-01..10` with real mp3.
- Writing Lab types: CH (chart, 4-paragraph template), IE informal e-mail, FE formal e-mail; 9 stages. AI marking uses the Ministry rating scales (Outcome #4 e-mails, #5 informative text): level 1–5 → chart shown /5, e-mail 10/8/6/4/2; chart submissions carry the chart data so the AI checks numbers. Feedback released 30 min after sending; 6 texts/day; 60–450 words.
- localStorage keys keep the `es11…` prefixes (sync regex depends on them; separate origin so no clash).

## Updates (Oct 2026)
- "Themes" renamed **Units** in the UI (route `#UNITS`, `#THEMES` redirects; internal ids `TH-n`, `TT-n` unchanged). `TT-n` is now titled "Unit n practice" (28 items). Each unit path ends with full 60-mark exams (`D.unitExams` in build/export.py → model exams MT-xx).
- Past listening (EX-L01..09): opens the original files.fm links decoded from the booklet QR codes (`build/data/g10/past_links.json`, l1 = items 1–7, l2 = items 8–15).
- Chart intro: sentence 1 "The bar chart shows …", sentence 2 names the categories under the bars ("Book genres were horror, …"), then "Overall, …".

## Updates (Nov 2026)
- New content: **Model Exams MT-11..25** (build/data/g10/models/exam11..25.json, same shape as exam01) and **60 "2026/2027 mock tasks"**: `MK-L01..15` listening (L1 7 + L2 8, recordings inside the page), `MK-G01..15` grammar + vocabulary, `MK-R01..15` reading, `MK-W01..15` writing (chart /5 + e-mail /10, AI marking). Files in `build/data/g10/mock/{L,G,R,W}NN.json`; the exporter (`export_exams.py`) turns them into exams of kind `mock` (parts L/G/R/W) shown first on each `#PR-x` page. `build/validate_new.py FILE…` checks counts, answer indexes, numbers-as-words in scripts, word counts, chart numbers in the model answer.
- Listening is embedded: `site/audio/exam11..25_part{1,2}.mp3` and `site/audio/mockL01..15_part{1,2}.mp3`, recorded by `python3 build/tools/audio_new.py [keys]` (Kokoro neural voices, two different people per conversation, each voice calibrated to ~145 words/min and cached in `build/tools/voice_speed.json`, examiner intro, 10 s reading time, each recording played twice). TTS model files are expected in `$TTS_DIR` (kokoro.onnx + voices.bin). These are synthetic voices, not human recordings.
- Exam drafts are stored under localStorage keys `es11x-<ref>` (synced by SYNCK).
