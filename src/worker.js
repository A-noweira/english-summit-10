// English Summit 10 — platform API (Cloudflare Worker + one SQLite-backed Durable Object).
// Static pages come from ./site (assets). Only /api/* runs this code.
//
//   Accounts (the teacher creates them; one student = one account = one device):
//     POST /api/auth/login  {user, pw, device, ua}  -> {token, user, name, must_change} | {error:'device'} (a new-device request is sent to the teacher)
//     POST /api/auth/change {pw}         (header X-Session)  -> the student replaces the temporary password
//     POST /api/auth/logout              (header X-Session)  -> ends the session (the record stays)
//   Students (header X-Session: token from login):
//     POST /api/hello · GET /api/inbox · POST /api/done · POST /api/log · POST /api/beat · POST /api/state · GET /api/me
//     POST /api/write/submit {type: CH|IE|FE, topic, text, chart (CH only: {title, ylabel, unit, categories, series:[{name, values}]})} · GET /api/write/list
//   Teacher (header X-Teacher-Key: password; only its SHA-256 is stored here):
//     GET /api/t/accounts · POST /api/t/accounts/add|reset|status|unbind|delete · POST /api/t/device {id, approve}
//     GET /api/t/state · /api/t/students · /api/t/student?code= · /api/t/class · POST /api/t/notice|delete|live|live/delete|retry

import { DurableObject } from "cloudflare:workers";

const TEACHER_HASH = "a7c878aab84e809241ea86f62aae56a80e45a47fca9f40940c4708a7dcedb8ca";
const READY_MS = 30 * 60 * 1000;   // feedback is shown 30 minutes after sending
const PW_ALPH = "abcdefghjkmnpqrstuvwxyz23456789";
const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
async function sha256hex(t) { return hex(await crypto.subtle.digest("SHA-256", enc.encode(t))); }
async function pbkdf2(pw, salt) {
  const k = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
  return hex(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode(salt), iterations: 100000 }, k, 256));
}
const rnd = (n, alph) => { const b = crypto.getRandomValues(new Uint8Array(n)); return [...b].map(x => alph[x % alph.length]).join(""); };
const tempPassword = () => rnd(4, PW_ALPH) + "-" + rnd(4, PW_ALPH);
const newToken = () => hex(crypto.getRandomValues(new Uint8Array(24)));
const cleanUser = u => String(u || "").trim().toLowerCase().replace(/[^a-z0-9._-]/g, "").slice(0, 32);
function pwProblem(p, user) {
  p = String(p || "");
  if (p.length < 8) return "Use at least 8 characters. استخدم 8 أحرف على الأقل.";
  if (p.length > 64) return "The password is too long.";
  if (!/[a-z]/i.test(p) || !/[0-9]/.test(p)) return "Use letters and numbers together. استخدم حروفًا وأرقامًا معًا.";
  if (user && p.toLowerCase().includes(user.toLowerCase())) return "Do not put your username in your password. لا تضع اسم المستخدم داخل كلمة المرور.";
  return "";
}
function userFromName(name) {
  const parts = String(name || "").toLowerCase().normalize("NFKD").replace(/[^a-z\s-]/g, " ").split(/\s+/).filter(Boolean);
  if (!parts.length) return "s11";
  return (parts[0] + (parts.length > 1 ? "." + parts[parts.length - 1].replace(/^al-?/, "").slice(0, 10) : "")).replace(/-/g, "").slice(0, 20);
}

/* ---------------- AI marking (Workers AI, free tier) ---------------- */
const RUBRIC = {
  informative: { name: "Outcome #5 — Informative texts (here: a description of a bar chart)", crit: [
    ["Relevant information", "5 presents relevant information clearly and in an interesting way · 4 reasonable success in presenting relevant information · 3 manages to present relevant information but in a somewhat limited way · 2 attempts to present information but the result is obviously inadequate · 1 very little relevant information"],
    ["Details & examples (all numbers)", "5 very good use of details and examples · 4 good use of details and examples · 3 minimal details and examples · 2 poor use of details · 1 no details"],
    ["Structure & coherence", "5 very well-structured, clear and coherent · 4 generally well-structured · 3 not well-structured but reasonably clear · 2 poorly structured, often unclear · 1 incoherent and confusing"],
    ["Grammar & vocabulary", "5 varied range of grammar and vocabulary with a very good level of accuracy · 4 fair range, good accuracy · 3 limited range, reasonable accuracy · 2 very limited range, frequent errors · 1 extremely limited range, frequent serious errors"]] },
  interactive: { name: "Outcome #4 — Letters and e-mails (interactive texts)", crit: [
    ["Message to the reader", "5 the message to the intended reader is very clear · 4 fairly clear · 3 partially clear · 2 mostly unclear · 1 unclear"],
    ["Purpose", "5 the writing clearly succeeds in achieving its intended purpose (every point of the task is answered) · 4 reasonable success · 3 the purpose is only partially achieved · 2 only very limited success · 1 clearly fails"],
    ["Organisation & coherence", "5 very well-organised, clear and coherent · 4 generally well-organised, mostly clear and coherent · 3 not well-organised but still reasonably clear and coherent · 2 poorly organised, often unclear · 1 incoherent and confusing"],
    ["Grammar & vocabulary", "5 varied range of grammar and vocabulary with a very good level of accuracy · 4 fair range, good accuracy · 3 limited range, reasonable accuracy · 2 very limited range, frequent errors · 1 extremely limited range, frequent serious errors"]] },
};
const TYPES = {
  CH: { kind: "informative", max: 5, min: 100, sys: "Writing 1 is a description of a BAR CHART with two groups (at least 100 words, best 100-150, not more than about 160). The teacher's method has 4 paragraphs: (1) INTRODUCTION: sentence 1 'The bar chart shows ...' (what the chart shows, from the title, in the student's own words, no numbers; 'illustrates' is also accepted) + sentence 2 naming the categories printed under the bars, e.g. 'Book genres were horror, adventure, fantasy, poetry and science fiction.' (all categories, as in the chart) + 'Overall, [group 1] preferred ..., whereas [group 2] preferred ...' (or the same favourite for both groups); (2) FIRST GROUP: 'Firstly, the most popular ... for [group 1] was ..., with ... This was followed by ... (...), ... (...) and ... (...). However, the least popular ... was ..., with only ...'; (3) SECOND GROUP: 'In contrast, ...' (or 'Similarly, ...' when the favourite is the same) with the same pattern; (4) CONCLUSION: 'To summarize, both ... liked ... However, the biggest difference was in ..., where ... whereas ...'. Items go from the highest to the lowest, EVERY item is written with its number, and there is no personal opinion and no new idea. The chart data is given to you below the student's text: use it to check the text." },
  IE: { kind: "interactive", max: 10, min: 100, sys: "Writing 2 is an INFORMAL E-MAIL to a friend or relative (at least 100 words, best 100-130). The course method: 'Dear + first name,' + fixed greeting ('Hello, how are you and your family? I hope you are very well. I am very happy to write to you.') + 'I am writing this email to + purpose'. Body paragraphs: 'First,' (point 1 of the task) and 'Second,' (point 2; with three points put points 2 and 3 after 'Second,') are required; in each body paragraph the student adds two linkers that fit from For example, / However, / Therefore, / Moreover, (also accept For instance, / In addition, / Furthermore,) followed by a detail. The linkers must make sense; do not punish a different but correct linker. Fixed closing ('That's all I have for now. Please write and tell me your news. I am looking forward to hearing from you soon.') + 'Best wishes, + name'. Every point in the task must be answered." },
  FE: { kind: "interactive", max: 10, min: 100, sys: "Writing 2 is a FORMAL E-MAIL to a principal, teacher, manager, company or official (at least 100 words, best 100-130). The course method: 'Dear Mr / Ms + family name,' (or 'Dear Sir / Madam,') + 'I hope this email finds you in good health and high spirits.' + 'I am writing this email to + purpose' (ask / give / tell / inform / recommend ...). Body paragraphs: 'First,' (point 1 of the task) and 'Second,' (point 2) are required; in each body paragraph the student adds two linkers that fit from For example, / However, / Therefore, / Moreover, (also accept For instance, / In addition, / Furthermore,) followed by a detail. The linkers must make sense; do not punish a different but correct linker. Fixed closing ('Thank you for your time and attention. I look forward to your response. Please let me know if you need any further information.') + 'Yours sincerely,' (name known) or 'Yours faithfully,' (Dear Sir / Madam) + name. Formal register: no short forms (I am, do not), polite requests. Every point in the task must be answered." },
};
const MODELS = ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"];
/* the chart that was described: a plain-text table plus the facts needed to check the student's numbers */
function chartFacts(c) {
  if (!c) return "";
  const u = c.unit === "%" ? "%" : "", ser = c.series, cats = c.categories;
  const sorted = s => cats.map((x, i) => [x, s.values[i]]).sort((a, b) => b[1] - a[1]).map(p => `${p[0]} ${p[1]}${u}`).join(", ");
  let t = `\n\nCHART DATA (this is the chart the student had to describe)\nTitle: ${c.title}${c.ylabel ? " · " + c.ylabel : ""}${c.unit ? " · unit: " + c.unit : ""}\nItems: ${cats.join(" | ")}\n` +
    ser.map(s => `${s.name}: ` + cats.map((x, i) => `${x} = ${s.values[i]}${u}`).join("; ")).join("\n") + "\n" +
    ser.map(s => `${s.name} from highest to lowest: ${sorted(s)}`).join("\n");
  if (ser.length === 2) {
    const [a, b] = ser, idx = cats.map((x, i) => i);
    const best = (f, cmp) => { const m = cmp(...idx.map(f)); return idx.filter(i => f(i) === m).map(i => cats[i]).join(" / "); };
    t += `\nHighest for ${a.name}: ${best(i => a.values[i], Math.max)} · lowest for ${a.name}: ${best(i => a.values[i], Math.min)}\nHighest for ${b.name}: ${best(i => b.values[i], Math.max)} · lowest for ${b.name}: ${best(i => b.values[i], Math.min)}\n` +
      `Item both groups liked (both bars high): ${best(i => Math.min(a.values[i], b.values[i]), Math.max)}\nBiggest difference between the groups: ${best(i => Math.abs(a.values[i] - b.values[i]), Math.max)} (${idx.filter(i => Math.abs(a.values[i] - b.values[i]) === Math.max(...idx.map(j => Math.abs(a.values[j] - b.values[j])))).map(i => `${a.values[i]}${u} vs ${b.values[i]}${u}`).join(" / ")})`;
  }
  return t;
}
function cleanChart(c) {
  if (!c || typeof c !== "object") return null;
  const cats = (Array.isArray(c.categories) ? c.categories : []).slice(0, 10).map(x => clip(x, 60));
  const series = (Array.isArray(c.series) ? c.series : []).slice(0, 4).map(s => ({ name: clip(s && s.name, 40), values: (Array.isArray(s && s.values) ? s.values : []).slice(0, cats.length).map(Number) }));
  if (cats.length < 2 || !series.length || series.some(s => s.values.length !== cats.length || s.values.some(v => !isFinite(v) || v < 0 || v > 1e6))) return null;
  return { title: clip(c.title, 160), ylabel: clip(c.ylabel, 80), unit: clip(c.unit, 8), categories: cats, series };
}
function gradePrompt(sub) {
  const T = TYPES[sub.type] || TYPES.CH, R = RUBRIC[T.kind], chart = sub.type === "CH" ? (typeof sub.chart === "string" ? JSON.parse(sub.chart) : sub.chart) : null;
  const chk = chart ? " CHART CHECK: compare EVERY item and EVERY number in the student's text with the CHART DATA. A wrong number, a wrong highest / lowest / both-liked / biggest-difference item, a wrong order, a missing item or an invented item is a DATA mistake: list each one in 'mistakes' with type 'data' (wrong = the student's exact words, correct = the right words) and lower criterion 2 (one wrong or missing number: at most band 4; two or three: at most 3; more than three: at most 2). If the overall comparison or the highest / lowest items are wrong, lower criterion 1 as well. Never accept a number that the chart does not contain. In 'task' say whether all numbers and items are reported correctly." : "";
  return [
    { role: "system", content: "You are an experienced, kind and precise examiner of Grade 10 English writing in Oman (Semester One, 2026-2027). " + T.sys +
      `\nMark with the Ministry rating scale — ${R.name}. Give each criterion a band from 1 to 5 using exactly these descriptors:\n` + R.crit.map((c, i) => `${i + 1}. ${c[0]}: ${c[1]}`).join("\n") +
      `\nThe overall level (1-5) is the average of the four bands, rounded. If the text is off-topic, lower the first two criteria. If it is shorter than ${T.min} words, no criterion may be above 3. Judge as a fair Grade 10 EFL examiner (level A2-B1), not a native-speaker editor: simple correct language can still earn 4.` + chk +
      "\nAnswer ONLY with JSON: {\"criteria\": [{\"name\": \"criterion name\", \"band\": 1-5, \"comment\": \"one short sentence\"}], \"level\": 1-5, \"summary\": \"2-3 sentences in simple English\", \"summary_ar\": \"the same in Arabic\", \"task\": \"does it answer every part of the question?\", \"organisation\": \"comment on the structure, fixed phrases and linkers\", \"strengths\": [\"...\"], \"mistakes\": [{\"wrong\": \"exact words from the text\", \"correct\": \"corrected words\", \"type\": \"grammar|spelling|punctuation|vocabulary|capital|word order|register|data\", \"why_ar\": \"short reason in Arabic\"}], \"next_steps\": [\"3 concrete things to do next time\"]}. " +
      "List EVERY language mistake you find (up to 40), copying the wrong words exactly as written. Be encouraging but honest. Use British spelling." },
    { role: "user", content: `Question: ${sub.topic}\n\nStudent's text (${sub.words} words):\n"""\n${sub.text}\n"""` + chartFacts(chart) },
  ];
}
function parseJSON(t) {
  if (t && typeof t === "object") return t;
  const s = String(t || ""); const a = s.indexOf("{"), b = s.lastIndexOf("}");
  if (a < 0 || b <= a) throw new Error("no json");
  return JSON.parse(s.slice(a, b + 1));
}
function clean(r, sub) {
  const T = TYPES[sub.type] || TYPES.CH, R = RUBRIC[T.kind];
  const arr = (x, n) => (Array.isArray(x) ? x : []).slice(0, n);
  let crit = arr(r.criteria, 4).map((c, i) => ({ name: clip(c.name || (R.crit[i] || [""])[0], 60), band: Math.max(1, Math.min(5, Math.round(Number(c.band) || 1))), comment: clip(c.comment, 300) }));
  if (sub.words < T.min) crit = crit.map(c => ({ ...c, band: Math.min(c.band, 3) }));
  let level = crit.length === 4 ? Math.round(crit.reduce((a, c) => a + c.band, 0) / 4) : Math.round(Number(r.level) || Number(r.score) / 2 || 1);
  level = Math.max(1, Math.min(5, level));
  if (sub.words < 60) level = Math.min(level, 2);
  const score = level * 2;   // rating scale level x 2 (10 / 8 / 6 / 4 / 2); shown mark: chart = level out of 5, e-mail = level x 2 out of 10
  return { score, level, mark: T.max === 5 ? level : score, max: T.max, criteria: crit,
    summary: clip(r.summary, 800), summary_ar: clip(r.summary_ar, 800), task: clip(r.task, 500), organisation: clip(r.organisation, 800),
    strengths: arr(r.strengths, 8).map(x => clip(x, 300)), next_steps: arr(r.next_steps, 6).map(x => clip(x, 300)),
    mistakes: arr(r.mistakes, 40).map(m => ({ wrong: clip(m.wrong, 200), correct: clip(m.correct, 200), type: clip(m.type, 30), why_ar: clip(m.why_ar, 300) })).filter(m => m.wrong) };
}
async function aiGrade(env, sub) {
  if (!env.AI) {   // local test without the AI binding
    return clean({ criteria: [{ band: 3 }, { band: 3 }, { band: 4 }, { band: 3 }], summary: "Test feedback (no AI binding in this environment).", strengths: ["Clear paragraphs"], mistakes: [{ wrong: "go", correct: "went", type: "grammar", why_ar: "الماضي" }], next_steps: ["Use more linkers"] }, sub);
  }
  let last;
  for (const model of MODELS) {
    try {
      const out = await env.AI.run(model, { messages: gradePrompt(sub), max_tokens: 2500, temperature: 0.2 });
      return clean(parseJSON(out.response ?? out), sub);
    } catch (e) { last = e; }
  }
  throw last || new Error("AI failed");
}

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const clip = (s, n) => String(s ?? "").slice(0, n);

export class Board extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec(`CREATE TABLE IF NOT EXISTS notices(id TEXT PRIMARY KEY, created INTEGER, type TEXT, title TEXT, body TEXT, link TEXT, due TEXT, target TEXT);
      CREATE TABLE IF NOT EXISTS live(id TEXT PRIMARY KEY, created INTEGER, title TEXT, url TEXT, starts TEXT, note TEXT);
      CREATE TABLE IF NOT EXISTS students(code TEXT PRIMARY KEY, name TEXT, first_seen INTEGER, last_seen INTEGER, minutes INTEGER DEFAULT 0, logins INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS done(code TEXT, id TEXT, at INTEGER, PRIMARY KEY(code, id));
      CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, t INTEGER, kind TEXT, ref TEXT, data TEXT);
      CREATE INDEX IF NOT EXISTS ev_code ON events(code, t);
      CREATE TABLE IF NOT EXISTS items(code TEXT, kind TEXT, key TEXT, ref TEXT, seen INTEGER, ok INTEGER, bad INTEGER, streak INTEGER, last INTEGER, lastans TEXT, PRIMARY KEY(code, kind, key));
      CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, t INTEGER, act TEXT, ref TEXT, skill TEXT, theme INTEGER, score REAL, max REAL, detail TEXT);
      CREATE INDEX IF NOT EXISTS sc_code ON scores(code, t);
      CREATE TABLE IF NOT EXISTS state(code TEXT PRIMARY KEY, data TEXT, t INTEGER);
      CREATE TABLE IF NOT EXISTS subs(id TEXT PRIMARY KEY, code TEXT, name TEXT, type TEXT, topic TEXT, text TEXT, words INTEGER, created INTEGER, status TEXT, tries INTEGER, result TEXT);
      CREATE TABLE IF NOT EXISTS accounts(user TEXT PRIMARY KEY, name TEXT, cls TEXT, salt TEXT, hash TEXT, temp TEXT, must_change INTEGER, status TEXT, device TEXT, token TEXT, token_t INTEGER, created INTEGER, fails INTEGER DEFAULT 0, lock_until INTEGER DEFAULT 0);
      CREATE INDEX IF NOT EXISTS acc_token ON accounts(token);
      CREATE TABLE IF NOT EXISTS devreq(id TEXT PRIMARY KEY, user TEXT, device TEXT, ua TEXT, created INTEGER, status TEXT);`);
    try { this.sql.exec("ALTER TABLE subs ADD COLUMN chart TEXT"); } catch (e) { /* column already there */ }
    this.env = env;
  }
  rows(q, ...a) { return [...this.sql.exec(q, ...a)]; }

  /* ---- accounts ---- */
  async setPassword(user, pw, temp) {
    const salt = rnd(16, PW_ALPH), hash = await pbkdf2(pw, salt);
    this.sql.exec("UPDATE accounts SET salt=?, hash=?, temp=?, must_change=?, token=NULL WHERE user=?", salt, hash, temp ? pw : null, temp ? 1 : 0, user);
  }
  async addAccounts(list) {
    const created = [], errors = [], now = Date.now();
    for (const st of (list || []).slice(0, 200)) {
      const name = clip(String(st.name || "").trim().replace(/\s+/g, " "), 80), cls = clip(String(st.cls || "").trim(), 20);
      if (name.length < 2) { errors.push({ name: name || "?", why: "no name" }); continue; }
      let user = cleanUser(st.user);
      if (st.user && user.length < 3) { errors.push({ name, why: "username too short" }); continue; }
      if (user && this.rows("SELECT 1 FROM accounts WHERE user=?", user).length) { errors.push({ name, why: "username already used" }); continue; }
      if (!user) { const base = userFromName(name); user = base; let k = 1; while (user.length < 3 || this.rows("SELECT 1 FROM accounts WHERE user=? UNION SELECT 1 FROM students WHERE code=?", user, user).length) user = base + (++k); }
      const pw = tempPassword();
      this.sql.exec("INSERT INTO accounts(user,name,cls,must_change,status,created,fails,lock_until) VALUES(?,?,?,1,'active',?,0,0)", user, name, cls, now);
      await this.setPassword(user, pw, true);
      const ex = this.rows("SELECT 1 FROM students WHERE code=?", user)[0];
      if (ex) this.sql.exec("UPDATE students SET name=? WHERE code=?", name, user);
      else this.sql.exec("INSERT INTO students(code,name,first_seen,last_seen,minutes,logins) VALUES(?,?,?,?,0,0)", user, name, now, 0);
      created.push({ user, name, cls, pw });
    }
    return { created, errors };
  }
  async login(user, pw, device, ua) {
    const now = Date.now(), bad = { error: "Wrong username or password. اسم المستخدم أو كلمة المرور غير صحيحة." };
    const a = this.rows("SELECT * FROM accounts WHERE user=?", user)[0];
    if (!a) { await pbkdf2(pw, "x"); return bad; }
    if (a.lock_until > now) return { error: "Too many wrong tries. Wait 10 minutes. محاولات كثيرة، انتظر 10 دقائق." };
    if ((await pbkdf2(pw, a.salt)) !== a.hash) {
      const f = (a.fails || 0) + 1;
      this.sql.exec("UPDATE accounts SET fails=?, lock_until=? WHERE user=?", f >= 5 ? 0 : f, f >= 5 ? now + 10 * 60000 : 0, user);
      return bad;
    }
    this.sql.exec("UPDATE accounts SET fails=0 WHERE user=?", user);
    if (a.status === "stopped") return { error: "Your account is stopped. Ask your teacher. حسابك موقوف، راجع معلمك." };
    if (!device) return { error: "This browser cannot save data. Turn off private mode and try again." };
    if (a.device && a.device !== device) {
      const rej = this.rows("SELECT 1 FROM devreq WHERE user=? AND device=? AND status='rejected' AND created>?", user, device, now - 86400000)[0];
      if (rej) return { error: "Your teacher did not accept this device. Use your own device. لم يوافق المعلم على هذا الجهاز، استخدم جهازك." };
      const p = this.rows("SELECT id FROM devreq WHERE user=? AND device=? AND status='pending'", user, device)[0];
      if (p) this.sql.exec("UPDATE devreq SET created=?, ua=? WHERE id=?", now, ua, p.id);
      else this.sql.exec("INSERT INTO devreq VALUES(?,?,?,?,?,'pending')", crypto.randomUUID().slice(0, 12), user, device, ua, now);
      this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", user, now, "device_request", "", JSON.stringify({ ua }));
      return { error: "device" };
    }
    const token = newToken();
    this.sql.exec("UPDATE accounts SET device=?, token=?, token_t=? WHERE user=?", device, token, now, user);
    this.sql.exec("UPDATE students SET logins=COALESCE(logins,0)+1, last_seen=?, first_seen=CASE WHEN first_seen IS NULL OR first_seen=0 THEN ? ELSE first_seen END WHERE code=?", now, now, user);
    this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", user, now, "login", "", JSON.stringify({ ua }));
    return { token, user, name: a.name, must_change: !!a.must_change };
  }
  session(token) {
    if (!token || token.length < 20) return null;
    const a = this.rows("SELECT user, name, status, must_change FROM accounts WHERE token=?", token)[0];
    return a && a.status !== "stopped" ? a : null;
  }
  async changePw(user, pw) {
    const prob = pwProblem(pw, user); if (prob) return { error: prob };
    const a = this.rows("SELECT token FROM accounts WHERE user=?", user)[0];
    await this.setPassword(user, pw, false);
    this.sql.exec("UPDATE accounts SET token=? WHERE user=?", a.token, user);   // stay logged in on this device
    this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", user, Date.now(), "password_changed", "", "null");
    return { ok: true };
  }
  logout(user) { this.sql.exec("UPDATE accounts SET token=NULL WHERE user=?", user); this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", user, Date.now(), "logout", "", "null"); }
  accounts() {
    const now = Date.now();
    const seen = Object.fromEntries(this.rows("SELECT code, last_seen FROM students").map(r => [r.code, r.last_seen]));
    return {
      accounts: this.rows("SELECT user,name,cls,status,must_change,temp,device,token,created FROM accounts ORDER BY cls, name COLLATE NOCASE").map(a => ({
        user: a.user, name: a.name, cls: a.cls, status: a.status, must_change: !!a.must_change, temp: a.must_change ? a.temp : null, device: !!a.device,
        online: !!a.token && (seen[a.user] || 0) > now - 10 * 60000, last_seen: seen[a.user] || 0, created: a.created })),
      requests: this.rows("SELECT d.id, d.user, d.ua, d.created, a.name, a.cls FROM devreq d JOIN accounts a ON a.user=d.user WHERE d.status='pending' ORDER BY d.created DESC") };
  }
  async resetPw(user) {
    if (!this.rows("SELECT 1 FROM accounts WHERE user=?", user).length) return { error: "not found" };
    const pw = tempPassword(); await this.setPassword(user, pw, true);
    this.sql.exec("UPDATE accounts SET fails=0, lock_until=0 WHERE user=?", user);
    return { pw };
  }
  setStatus(user, status) { this.sql.exec("UPDATE accounts SET status=?, token=CASE WHEN ?='stopped' THEN NULL ELSE token END WHERE user=?", status, status, user); return { ok: true }; }
  unbind(user) { this.sql.exec("UPDATE accounts SET device=NULL, token=NULL WHERE user=?", user); this.sql.exec("UPDATE devreq SET status='closed' WHERE user=? AND status='pending'", user); return { ok: true }; }
  deviceDecision(id, approve) {
    const r = this.rows("SELECT * FROM devreq WHERE id=? AND status='pending'", id)[0]; if (!r) return { error: "not found" };
    if (approve) {
      this.sql.exec("UPDATE accounts SET device=?, token=NULL WHERE user=?", r.device, r.user);
      this.sql.exec("UPDATE devreq SET status='closed' WHERE user=? AND status='pending' AND id<>?", r.user, id);
    }
    this.sql.exec("UPDATE devreq SET status=? WHERE id=?", approve ? "approved" : "rejected", id);
    this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", r.user, Date.now(), approve ? "device_approved" : "device_rejected", "", "null");
    return { ok: true };
  }
  deleteAccount(user) {
    for (const [t, c] of [["accounts", "user"], ["devreq", "user"], ["students", "code"], ["done", "code"], ["events", "code"], ["items", "code"], ["scores", "code"], ["state", "code"], ["subs", "code"]])
      this.sql.exec(`DELETE FROM ${t} WHERE ${c}=?`, user);
    return { ok: true };
  }

  /* ---- student activity ---- */
  hello(code) {
    this.sql.exec("UPDATE students SET last_seen=? WHERE code=?", Date.now(), code);
    return { ok: true, name: (this.rows("SELECT name FROM accounts WHERE user=?", code)[0] || {}).name || "" };
  }
  log(code, b) {
    const now = Date.now();
    for (const e of (b.events || []).slice(0, 200))
      this.sql.exec("INSERT INTO events(code,t,kind,ref,data) VALUES(?,?,?,?,?)", code, Math.min(Number(e.t) || now, now), clip(e.kind, 30), clip(e.ref, 80), clip(JSON.stringify(e.data ?? null), 4000));
    for (const it of (b.items || []).slice(0, 400)) {
      const kind = clip(it.kind, 10), key = clip(it.key, 120), ok = it.ok ? 1 : 0;
      const ex = this.rows("SELECT streak FROM items WHERE code=? AND kind=? AND key=?", code, kind, key)[0];
      if (ex) this.sql.exec("UPDATE items SET seen=seen+1, ok=ok+?, bad=bad+?, streak=?, last=?, lastans=?, ref=? WHERE code=? AND kind=? AND key=?",
                            ok, 1 - ok, ok ? ex.streak + 1 : 0, now, clip(it.ans, 120), clip(it.ref, 40), code, kind, key);
      else this.sql.exec("INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?)", code, kind, key, clip(it.ref, 40), 1, ok, 1 - ok, ok, now, clip(it.ans, 120));
    }
    for (const sc of (b.scores || []).slice(0, 50))
      this.sql.exec("INSERT INTO scores(code,t,act,ref,skill,theme,score,max,detail) VALUES(?,?,?,?,?,?,?,?,?)", code, Math.min(Number(sc.t) || now, now),
        clip(sc.act, 30), clip(sc.ref, 60), clip(sc.skill, 20), Number(sc.theme) || 0, Number(sc.score) || 0, Number(sc.max) || 0, clip(JSON.stringify(sc.detail ?? null), 6000));
    this.sql.exec("UPDATE students SET last_seen=? WHERE code=?", now, code);
  }
  beat(code) { this.sql.exec("UPDATE students SET minutes=COALESCE(minutes,0)+1, last_seen=? WHERE code=?", Date.now(), code); }
  setState(code, data) { this.sql.exec("INSERT OR REPLACE INTO state VALUES(?,?,?)", code, clip(data, 400000), Date.now()); }
  me(code) {
    const st = this.rows("SELECT data, t FROM state WHERE code=?", code)[0];
    return { state: st ? JSON.parse(st.data) : null, state_t: st ? st.t : 0,
      scores: this.rows("SELECT t,act,ref,skill,theme,score,max FROM scores WHERE code=? ORDER BY t", code),
      items: this.rows("SELECT kind,key,ref,seen,ok,bad,streak,last FROM items WHERE code=?", code),
      student: this.rows("SELECT name,first_seen,last_seen,minutes,logins FROM students WHERE code=?", code)[0] || null,
      subs: this.rows("SELECT type,created,result FROM subs WHERE code=? AND status='done'", code).filter(r => Date.now() >= r.created + READY_MS).map(r => ({ type: r.type, t: r.created, score: JSON.parse(r.result).score })) };
  }
  /* ---- teacher views ---- */
  summaries() {
    const studs = this.rows("SELECT s.*, a.cls FROM students s LEFT JOIN accounts a ON a.user=s.code ORDER BY a.cls, s.name COLLATE NOCASE");
    const asg = this.rows("SELECT id, target FROM notices WHERE type='assignment'");
    return studs.map(s => {
      const sk = {}; this.rows("SELECT skill, SUM(score) AS s, SUM(max) AS m, COUNT(*) AS n FROM scores WHERE code=? AND max>0 GROUP BY skill", s.code).forEach(r => sk[r.skill] = { pct: Math.round(100 * r.s / r.m), n: r.n });
      const w = this.rows("SELECT SUM(CASE WHEN streak>=3 THEN 1 ELSE 0 END) AS mastered, COUNT(*) AS seen FROM items WHERE code=? AND kind='word'", s.code)[0];
      const mine = asg.filter(a => !a.target || JSON.parse(a.target).length === 0 || JSON.parse(a.target).includes(s.code)).map(a => a.id);
      const done = this.rows("SELECT id FROM done WHERE code=?", s.code).map(r => r.id).filter(id => mine.includes(id)).length;
      const ai = this.rows("SELECT result FROM subs WHERE code=? AND status='done'", s.code).map(r => JSON.parse(r.result).score);
      return { ...s, skills: sk, words_mastered: w.mastered || 0, words_seen: w.seen || 0, hw_done: done, hw_total: mine.length,
               writing_avg: ai.length ? Math.round(10 * ai.reduce((a, b) => a + b, 0) / ai.length) / 10 : null, writing_n: ai.length,
               activities: this.rows("SELECT COUNT(*) AS n FROM scores WHERE code=?", s.code)[0].n };
    });
  }
  profile(code) {
    return { student: this.rows("SELECT * FROM students WHERE code=?", code)[0] || null,
      scores: this.rows("SELECT t,act,ref,skill,theme,score,max,detail FROM scores WHERE code=? ORDER BY t DESC LIMIT 1500", code).map(r => ({ ...r, detail: r.detail ? JSON.parse(r.detail) : null })),
      items: this.rows("SELECT kind,key,ref,seen,ok,bad,streak,last,lastans FROM items WHERE code=? ORDER BY bad DESC", code),
      events: this.rows("SELECT t,kind,ref,data FROM events WHERE code=? ORDER BY t DESC LIMIT 400", code).map(r => ({ ...r, data: r.data ? JSON.parse(r.data) : null })),
      subs: this.rows("SELECT id,type,topic,text,words,created,status,result,chart FROM subs WHERE code=? ORDER BY created DESC", code).map(r => ({ ...r, result: r.result ? JSON.parse(r.result) : null, chart: r.chart ? JSON.parse(r.chart) : null })),
      done: this.rows("SELECT id, at FROM done WHERE code=?", code),
      state: (this.rows("SELECT data FROM state WHERE code=?", code)[0] || {}).data || null };
  }
  classView() {
    return {
      skills: this.rows("SELECT skill, SUM(score) AS s, SUM(max) AS m, COUNT(DISTINCT code) AS students FROM scores WHERE max>0 GROUP BY skill"),
      themes: this.rows("SELECT theme, skill, SUM(score) AS s, SUM(max) AS m FROM scores WHERE max>0 AND theme>0 GROUP BY theme, skill"),
      words: this.rows("SELECT key, SUM(bad) AS bad, SUM(ok) AS ok, COUNT(DISTINCT code) AS students FROM items WHERE kind='word' GROUP BY key HAVING SUM(bad)>0 ORDER BY SUM(bad)*1.0/(SUM(ok)+SUM(bad)) DESC, SUM(bad) DESC LIMIT 25"),
      questions: this.rows("SELECT key, ref, SUM(bad) AS bad, SUM(ok) AS ok FROM items WHERE kind IN ('q','gram') GROUP BY key HAVING SUM(bad)>0 ORDER BY SUM(bad)*1.0/(SUM(ok)+SUM(bad)) DESC, SUM(bad) DESC LIMIT 25"),
      activity: this.rows("SELECT date(t/1000,'unixepoch') AS d, COUNT(*) AS n FROM scores WHERE t>? GROUP BY d ORDER BY d", Date.now() - 30 * 86400000) };
  }
  inbox(code) {
    this.sql.exec("UPDATE students SET last_seen=? WHERE code=?", Date.now(), code);
    const notices = this.rows("SELECT id,created,type,title,body,link,due,target FROM notices ORDER BY created DESC LIMIT 200")
      .filter(n => !n.target || JSON.parse(n.target).length === 0 || JSON.parse(n.target).includes(code))
      .map(({ target, ...n }) => n);
    const live = this.rows("SELECT id,title,url,starts,note FROM live ORDER BY starts ASC");
    const done = this.rows("SELECT id FROM done WHERE code=?", code).map(r => r.id);
    return { notices, live, done };
  }
  setDone(code, id, isDone) {
    if (isDone) this.sql.exec("INSERT OR REPLACE INTO done VALUES(?,?,?)", code, id, Date.now());
    else this.sql.exec("DELETE FROM done WHERE code=? AND id=?", code, id);
  }
  state() {
    const notices = this.rows("SELECT * FROM notices ORDER BY created DESC").map(n => ({ ...n, target: n.target ? JSON.parse(n.target) : [],
      done: this.rows("SELECT code FROM done WHERE id=?", n.id).map(r => r.code) }));
    const subs = this.rows("SELECT id,code,name,type,topic,words,created,status,result,text,chart FROM subs ORDER BY created DESC LIMIT 150")
      .map(r => ({ ...r, result: r.result ? JSON.parse(r.result) : null, chart: r.chart ? JSON.parse(r.chart) : null }));
    return { notices, live: this.rows("SELECT * FROM live ORDER BY starts ASC"),
             students: this.rows("SELECT s.code, s.name, a.cls FROM students s JOIN accounts a ON a.user=s.code ORDER BY a.cls, s.name COLLATE NOCASE"), subs };
  }
  addNotice(n) {
    const id = crypto.randomUUID().slice(0, 8);
    this.sql.exec("INSERT INTO notices VALUES(?,?,?,?,?,?,?,?)", id, Date.now(), n.type, n.title, n.body, n.link, n.due, JSON.stringify(n.target));
    return id;
  }
  delNotice(id) { this.sql.exec("DELETE FROM notices WHERE id=?", id); this.sql.exec("DELETE FROM done WHERE id=?", id); }
  submit(code, type, topic, text, words, chart) {
    const day = Date.now() - 86400000;
    const n = this.rows("SELECT COUNT(*) AS n FROM subs WHERE code=? AND created>?", code, day)[0].n;
    if (n >= 6) return { error: "You can send 6 texts a day. Try again tomorrow. يمكنك إرسال 6 موضوعات في اليوم." };
    const id = crypto.randomUUID().slice(0, 10), now = Date.now();
    const name = (this.rows("SELECT name FROM students WHERE code=?", code)[0] || {}).name || "";
    this.sql.exec("INSERT INTO subs(id,code,name,type,topic,text,words,created,status,tries,result,chart) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", id, code, name, type, topic, text, words, now, "pending", 0, null, chart ? JSON.stringify(chart) : null);
    this.ctx.storage.setAlarm(Date.now() + 2000);
    return { id, ready_at: now + READY_MS };
  }
  mySubs(code) {
    const now = Date.now();
    const rows = this.rows("SELECT id,type,topic,text,words,created,status,result,chart FROM subs WHERE code=? ORDER BY created DESC LIMIT 30", code);
    if (rows.some(r => r.status === "pending")) this.ctx.storage.setAlarm(Date.now() + 1000);
    return rows.map(r => { const ready = now >= r.created + READY_MS && r.status === "done";
      return { id: r.id, type: r.type, topic: r.topic, text: r.text, words: r.words, created: r.created, ready_at: r.created + READY_MS, chart: r.chart ? JSON.parse(r.chart) : null,
               status: ready ? "ready" : (r.status === "failed" ? "failed" : "waiting"), result: ready ? JSON.parse(r.result) : null }; });
  }
  async alarm() {
    const todo = this.rows("SELECT * FROM subs WHERE status='pending' AND tries<3 ORDER BY created LIMIT 4");
    for (const sub of todo) {
      try { const res = await aiGrade(this.env, sub); this.sql.exec("UPDATE subs SET status='done', result=? WHERE id=?", JSON.stringify(res), sub.id); }
      catch (e) { this.sql.exec("UPDATE subs SET tries=tries+1, status=CASE WHEN tries+1>=3 THEN 'failed' ELSE 'pending' END WHERE id=?", sub.id); }
    }
    if (this.rows("SELECT COUNT(*) AS n FROM subs WHERE status='pending' AND tries<3")[0].n) this.ctx.storage.setAlarm(Date.now() + 60000);
  }
  retry(id) { this.sql.exec("UPDATE subs SET status='pending', tries=0 WHERE id=?", id); this.ctx.storage.setAlarm(Date.now() + 1000); }
  addLive(l) { const id = crypto.randomUUID().slice(0, 8); this.sql.exec("INSERT INTO live VALUES(?,?,?,?,?,?)", id, Date.now(), l.title, l.url, l.starts, l.note); return id; }
  delLive(id) { this.sql.exec("DELETE FROM live WHERE id=?", id); }
}

let TFAIL = { n: 0, t: 0 };   // simple brake on teacher-password guessing (per worker instance)
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);
    const board = env.BOARD.get(env.BOARD.idFromName("main"));
    const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
    const p = url.pathname;
    try {
      /* ---- teacher ---- */
      if (p.startsWith("/api/t/")) {
        if (TFAIL.n >= 10 && Date.now() - TFAIL.t < 10 * 60000) return json({ error: "Too many wrong passwords. Wait 10 minutes." }, 429);
        const key = req.headers.get("x-teacher-key") || "";
        if ((await sha256hex("ES10-TEACHER:" + key)) !== TEACHER_HASH) { TFAIL = { n: Date.now() - TFAIL.t > 10 * 60000 ? 1 : TFAIL.n + 1, t: Date.now() }; return json({ error: "wrong password" }, 401); }
        TFAIL = { n: 0, t: 0 };
        const user = cleanUser(body.user);
        if (p === "/api/t/login") return json({ ok: true });
        if (p === "/api/t/accounts") return json(await board.accounts());
        if (p === "/api/t/accounts/add") return json(await board.addAccounts(Array.isArray(body.students) ? body.students : []));
        if (p === "/api/t/accounts/reset") return json(await board.resetPw(user));
        if (p === "/api/t/accounts/status") return json(await board.setStatus(user, body.status === "stopped" ? "stopped" : "active"));
        if (p === "/api/t/accounts/unbind") return json(await board.unbind(user));
        if (p === "/api/t/accounts/delete") return json(await board.deleteAccount(user));
        if (p === "/api/t/device") return json(await board.deviceDecision(clip(body.id, 20), !!body.approve));
        if (p === "/api/t/state") return json(await board.state());
        if (p === "/api/t/notice") {
          const type = ["notice", "assignment"].includes(body.type) ? body.type : "notice";
          const target = Array.isArray(body.target) ? body.target.map(cleanUser).filter(Boolean) : [];
          if (!clip(body.title, 200).trim()) return json({ error: "title required" }, 400);
          return json({ id: await board.addNotice({ type, title: clip(body.title, 200), body: clip(body.body, 3000), link: clip(body.link, 500), due: clip(body.due, 40), target }) });
        }
        if (p === "/api/t/delete") { await board.delNotice(clip(body.id, 20)); return json({ ok: true }); }
        if (p === "/api/t/live") {
          if (!/^https?:\/\//.test(body.url || "")) return json({ error: "link must start with https://" }, 400);
          return json({ id: await board.addLive({ title: clip(body.title, 200) || "Live class", url: clip(body.url, 500), starts: clip(body.starts, 40), note: clip(body.note, 500) }) });
        }
        if (p === "/api/t/retry") { await board.retry(clip(body.id, 20)); return json({ ok: true }); }
        if (p === "/api/t/live/delete") { await board.delLive(clip(body.id, 20)); return json({ ok: true }); }
        if (p === "/api/t/students") return json({ students: await board.summaries() });
        if (p === "/api/t/student") return json(await board.profile(cleanUser(url.searchParams.get("code"))));
        if (p === "/api/t/class") return json(await board.classView());
        return json({ error: "not found" }, 404);
      }
      /* ---- log in ---- */
      if (p === "/api/auth/login") {
        if (req.method !== "POST") return json({ error: "POST only" }, 405);
        const user = cleanUser(body.user), pw = clip(body.pw, 80);
        if (!user || !pw) return json({ error: "Write your username and password." }, 400);
        return json(await board.login(user, pw, clip(body.device, 80), clip(body.ua, 160)));
      }
      /* ---- everything else needs a valid session ---- */
      const me = await board.session(req.headers.get("x-session") || "");
      if (!me) return json({ error: "session", msg: "You were logged out (your account was opened again, or your teacher changed it). Log in again. <span class=\"ar\">انتهت الجلسة، ادخل مرة أخرى.</span>" }, 401);
      const code = me.user;
      if (p === "/api/auth/change") return json(await board.changePw(code, clip(body.pw, 80)));
      if (p === "/api/auth/logout") { await board.logout(code); return json({ ok: true }); }
      if (me.must_change) return json({ error: "must_change" }, 403);
      if (p === "/api/hello") return json(await board.hello(code));
      if (p === "/api/inbox") return json(await board.inbox(code));
      if (p === "/api/log") { await board.log(code, body); return json({ ok: true }); }
      if (p === "/api/beat") { await board.beat(code); return json({ ok: true }); }
      if (p === "/api/state") { await board.setState(code, JSON.stringify(body.data ?? {})); return json({ ok: true }); }
      if (p === "/api/me") return json(await board.me(code));
      if (p === "/api/write/submit") {
        const type = TYPES[body.type] ? body.type : "CH", text = clip(body.text, 6000).trim(), topic = clip(body.topic, 600).trim();
        const words = (text.match(/[A-Za-z0-9’']+/g) || []).length;
        if (!topic) return json({ error: "Choose or write a topic first." }, 400);
        if (words < 60) return json({ error: "Write at least 60 words before you send (the exam needs 100+)." }, 400);
        if (words > 450) return json({ error: "Your text is too long (more than 450 words)." }, 400);
        const chart = type === "CH" ? cleanChart(body.chart) : null;
        if (type === "CH" && !chart) return json({ error: "The chart data is missing. Choose a chart first." }, 400);
        return json(await board.submit(code, type, topic, text, words, chart));
      }
      if (p === "/api/write/list") return json({ subs: await board.mySubs(code), now: Date.now() });
      if (p === "/api/done") { await board.setDone(code, clip(body.id, 20), !!body.done); return json({ ok: true }); }
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: "server error" }, 500);
    }
  },
};
