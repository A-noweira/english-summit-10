#!/usr/bin/env python3
"""Record the listening parts of the new exams (MT-11..25) and mock tasks (MK-L01..15) with natural neural voices.
usage: python3 build/tools/audio_new.py [--wpm 150] KEY ...   KEY = exam11 | mockL01 ...   (no key = everything found)
Each part: examiner intro -> time to read -> 'Now listen' -> recording -> 'Now listen again' -> recording -> end.
Different people (voice pairs rotate per file), medium speed (~145-155 words/min), levelled loudness, 48 kbps mono mp3 -> site/audio/<key>_part{1,2}.mp3"""
import json, sys, os, glob, subprocess, re, random
import numpy as np
from kokoro_onnx import Kokoro
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H, '..', '..'))
TTS = os.environ.get('TTS_DIR', '/tmp/claude-0/-home-claude/85a6e14a-c668-511a-a384-40b4f46ec0a1/scratchpad/tts')
OUT = os.path.join(ROOT, 'site', 'audio'); os.makedirs(OUT, exist_ok=True)
SR = 24000
F = ['af_heart', 'af_bella', 'bf_emma', 'af_sarah', 'bf_isabella', 'af_aoede', 'af_kore', 'af_jessica']
M = ['am_michael', 'bm_george', 'am_fenrir', 'bm_fable', 'am_adam', 'am_puck']
NARR = 'af_nova'
SPEED = 0.84
SPD_FILE = os.path.join(H, 'voice_speed.json')
def load_spd():
    try: return json.load(open(SPD_FILE))
    except Exception: return {}
def save_spd(v, spd):
    d = load_spd(); d[v] = round(spd, 3); json.dump(d, open(SPD_FILE, 'w'), indent=1)
k = Kokoro(os.path.join(TTS, 'kokoro.onnx'), os.path.join(TTS, 'voices.bin'))
sil = lambda s: np.zeros(int(SR * s), dtype=np.float32)
def lvl(a, target=0.10):
    r = float(np.sqrt(np.mean(a ** 2)) or 1); a = a * (target / r); return np.clip(a, -0.97, 0.97).astype(np.float32)
def say(text, voice, speed):
    text = re.sub(r'\s+', ' ', text).strip()
    a, sr = k.create(text, voice=voice, speed=speed, lang='en-gb' if voice[0] == 'b' else 'en-us'); assert sr == SR
    a = a.astype(np.float32); nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(0, nz[0] - 800): nz[-1] + 1600]            # trim silence around the line
    return lvl(a)
def mp3(a, path):
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', 'highpass=f=70,loudnorm=I=-18:TP=-2:LRA=7', '-ar', '24000', '-b:a', '48k', path], input=pcm, check=True)
def part(key, idx, p, ctx, sc, title):
    rnd = random.Random(f'{key}-{p}'); fv = F[(idx * 2 + p) % len(F)]; mv = M[(idx * 3 + p) % len(M)]
    seen = {}; fi = [fv, F[(idx * 2 + p + 3) % len(F)]]; mi = [mv, M[(idx * 3 + p + 2) % len(M)]]
    segs = []; sp = sorted({s['speaker'] for s in sc}); words = 0
    for s in sc:
        if s['speaker'] not in seen: seen[s['speaker']] = (fi if s['gender'] == 'f' else mi).pop(0)
    WPM = 148.0
    for who in seen:                    # voices differ in pace: record each speaker, measure real words/min, re-record once if off target
        idx_ = [i for i, s in enumerate(sc) if s['speaker'] == who]; known = load_spd().get(seen[who]); spd = known or SPEED
        for rnd_ in range(2):
            au = {i: say(sc[i]['text'], seen[who], spd) for i in idx_}
            w = sum(len(sc[i]['text'].split()) for i in idx_); d = sum(len(au[i]) for i in idx_) / SR
            wpm = w / d * 60; print(f'    {who} {seen[who]} {wpm:.0f}wpm @ {spd:.2f}', flush=True)
            if known or abs(wpm - WPM) <= 8 or rnd_:
                if not known: save_spd(seen[who], spd)
                break
            spd = max(0.62, min(1.1, spd * WPM / wpm))
        for i in idx_: segs.append((i, au[i]))
        words += w
    segs = [a for i, a in sorted(segs, key=lambda t: t[0])]
    if len(sp) == 1:    # a talk: short natural pauses between paragraphs
        body = np.concatenate([np.concatenate([a, sil(0.9)]) for a in segs])
    else:               # a conversation: turn-taking pauses vary a little
        body = np.concatenate([np.concatenate([a, sil(rnd.uniform(0.55, 0.85))]) for a in segs])
    nar = lambda t: say(t, NARR, 0.92)
    out = np.concatenate([nar(f'Listening, part {p}. {ctx} You will hear the recording twice. You now have time to read the questions.'), sil(10),
        nar('Now listen.'), sil(1.2), body, sil(2.5), nar('Now listen again.'), sil(1.2), body, sil(2.5),
        nar(f'This is the end of listening, part {p}. You now have time to check your answers.'), sil(5)])
    path = os.path.join(OUT, f'{key}_part{p}.mp3'); mp3(out, path)
    print(key, p, 'voices', sorted(set(seen.values())), f'{len(out)/SR:.0f}s', f'{words/(sum(len(s)for s in segs)/SR)*60:.0f}wpm(spoken)', f'{os.path.getsize(path)/1e6:.2f}MB', flush=True)
def jobs():
    D = os.path.join(ROOT, 'build', 'data', 'g10'); J = []
    for n in range(11, 26):
        f = f'{D}/models/exam{n:02d}.json'
        if os.path.exists(f): J.append((f'exam{n:02d}', n, f))
    for n in range(1, 16):
        f = f'{D}/mock/L{n:02d}.json'
        if os.path.exists(f): J.append((f'mockL{n:02d}', 100 + n, f))
    return J
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--wpm']: SPEED = float(a[1]); a = a[2:]
    for key, idx, f in jobs():
        if a and key not in a: continue
        if all(os.path.exists(os.path.join(OUT, f'{key}_part{p}.mp3')) for p in (1, 2)) and not os.environ.get('FORCE'): continue
        x = json.load(open(f, encoding='utf-8'))
        part(key, idx, 1, x['listening1']['context'], x['listening1']['script'], x.get('title', key))
        part(key, idx, 2, x['listening2']['context'], x['listening2']['script'], x.get('title', key))
