// explainer-film · 白板库 WB（由 engine/spacex_wb/common.js 改出的副本，原文件一字不动）。
// 一整块暖纸大白板 ＋ 一台相机（RSA 型，语法卡 y3_whiteboard）。全片各段画在同一块板上，每段的 scene 文件只往板上「排笔画」和「排相机」，
// 画面只由全片时间 t 决定——段与段之间没有转场函数，转场就是相机在板上移动，板上的东西不跳。
// 相对原版的改动：
//  ① 色板、字体、笔速、版式行、字幕、纸纹全部来自主题 T（window.WB_THEME，engine/<片名>/theme.js 由 project.json 的 theme 生成）；
//     缺省＝白板暖纸色板：板底 #f5efe1（纸纹＋36px 点阵，点阵跟板走）、墨 #2b2620、唯一强调红 #c0391b（淡面 rgba(192,57,27,.18)）、卡面 #fbf7ec；
//     主题里的颜色启动时用 CSS.supports 核，非法即 console.error（render.py 记为页面错误、非零退出）；
//  ② 板上字用系统字体：标题与标签 Songti SC、卡内正文 PingFang SC、大数字 Georgia 粗体；不用随包字体，启动时核这三种系统字体在不在（缺就拒绝启动）；
//  ③ WB.move 默认 creep 0：相机停留时完全不动，画面的「活」只来自正在写的字、正在画的线、正在滚的数；
//  ④ 不加载手图、默认不画笔尖（WB.PEN = false）；
//  ⑤ （无改动：与原版一样只按 1920×1080 画，不做整体缩放；草稿 960×540 由 tools/render.sh 先渲 1920×1080 再用 ffmpeg 缩）；
//  ⑥ 节拍级对位 WB.qb / WB.qbe（engine/<片名>/tmb.js）；WB.q / WB.qe 不再依赖 spacex/tm.js；
//  ⑦ 文字可选 fam（字体）、wt（字重）、rot（旋转）；任何笔画可设 dims（按时间变淡，如「其余卡降到 70% 墨色」）；
//  ⑧ 具名元素：笔画带 el（timeline 事件的 el），事件实际起点用 WB.ev 登记 → eventTimes()；visibleText()/visibleItems()/elementBoxes(t)；
//  ⑨ 字幕层 GLOBAL_OVERLAY（底部 200px 带，PingFang 42px，纸卡底，按 TIMING.seg[].captions 起止）；
//  ⑩ ?t=秒 预览定格；?lockcam=秒（或运行时设 WB.lockcam）用该时刻的相机渲任意 t（QA 用来剔除运镜）；
//  ⑪ 字体 document.fonts.load 完成并核过之后才建板（WB.build）、才置 __ready；
//  ⑫ 便签卡、数字滚动、按 x 长出的曲线、红圈、划掉等常用件（WB.card / count / grow / ring / strike）。
//  ⑬ 砸入类动作件：WB.pop 的 slam（0.17 s 砸入）、WB.count 的 slamIn（起滚那一刻整数砸入）、WB.pill（胶囊小标整块砸入）、WB.travel（远行），
//     pop 另记落定字框 rb（WB.items 用它给版面读数；bb 仍含放大过冲，供绘制与裁剪）。
//  ⑭ 相机落地停稳 WB.SETTLE（0.5 s）再起笔；WB.fade 擦干净（不留淡痕）；WB.lead 可走自定路径（o.pts）。
//  ⑮ 画法包钩子 WB.STYLE（engine/<片名>/wb/style.js 在本文件之后加载、Object.assign 设钩子；缺省值下与白板逐像素一致）：
//     ground(c, t, cam) 画底面（null＝纸面）；overlay(c, t, cam) 屏幕层（FX 之后、字幕之前）；text 'hand'|'type'|'fade'；jitter 手抖倍率；
//     card(g, s, q, t) 换便签卡画法；motionBlur 运镜糊影（缺省 true；false＝运镜时每帧只按当时相机画一遍，干净平移）。主题 extra_colors 列的额外颜色键同样 CSS.supports 核，全部颜色键在 WB.C；
//     通用件 WB.image（图片须登记在 project.json 的 assets）、WB.icon（扁平图标，纯绘制）；装饰性持续动作（线 boil、粒子、呼吸）一律经 WB.ambientT(t) 取时间。
//  ⑯ 正式接口（缺省值下渲染与之前逐像素一致）：
//     笔画选项 camOk: true＝慢推中允许起笔（WB.build 不把它顺延到停稳之后；qa 的 cam_pen 只在起笔起 0.3 s 内相机够慢时放行，引线仍用 lead）；
//     会动的自定义件给 bbAt(t) 或 pos(t)＋ext、不给 bb：建板完成后引擎求全程位置框的并集当包围盒（见「动态包围盒」）；
//     WB.STYLE 再加 stroke(g, s, d, t)（线笔画的画法）、glyph(s, i, f)（手写字的露出遮罩）、caption(ctx, text, box)（字幕底条），drawBoard 每遍设 WB.drawT＝本遍绘制时刻；
//     WB.items 每条另报 sid（WB.S 下标），qa 的 layout 按它归并（同一串字在两处是两条笔画，分别计）。
// 其余 WB API（line/text/pop/fill/custom/hatch/arrow/lead/sk/prep/相机/章节）保留；原版的 SpaceX 画稿库（火箭、地球、火柴人等简笔画）已删。
// 约定：WB.cur 是「下一笔从什么时候开始」（全片秒）；WB.line/text 会把它往后推；WB.pop/fill/custom 不推（或只推一点）。
(() => {
const W = 1920, H = 1080;   // 逻辑画布
const { clamp, lerp } = U;
// 主题：缺省值＝白板暖纸值；window.WB_THEME 逐键覆盖，嵌套对象（fonts/world/rows/caption/paper）逐子键合并
const TD = { ink: '#2b2620', accent: '#c0391b', board: '#f5efe1', wash: 'rgba(192,57,27,.18)', dim: '#8a7d69', soft: '#55493a', card: '#fbf7ec', line: '#d8cbb0',
  tape: 'rgba(222,196,138,.6)', card_band: 'rgba(192,57,27,.10)', fonts: { title: 'Songti SC', body: 'PingFang SC', num: 'Georgia' },
  required_fonts: ['Songti SC', 'PingFang SC', 'Georgia'], speed: 2500, lw: 6.5, settle: 0.5, world: { w: 4800, h: 2800 }, rows: { A: 80, B: 1250, C: 2300 },
  caption: { band: 200, size: 42, bg: 'rgba(251,247,236,.94)', max_chars: 20 },
  paper: { grain: [110, 92, 64], dots: 'rgba(120,100,70,.22)', light: 'rgba(255,255,255,.38)', warm: 'rgba(190,160,110,.14)' } };
const TU = window.WB_THEME || {}, T = Object.assign({}, TD, TU);
for (const k of ['fonts', 'world', 'rows', 'caption', 'paper']) T[k] = Object.assign({}, TD[k], TU[k] || {});
const fam = n => /^[A-Za-z][A-Za-z0-9-]*$/.test(n) ? n : `"${n}"`;   // 带空格的字体名加引号（"Songti SC"），单词名照写（Georgia）
const COLS = ['ink', 'accent', 'board', 'wash', 'dim', 'soft', 'card', 'line', 'tape', 'card_band'];
const EXTRA = Array.isArray(T.extra_colors) ? T.extra_colors.filter(k => typeof k === 'string' && k) : [];   // 画法包的额外颜色键（style.json extra_colors，建工程时写进主题）
const themeBad = () => { const bad = [], col = (k, v) => { if (typeof v !== 'string' || !CSS.supports('color', v)) bad.push(`${k}=${JSON.stringify(v)}`); };
  COLS.forEach(k => col(k, T[k]));
  if (T.extra_colors != null && !(Array.isArray(T.extra_colors) && EXTRA.length === T.extra_colors.length)) bad.push(`extra_colors=${JSON.stringify(T.extra_colors)}`);
  EXTRA.forEach(k => col(k, T[k]));
  col('caption.bg', T.caption.bg); ['dots', 'light', 'warm'].forEach(k => col('paper.' + k, T.paper[k]));
  for (const k of ['speed', 'lw', 'settle']) if (!(typeof T[k] === 'number' && T[k] > 0)) bad.push(`${k}=${JSON.stringify(T[k])}`);
  for (const k of ['band', 'size', 'max_chars']) if (!(typeof T.caption[k] === 'number' && T.caption[k] > 0)) bad.push(`caption.${k}=${JSON.stringify(T.caption[k])}`);
  if (!(Array.isArray(T.paper.grain) && T.paper.grain.length === 3 && T.paper.grain.every(v => Number.isInteger(v) && v >= 0 && v <= 255))) bad.push(`paper.grain=${JSON.stringify(T.paper.grain)}`);
  for (const k of ['title', 'body', 'num']) if (typeof T.fonts[k] !== 'string' || !T.fonts[k]) bad.push(`fonts.${k}=${JSON.stringify(T.fonts[k])}`);
  return bad; };
{ const bad = themeBad(); if (bad.length) console.error('WB_THEME 主题值非法（project.json 的 theme）：' + bad.join('；')); }
const INK = T.ink, OR = T.accent, BOARD = T.board, WASH = T.wash;
const FONT = fam(T.fonts.title), BODY = fam(T.fonts.body), NUMF = fam(T.fonts.num);
const DIM = T.dim, SOFT = T.soft, CARD = T.card, LINE = T.line, TAPE = T.tape;
const SPEED = T.speed, LW = T.lw, BAND = H - T.caption.band;   // BAND＝字幕带上沿（1080p 下 880）
const WB = window.WB = { INK, OR, BOARD, WASH, FONT, BODY, NUMF, DIM, SOFT, CARD, LINE, TAPE, SPEED, LW,
  S: [], K: [], FX: [], WHIP: [], CH: {}, EV: [], cur: 0, built: false, texts: [], PEN: false, lockcam: null, lastT: 0, SETTLE: T.settle, THEME: T, WORLD: T.world };
const ROW = Object.assign({}, T.rows);
WB.ROW = ROW;
// 全部颜色键（含画法包额外色，如 WB.C.pink）：场景里颜色一律经它或 WB.INK/OR/… 取；取本画法没有的键（换过画法？）console.warn 一次，值为 undefined（各件按缺省色画）
WB.C = new Proxy(Object.fromEntries(COLS.concat(EXTRA).map(k => [k, T[k]])), { get(o, k) {
  if (typeof k === 'string' && !(k in o) && !(WB._cwarn || (WB._cwarn = new Set())).has(k)) { WB._cwarn.add(k); console.warn(`WB.C.${k}：本画法的主题里没有这个颜色键（换过画法？），按件的缺省色画`); }
  return o[k]; } });
// 画法钩子：缺省值＝白板（逐像素与加钩子之前一致）；style.js 用 Object.assign(WB.STYLE, {...}) 改，不得给 WB／DG 等引擎函数重新赋值。
// stroke(g, s, d, t)：画线笔画 s 的前 d 弧长（g 已设好 strokeStyle、lineWidth、虚线），返回笔尖｜null；null＝DG.drawPartial 等宽描边。
// glyph(s, i, f)：手写字 s 第 i 个字写到 f（0–1）时的露出遮罩，返回 [Path2D（字内坐标：原点＝该字左端、基线）, 笔尖] 或 null（null＝这个字没有笔顺数据，按之字形揭开）；
//   null＝WB.so 取笔顺中线＋WB.soAt 沿中线露出。caption(ctx, text, box)：画字幕底条（box = {x, y, w, h, r, lines, size}，字由引擎随后画在上面）；null＝圆角纸卡条。
WB.STYLE = { name: null, ground: null, overlay: null, text: 'hand', jitter: 1, card: null, motionBlur: true, stroke: null, glyph: null, caption: null };
const QS = new URLSearchParams(location.search);
if (QS.has('lockcam')) WB.lockcam = +QS.get('lockcam');
const PREVIEW_T = QS.has('t') ? +QS.get('t') : null;
// 装饰性持续动作（线 boil、粒子、呼吸、天色缓变）的时间源：QA 锁相机（WB.lockcam）时冻结在锁定时刻；页面参数 noambient=1
// （或 render.sh --noambient 生成的包装 eras 设 window.WB_NOAMBIENT）时恒为 0。承载内容的揭开不用它。
const NOAMB = QS.get('noambient') === '1' || window.WB_NOAMBIENT === true;
WB.ambientT = t => NOAMB ? 0 : WB.lockcam != null ? WB.lockcam : t;

// ---------- 时间 ----------
const segFind = (id, key, which) => {
  const s = TIMING.seg[id], i = s.text.indexOf(key);
  if (i < 0) { console.error(`WB.q: 段 ${id} 的口播里没有「${key}」`); return s.t0; }
  const j = which === 'end' ? i + key.length - 1 : i; return s.t0 + (which === 'end' ? s.charEnd[j] : s.charStart[j]);
};
WB.T0 = id => TIMING.seg[id].t0;
WB.T1 = id => TIMING.seg[id].t0 + TIMING.seg[id].dur;
WB.q = (id, key) => segFind(id, key, 'start');
WB.qe = (id, key) => segFind(id, key, 'end');
WB.qb = (beat, key) => TMB.cue(beat, key);
WB.qbe = (beat, key) => TMB.end(beat, key);
WB.vo = beat => TMB.vo(beat);
WB.at = t => (WB.cur = t);
WB.go = t => (WB.cur = Math.max(WB.cur, t));

// ---------- 几何 ----------
const bbOf = (pts, pad = 0) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [x, y] of pts) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } return [x0 - pad, y0 - pad, x1 + pad, y1 + pad]; };
WB.bbOf = bbOf;
WB.union = (...bbs) => { const r = [1e9, 1e9, -1e9, -1e9], list = bbs.length === 1 && Array.isArray(bbs[0][0]) ? bbs[0] : bbs; for (const b of list) if (b) { r[0] = Math.min(r[0], b[0]); r[1] = Math.min(r[1], b[1]); r[2] = Math.max(r[2], b[2]); r[3] = Math.max(r[3], b[3]); } return r; };
WB.circ = (cx, cy, r, turns = 1.06, a0 = -Math.PI / 2) => DG.arcPts(cx, cy, r, r, a0, a0 + turns * Math.PI * 2, Math.max(18, Math.round(r * turns / 3)));
WB.ell = (cx, cy, rx, ry, a0 = -Math.PI / 2, turns = 1.03, rot = 0, n = 64) => { const c = Math.cos(rot), s = Math.sin(rot);
  return DG.arcPts(0, 0, rx, ry, a0, a0 + turns * Math.PI * 2, n).map(([x, y]) => [cx + x * c - y * s, cy + x * s + y * c]); };
WB.dense = (P, k = 10) => { const out = []; for (let i = 0; i < P.length - 1; i++) for (let j = 0; j < k; j++) out.push([lerp(P[i][0], P[i + 1][0], j / k), lerp(P[i][1], P[i + 1][1], j / k)]); out.push(P[P.length - 1]); return out; };
WB.rect = (x, y, w, h) => WB.dense([[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y + 2]], 12);
WB.quad = (a, c, b, n = 28) => { const o = []; for (let i = 0; i <= n; i++) { const u = i / n; o.push([(1 - u) * (1 - u) * a[0] + 2 * u * (1 - u) * c[0] + u * u * b[0], (1 - u) * (1 - u) * a[1] + 2 * u * (1 - u) * c[1] + u * u * b[1]]); } return o; };
WB.xf = (pts, x, y, s = 1, r = 0) => { const c = Math.cos(r), n = Math.sin(r); return pts.map(([a, b]) => [x + (a * c - b * n) * s, y + (a * n + b * c) * s]); };

// ---------- 具名元素与事件登记 ----------
// WB.group(el, fn)：fn 里新压进 WB.S 的笔画都打上 el（已有 el 的不改）；WB.ev(节拍, el, 动作, 笔画|秒, dur)：登记 timeline 事件的实际起点
// （传笔画对象时取 build 之后它的 t0——「一支笔同时只画一笔」可能把它顺延）。eventTimes() 给 QA 用。
WB.group = (el, fn) => { const n0 = WB.S.length; const r = fn(); WB.S.slice(n0).forEach(s => { if (!s.el) s.el = el; }); return r; };
// dur 缺省：线、字、弹入取它自己的实际时长（随口播放慢的字按真实写字时长查），其余取 timeline 里的 dur
WB.ev = (beat, el, act, ref, dur) => { const e = TMB.ev(beat, el, act), own = ref && ['text', 'line', 'pop'].includes(ref.kind) ? Math.max(0.2, ref.t1 - ref.t0) : null;
  WB.EV.push({ beat, el, do: act, ref, dur: dur ?? own ?? e.dur ?? 0.5 }); return ref; };
const evStart = r => typeof r === 'number' ? r : Array.isArray(r) ? Math.min(...r.map(evStart)) : r && r.t0 != null ? r.t0 : NaN;
// 变淡：给 el（含 el.子项）的全部笔画在 t 起 dur 秒内把不透明度变到 a（「其余卡降到 70% 墨色」）
WB.dimEl = (el, t, a, dur = 0.3) => WB.S.forEach(s => { if (s.el === el || (s.el && s.el.startsWith(el + '.'))) (s.dims || (s.dims = [])).push([t, a, dur]); });
const dimAt = (s, t) => { let a = 1; if (!s.dims) return 1; for (const [t0, to, d] of s.dims) { if (t < t0) break; a = lerp(a, to, MO.sineInOut(clamp((t - t0) / d))); } return a; };

// ---------- 笔画 ----------
WB.line = (raw, o = {}) => {
  const { w = LW, col = INK, speed = SPEED, smooth = true, amp = 1.9, min = 0.04, gap = 0.02, dash = null, until = null } = o;
  const pts = smooth ? DG.hand(raw, { amp: amp * WB.STYLE.jitter, seed: o.seed ?? WB.S.length + 7, per: 8 }) : raw;   // 手抖×画法 jitter（sk/sketch/ring 等都经这里）
  const cum = DG.cum(pts), len = cum[cum.length - 1], d = o.dur ?? Math.max(min, len / speed);
  const s = { kind: 'line', pts, cum, len, w, col, dash, t0: o.t0 ?? WB.cur, until, bb: bbOf(pts, w + 4), handed: o.handed !== false, nofit: !!o.nofit, el: o.el, ease: o.ease };
  if (o.camOk) s.camOk = true;   // 慢推中允许起笔（见 WB.build、qa 的 cam_pen）；line/text/pop/fill/custom 都认这个选项，也可建好后设 s.camOk = true
  s.t1 = s.t0 + d; WB.S.push(s); if (o.t0 == null) WB.cur += d + gap; return s;
};
const mctx = () => WB._m || (WB._m = document.createElement('canvas').getContext('2d'));
WB.cf = (ch, size, fam = FONT, wt = '') => `${wt ? wt + ' ' : ''}${size}px ${fam}`;
WB.measure = (str, size, fam = FONT, wt = '') => { const g = mctx(); let w = 0; for (const ch of str) { g.font = WB.cf(ch, size, fam, wt); w += g.measureText(ch).width; } return w; };
// 笔顺：汉字沿 hanzi-writer 的笔画中线一笔一笔露出字（1024 格，y 朝上，顶边 900）；数字用手写中线（按字的墨迹框归一化）；
// 其余字符（拉丁字母、标点）仍用之字形揭开。中线只决定「先露哪里」，字形本身不变，写完正好是整字。
const DIGM = {
  '0': [[[0.55, 0.02], [0.2, 0.15], [0.05, 0.5], [0.2, 0.88], [0.5, 0.98], [0.82, 0.86], [0.95, 0.5], [0.82, 0.13], [0.5, 0.02], [0.3, 0.1]]],
  '1': [[[0.15, 0.22], [0.6, 0.02], [0.6, 0.98]]],
  '2': [[[0.1, 0.25], [0.35, 0.03], [0.7, 0.05], [0.88, 0.28], [0.75, 0.55], [0.08, 0.97], [0.95, 0.97]]],
  '3': [[[0.1, 0.12], [0.45, 0.02], [0.82, 0.15], [0.8, 0.38], [0.45, 0.5], [0.85, 0.62], [0.88, 0.85], [0.5, 0.98], [0.08, 0.88]]],
  '4': [[[0.68, 0.98], [0.68, 0.02], [0.05, 0.7], [0.97, 0.7]]],
  '5': [[[0.88, 0.04], [0.25, 0.04], [0.15, 0.48], [0.5, 0.4], [0.88, 0.58], [0.85, 0.85], [0.5, 0.98], [0.1, 0.88]]],
  '6': [[[0.8, 0.04], [0.35, 0.25], [0.1, 0.62], [0.25, 0.92], [0.55, 0.98], [0.88, 0.8], [0.85, 0.55], [0.5, 0.45], [0.15, 0.6]]],
  '7': [[[0.05, 0.04], [0.95, 0.04], [0.65, 0.45], [0.38, 0.98]]],
  '8': [[[0.55, 0.48], [0.2, 0.3], [0.3, 0.06], [0.55, 0.02], [0.8, 0.12], [0.78, 0.32], [0.45, 0.52], [0.12, 0.72], [0.25, 0.94], [0.55, 0.98], [0.88, 0.8], [0.75, 0.6], [0.5, 0.5]]],
  '9': [[[0.85, 0.32], [0.55, 0.5], [0.2, 0.42], [0.12, 0.18], [0.45, 0.02], [0.85, 0.12], [0.9, 0.4], [0.75, 0.75], [0.45, 0.98]]],
};
const soCache = new Map();
WB.so = (ch, size, wch, fam = FONT, wt = '') => {
  const key = ch + '|' + size + '|' + wch.toFixed(2) + '|' + fam + '|' + wt; if (soCache.has(key)) return soCache.get(key);
  let strokes = null, bw = 0; const M = window.WB_STROKES && window.WB_STROKES[ch];
  if (M) { const k = size / 1024; strokes = M.map(st => st.map(([X, Y]) => [X * k + (wch - size) / 2, -size * 0.88 + (900 - Y) * k])); bw = size * 0.22; }
  else if (DIGM[ch]) { const g = mctx(); g.font = WB.cf(ch, size, fam, wt); const m = g.measureText(ch), x0 = -m.actualBoundingBoxLeft, x1 = m.actualBoundingBoxRight, y0 = -m.actualBoundingBoxAscent, y1 = m.actualBoundingBoxDescent;
    strokes = DIGM[ch].map(st => st.map(([u, v]) => [x0 + u * (x1 - x0), y0 + v * (y1 - y0)])); bw = size * 0.26; }
  let r = null;
  if (strokes) { const cums = strokes.map(DG.cum), lens = cums.map(c => c[c.length - 1]), gap = size * 0.1; r = { strokes, cums, lens, gap, bw, tot: lens.reduce((a, b) => a + b, 0) + gap * (strokes.length - 1) }; }
  soCache.set(key, r); return r;
};
WB.soAt = (so, f, mask = true) => {
  let d = f * so.tot, tip = so.strokes[0][0]; const p = mask ? new Path2D() : null;
  for (let j = 0; j < so.strokes.length && d > 0; j++) {
    const dd = Math.min(d, so.lens[j]); if (mask) p.addPath(DG.revealMask(so.strokes[j], so.cums[j], dd, so.bw)); tip = DG.pointAt(so.strokes[j], so.cums[j], dd);
    d -= so.lens[j];
    if (d > 0 && j < so.strokes.length - 1) { if (d < so.gap) { const a = so.strokes[j][so.strokes[j].length - 1], b = so.strokes[j + 1][0], u = d / so.gap; tip = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u]; } d -= so.gap; }
  }
  return [p, tip];
};
const rotBB = (x0, y0, x1, y1, ox, oy, r) => { if (!r) return [x0, y0, x1, y1]; const c = Math.cos(r), s = Math.sin(r);
  return bbOf([[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => [ox + (x - ox) * c - (y - oy) * s, oy + (x - ox) * s + (y - oy) * c])); };
// 手写字：rate 字/秒（正文 14–16，标题 7.5）；fam 字体（默认宋体）、wt 字重、rot 绕起笔点旋转（弧度）
WB.text = (str, x, y, size, o = {}) => {
  const { col = INK, rate = 15, align = 'left', until = null, fam = FONT, wt = '', rot = 0 } = o;
  const chars = [...str], d = o.dur ?? chars.length / rate, g = mctx();
  const ws = chars.map(ch => { g.font = WB.cf(ch, size, fam, wt); return g.measureText(ch).width; }), w = ws.reduce((a, b) => a + b, 0), x0 = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
  const s = { kind: 'text', str, chars, ws, w, x: x0, y, size, col, fam, wt, rot, t0: o.t0 ?? WB.cur, until, bb: rotBB(x0 - 12, y - size * 1.05, x0 + w + 12, y + size * 0.35, x0, y, rot), handed: true, el: o.el };
  if (o.camOk) s.camOk = true;
  s.t1 = s.t0 + d; WB.S.push(s); WB.texts.push(str); if (o.t0 == null) WB.cur += d + 0.04; return s;
};
// 强调词：默认笔快写出来、写完那一刻＝o.at；stamp:true 改为 0.34s 放大回落整词弹出（不带笔）；slam:true 改为 0.17s 砸入（1.55→0.94→1.0，o.at＝砸到底那一刻）
WB.pop = (str, x, y, size, o = {}) => {
  const { col = OR, align = 'center', rot = 0, until = null, fam = FONT, wt = '' } = o;
  if (!o.stamp && !o.slam) {
    const n = [...str].length, dur = o.wdur ?? Math.max(0.22, Math.min(0.6, n / 15));
    const t0 = o.at != null ? o.at - dur : WB.cur;
    const s = WB.text(str, x, y, size, { col, align, dur, t0, until, fam, wt, rot, el: o.el, camOk: o.camOk });
    s.emph = true; if (o.at != null && o.wdur == null) s.slow = Math.max(0.42, Math.min(0.95, n * 0.17));
    if (o.at == null) WB.cur = t0 + dur + 0.04; return s;
  }
  const dur = o.dur ?? (o.slam ? MO.PULSE.slam : 0.34), w = WB.measure(str, size, fam, wt), x0 = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
  const t0 = o.at != null ? o.at - dur * (o.slam ? 0.6 : 0.55) : WB.cur;
  const s = { kind: 'pop', str, x: x0 + w / 2, y, w, size, col, rot, fam, wt, t0, t1: t0 + dur, until, slam: !!o.slam, bb: [x0 - size * 0.3, y - size * 1.3, x0 + w + size * 0.3, y + size * 0.5],
    rb: [x0 - 12, y - size * 1.05, x0 + w + 12, y + size * 0.35], el: o.el };   // bb 含放大过冲（画与裁剪用）；rb 是落定后的字框（给版面读数）
  if (o.camOk) s.camOk = true;
  WB.S.push(s); WB.texts.push(str); if (o.at == null) WB.cur += o.adv ?? 0.1; return s;
};
WB.fill = (pts, col = WASH, dur = 0.25, o = {}) => {
  const path = pts instanceof Path2D ? pts : U.poly(pts);
  const s = { kind: 'fill', path, col, t0: o.t0 ?? WB.cur, t1: (o.t0 ?? WB.cur) + dur, until: o.until ?? null, bb: o.bb || (pts instanceof Path2D ? null : bbOf(pts, 4)), el: o.el };
  if (o.camOk) s.camOk = true;
  WB.S.push(s); return s;
};
WB.fade = (arr, t, dur = 0.3) => arr.forEach(s => { s.fadeAt = t; s.fadeDur = dur; });
// 自定义：{ t0, t1, draw(g, q, t) → 笔尖|null, bb, handed, start(), end(), until, el, textAt(t) → 当前显示的字（给 visibleText）, camOk,
//   bbAt(t) 或 pos(t)＋ext（会动的件，不给 bb 时用，见下「动态包围盒」） }
WB.custom = o => { const s = { kind: 'custom', handed: false, bb: null, until: null, ...o }; if (s.bb == null) dynInit(s); WB.S.push(s); return s; };
// ---------- 动态包围盒（会动的自定义件） ----------
// 件给了 bbAt(t)（t 时刻的世界框 [x0, y0, x1, y1]），或给 pos(t)→[x, y] 加 ext（相对 pos 的 [左, 上, 右, 下] 偏移，框＝[x+ext0, y+ext1, x+ext2, y+ext3]），且没给 bb：
// 位置可能依赖后面章节才排的东西（纵轴重标区间、后一章才定义的位置函数），所以建板期间不求值（s.bb 保持 null：不参与取景、不裁剪）；
// 建板完成（WB.HS 已赋值）后引擎求 [t0, until 或片尾] 每 1/30 s 位置框的并集写进 s.bb 并缓存——渲染裁剪（drawBoard）、elementBoxes、penAt、items、QA 都用它，
// t0 时在画框外、后来才移进画框的件照常画出。建板期间 WB.fit（WB.shot 经它）遇到这类件且 fit 为真时当场求值（不缓存）；位置函数抛错或给出非有限数时
// 明确报错（console.error＋window.__bootErrors，带元素名与原因）并中止建板，不静默跳过。显式给了 bb 的照静态框处理。
const dynInit = s => {
  if (typeof s.bbAt === 'function') { s.dyn = true; s.boxAt = s.bbAt; return; }
  if (typeof s.pos !== 'function') return;
  const e = s.ext;
  if (!(Array.isArray(e) && e.length === 4 && e.every(Number.isFinite))) { console.error(`WB.custom：元素 ${s.el || '(无 el)'} 给了 pos 却没给 ext（相对 pos 的 [左, 上, 右, 下] 偏移，4 个有限数）：${JSON.stringify(e)}`); return; }
  s.dyn = true; s.boxAt = t => { const [x, y] = s.pos(t); return [x + e[0], y + e[1], x + e[2], y + e[3]]; };
};
const dynUnion = s => {
  const tEnd = s.until ?? ((window.TIMING && TIMING.total) || s.t0 + 60); let r = s.boxAt(s.t0).slice();
  for (let tt = s.t0; tt <= tEnd + 1e-9; tt += 1 / 30) { const b = s.boxAt(tt); r = [Math.min(r[0], b[0]), Math.min(r[1], b[1]), Math.max(r[2], b[2]), Math.max(r[3], b[3])]; }
  if (!(r.length === 4 && r.every(Number.isFinite))) throw new Error(`位置框不是 4 个有限数：${JSON.stringify(r)}`);
  return r;
};
const dynFail = (s, err, where) => {
  const msg = `动态包围盒求值失败（${where}）：元素 ${s.el || '(无 el)'}（${s.kind}，t0 ${(+s.t0).toFixed(2)}）：${(err && err.message) || err}。` +
    '位置要等后面章节才定的话，把取景（WB.fit/WB.shot）挪到定义位置的章节之后，或给这个件显式 bb';
  (window.__bootErrors || (window.__bootErrors = [])).push(msg); console.error(msg); return new Error(msg);
};
WB.hatchCircle = (cx, cy, r, o = {}) => {
  const { gap = 22, ang = -0.8, col = OR, w = 4.2, speed = SPEED * 3.2 } = o, ux = Math.cos(ang), uy = Math.sin(ang), nx = -uy, ny = ux;
  const out = []; for (let d = -r + gap * 0.6; d <= r - gap * 0.4; d += gap) { const h = Math.sqrt(r * r - d * d) * 0.9;
    out.push(WB.line([[cx + nx * d - ux * h, cy + ny * d - uy * h], [cx + nx * d + ux * h, cy + ny * d + uy * h]], { col, w, speed, min: 0.022, gap: 0.006, amp: 0.8, until: o.until, el: o.el })); }
  return out;
};
WB.hatchRect = (x, y, w0, h0, o = {}) => {
  const { gap = 20, col = OR, w = 4.2, speed = SPEED * 3.4 } = o, out = [];
  for (let k = gap * 0.5; k < w0 + h0; k += gap) { const a = [x + Math.min(k, w0), y + Math.max(0, k - w0)], b = [x + Math.max(0, k - h0), y + Math.min(k, h0)];
    out.push(WB.line([[a[0], a[1]], [b[0], b[1]]], { col, w, speed, min: 0.016, gap: 0.004, amp: 0.6, smooth: false, until: o.until, el: o.el })); }
  return out;
};
WB.lead = (a, b, t0, dur = 0.55, o = {}) => {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1, bend = o.bend ?? -0.18 * L;
  const pts = o.pts || WB.quad(a, [mx - dy / L * bend, my + dx / L * bend], b, 30);   // o.pts：自定路径（绕开板上已有的东西）
  const s1 = WB.line(pts, { col: o.col || OR, w: 8, dash: [2, 12], t0, dur: dur * 0.85, amp: 1.0, nofit: true, el: o.el });
  s1.lead = true;   // 引线＝笔领相机，唯一允许在运镜中画的笔画
  const e = pts[pts.length - 1], p = pts[pts.length - 4], an = Math.atan2(e[1] - p[1], e[0] - p[0]), h = 26;
  WB.line([[e[0] - Math.cos(an - 0.5) * h, e[1] - Math.sin(an - 0.5) * h], e, [e[0] - Math.cos(an + 0.5) * h, e[1] - Math.sin(an + 0.5) * h]], { col: o.col || OR, w: 6, smooth: false, t0: t0 + dur * 0.87, dur: dur * 0.13, nofit: true, el: o.el }).lead = true;
  return s1;
};
WB.arrow = (a, b, o = {}) => {
  const { bend = 0, col = INK, w = LW, head = 30, dash = null, speed = SPEED * 1.3 } = o;
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
  const c = [mx - dy / L * bend, my + dx / L * bend], pts = WB.quad(a, c, b, 30);
  const s1 = WB.line(pts, { col, w, dash, speed, until: o.until, amp: o.amp ?? 1.4, t0: o.t0, dur: o.dur, el: o.el });
  if (o.t0 != null) WB.cur = Math.max(WB.cur, s1.t1 + 0.02);
  const e = pts[pts.length - 1], p = pts[pts.length - 4], an = Math.atan2(e[1] - p[1], e[0] - p[0]);
  const s2 = WB.line([[e[0] - Math.cos(an - 0.5) * head, e[1] - Math.sin(an - 0.5) * head], e, [e[0] - Math.cos(an + 0.5) * head, e[1] - Math.sin(an + 0.5) * head]], { col, w, smooth: false, speed: speed * 0.8, until: o.until, el: o.el, t0: o.t0 != null ? s1.t1 + 0.01 : undefined });
  return [s1, s2];
};
WB.sk = (strokes, x, y, o = {}) => {
  const s = o.s || 1, r = o.rot || 0, out = [];
  for (const k of strokes) {
    if (k.fillPts) { out.push(WB.fill(WB.xf(k.fillPts, x, y, s, r), k.fillCol || WASH, 0.2, { until: o.until, el: o.el })); continue; }
    const pts = WB.xf(k.p, x, y, s, r);
    out.push(WB.line(pts, { w: (k.w || 1) * (o.w || LW), col: k.o ? OR : (o.col || INK), speed: (o.speed || SPEED) * (k.fast ? 2 : 1), smooth: k.smooth !== false, dash: k.dash, until: o.until, gap: o.gap ?? 0.01, min: o.min ?? 0.025, amp: k.amp ?? 1.2, el: o.el }));
  }
  return out;
};
WB.prep = (strokes, lw = LW) => strokes.map(k => k.fillPts ? { fill: U.poly(k.fillPts), col: k.fillCol || WASH } :
  ({ pts: k.smooth === false ? k.p : DG.hand(k.p, { amp: (k.amp ?? 1.1) * WB.STYLE.jitter, seed: (k.p.length * 13 + Math.round(k.p[0][0] * 7)) | 0, per: 8 }), w: (k.w || 1) * lw, col: k.o ? OR : INK, dash: k.dash }));
WB.drawPrep = (g, P, x, y, s = 1, r = 0, alpha = 1) => {
  g.save(); g.translate(x, y); if (r) g.rotate(r); if (s !== 1) g.scale(s, s); g.globalAlpha *= alpha; g.lineJoin = 'round'; g.lineCap = 'round';
  for (const k of P) {
    if (k.fill) { g.fillStyle = k.col; g.fill(k.fill); continue; }
    g.strokeStyle = k.col; g.lineWidth = k.w / s; if (k.dash) g.setLineDash(k.dash.map(v => v / s));
    g.beginPath(); k.pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.stroke(); if (k.dash) g.setLineDash([]);
  }
  g.restore();
};
WB.drawOn = (P, x, y, o = {}) => {
  const s = o.s || 1, r = o.rot || 0, out = [];
  for (const k of P) {
    if (k.fill) { out.push(WB.custom({ t0: WB.cur, t1: WB.cur + 0.2, until: o.until, bb: o.bb || null, draw(g, q) { g.save(); g.globalAlpha = q; g.translate(x, y); if (r) g.rotate(r); g.scale(s, s); g.fillStyle = k.col; g.fill(k.fill); g.restore(); return null; } })); continue; }
    const pts = WB.xf(k.pts, x, y, s, r);
    out.push(WB.line(pts, { w: k.w * (o.lws || 1), col: k.col, dash: k.dash, smooth: false, speed: o.speed || SPEED, until: o.until, gap: 0.01, min: 0.025 }));
  }
  return out;
};

// ---------- 常用件 ----------
// 便签卡：手画框 0.35s → 卡面铺开 0.25s（压在框和字下面）→ 胶带啪地贴上（0.17s 砸入）；标题带一条淡红面。返回 {face, frame, tape, band, t1}
// 画法包设了 WB.STYLE.card 时整张卡换成一个自定义件：t0 起 o.dur（缺省 0.57 s）内由 card(g, s, q, t) 画（s 带 x/y/w/h/o），四个返回键都指向它
WB.card = (x, y, w, h, o = {}) => {
  const t0 = o.t0 ?? WB.cur, el = o.el;
  if (WB.STYLE.card) { const bb = [x, y, x + w, y + h];
    const s = WB.custom({ t0, t1: t0 + (o.dur ?? 0.57), el, bb, fit: true, until: o.until ?? null, x, y, w, h, o, draw(g, q, t) { return WB.STYLE.card(g, this, q, t); } });
    return { face: s, frame: s, tape: s, band: s, t1: s.t1, bb }; }
  const face = WB.fill(U.poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]), CARD, 0.25, { t0: t0 + 0.22, el, bb: [x, y, x + w, y + h] });
  const band = WB.fill(U.poly([[x + 6, y + 6], [x + w - 6, y + 6], [x + w - 6, y + (o.band ?? 92)], [x + 6, y + (o.band ?? 92)]]), T.card_band, 0.25, { t0: t0 + 0.3, el, bb: [x, y, x + w, y + 92] });
  const frame = WB.line(WB.rect(x, y, w, h), { t0, dur: 0.35, w: 4.2, col: SOFT, amp: 1.3, el });
  const tx = x + w / 2, ty = y - 4, ta = t0 + 0.4;
  const tape = WB.custom({ t0: ta, t1: ta + 0.17, el, bb: [tx - 70, ty - 20, tx + 70, ty + 20], draw(g, q, t) {
    const k = MO.slamK(q); g.save(); g.translate(tx, ty); g.rotate(-0.035); g.scale(k, k); g.globalAlpha *= clamp(q * 3);
    g.fillStyle = TAPE; g.fillRect(-62, -15, 124, 30); g.strokeStyle = 'rgba(120,90,40,.35)'; g.setLineDash([4, 4]); g.lineWidth = 1.5; g.beginPath(); g.moveTo(-62, -15); g.lineTo(-62, 15); g.moveTo(62, -15); g.lineTo(62, 15); g.stroke(); g.restore(); return null; } });
  return { face, frame, tape, band, t1: ta + 0.17, bb: [x, y, x + w, y + h] };
};
// 胶囊小标：圆角框＋字，整块 0.17 s 砸入（o.at＝砸到底那一刻）。o = {at, size=40, fam=BODY, wt='600', col=INK（字）, line（框，默认同字色）,
// face（底色，默认卡面色；null 不铺）, padX=22, h, lw=4, el}。返回自定义笔画（带 w、h，供排版）
WB.pill = (str, x, y, o = {}) => {
  const size = o.size ?? 40, fam = o.fam ?? BODY, wt = o.wt ?? '600', col = o.col ?? INK, padX = o.padX ?? 22, h = o.h ?? Math.round(size * 1.6), lw = o.lw ?? 4;
  const w = WB.measure(str, size, fam, wt) + padX * 2, dur = MO.PULSE.slam, t0 = (o.at ?? WB.cur) - dur * 0.6;
  const s = WB.custom({ t0, t1: t0 + dur, el: o.el, size, w, h, bb: [x - 6, y - 6, x + w + 6, y + h + 6], textAt: () => str, draw(g, q) {
    const k = MO.slamK(q); g.globalAlpha *= clamp(q * 4); g.translate(x + w / 2, y + h / 2); g.scale(k, k);
    g.beginPath(); g.roundRect(-w / 2, -h / 2, w, h, h / 2);
    if (o.face !== null) { g.fillStyle = o.face ?? CARD; g.fill(); }
    g.strokeStyle = o.line ?? col; g.lineWidth = lw; g.stroke();
    g.font = `${wt} ${size}px ${fam}`; g.fillStyle = col; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(str, 0, size * 0.04); return null; } });
  WB.texts.push(str); return s;
};
// ---------- 小草图（口播里没有新词的句子，配一个与句意相关的笔动；全是笔画，不是字） ----------
// WB.sketch(paths, o)：paths = [[点列, {smooth, dash, w, col, amp}]…] 一笔接一笔画（按笔画长度分摊 o.dur，缺省按 900 px/s），返回 {s: 笔画[], t0, t1}。
// 其余几个是常用小图：勾、叉、页（折角＋几行线）、一叠纸、放大镜、波浪下划线、锁、划掉的眼睛、小钟、小票、印章（砸入）。
WB.sketch = (paths, o = {}) => {
  const lens = paths.map(([p]) => { const c = DG.cum(p); return c[c.length - 1] || 1; }), tot = lens.reduce((a, b) => a + b, 0);
  const dur = o.dur ?? Math.max(0.4, tot / 900), t0 = o.t0 ?? WB.cur; let t = t0; const out = [];
  paths.forEach(([pts, q = {}], i) => { const d = Math.max(0.05, (dur - 0.02 * (paths.length - 1)) * lens[i] / tot);
    out.push(WB.line(pts, { t0: t, dur: d, w: q.w ?? o.w ?? 5, col: q.col ?? o.col ?? INK, smooth: q.smooth ?? o.smooth ?? true, amp: q.amp ?? o.amp ?? 0.9, dash: q.dash ?? null, el: o.el, nofit: o.nofit }));
    t += d + 0.02; });
  return { s: out, t0, t1: t - 0.02 };
};
const sk = WB.sketch, arc = (cx, cy, rx, ry, a0, a1, n = 24) => DG.arcPts(cx, cy, rx, ry, a0, a1, n);
WB.tick = (x, y, z, o = {}) => sk([[[[x - z * 0.5, y - z * 0.02], [x - z * 0.12, y + z * 0.38], [x + z * 0.55, y - z * 0.5]], { smooth: false }]], { dur: 0.5, w: 6, ...o });
WB.cross = (x, y, z, o = {}) => sk([[[[x - z / 2, y - z / 2], [x + z / 2, y + z / 2]], { smooth: false }], [[[x + z / 2, y - z / 2], [x - z / 2, y + z / 2]], { smooth: false }]], { dur: 0.6, w: 6, col: OR, ...o });
WB.page = (x, y, w, h, o = {}) => { const f = Math.min(w, h) * 0.28, n = o.lines ?? 3, P = [[[[x, y], [x + w - f, y], [x + w, y + f], [x + w, y + h], [x, y + h], [x, y + 2]], { smooth: false }],
    [[[x + w - f, y], [x + w - f, y + f], [x + w, y + f]], { smooth: false, w: 3 }]];
  for (let i = 0; i < n; i++) { const yy = y + f + (h - f) * (i + 0.8) / (n + 0.6); P.push([[[x + w * 0.16, yy], [x + w * (i === n - 1 ? 0.6 : 0.84), yy]], { w: 3, smooth: false }]); }
  return sk(P, { dur: 0.9, w: 4, ...o }); };
WB.stackIcon = (x, y, w, h, n, o = {}) => { const P = []; for (let i = n - 1; i >= 0; i--) { const dx = i * 9, dy = -i * 9; P.push([[[x + dx, y + dy + 6], [x + dx, y + dy], [x + w + dx, y + dy], [x + w + dx, y + h + dy], [x + w + dx - 6, y + h + dy]], { smooth: false }]); }
  P.push([WB.rect(x, y, w, h), { smooth: false }]); return sk(P, { dur: 0.25 + 0.12 * n, w: 4, ...o }); };
WB.magnifier = (x, y, r, o = {}) => sk([[arc(x, y, r, r, -2.2, -2.2 + Math.PI * 2.05, 36)], [[[x + r * 0.72, y + r * 0.72], [x + r * 1.7, y + r * 1.7]], { smooth: false, w: 8 }]], { dur: 0.8, w: 5, ...o });
WB.wavy = (x0, x1, y, o = {}) => { const P = [], n = Math.max(6, Math.round((x1 - x0) / 22)); for (let i = 0; i <= n; i++) P.push([x0 + (x1 - x0) * i / n, y + (i % 2 ? 7 : -7)]); return sk([[P]], { dur: 0.9, w: 5, col: OR, ...o }); };
WB.lockIcon = (x, y, w, o = {}) => sk([[arc(x + w / 2, y, w * 0.32, w * 0.42, Math.PI, Math.PI * 2, 16)], [WB.rect(x, y, w, w * 0.75), { smooth: false }], [[[x + w / 2, y + w * 0.3], [x + w / 2, y + w * 0.5]], { smooth: false, w: 6 }]], { dur: 0.8, w: 5, ...o });
WB.eyeOff = (x, y, w, o = {}) => sk([[arc(x, y + w * 0.32, w * 0.62, w * 0.42, -2.45, -0.69, 14)], [arc(x, y - w * 0.32, w * 0.62, w * 0.42, 0.69, 2.45, 14)], [arc(x, y, w * 0.13, w * 0.13, 0, Math.PI * 2.05, 14)],
    [[[x - w * 0.5, y + w * 0.38], [x + w * 0.5, y - w * 0.38]], { smooth: false, col: OR, w: 6 }]], { dur: 0.9, w: 4, ...o });
WB.clockIcon = (x, y, r, o = {}) => sk([[arc(x, y, r, r, -Math.PI / 2, Math.PI * 1.55, 30)], [[[x, y], [x, y - r * 0.62]], { smooth: false }], [[[x, y], [x + r * 0.45, y + r * 0.2]], { smooth: false }]], { dur: 0.8, w: 5, ...o });
WB.ticket = (x, y, w, h, o = {}) => { const n = h * 0.22; return sk([[[[x, y], [x + w, y], [x + w, y + h / 2 - n]].concat(arc(x + w, y + h / 2, n, n, -Math.PI / 2, -Math.PI * 1.5, 8)).concat([[x + w, y + h], [x, y + h], [x, y + h / 2 + n]])
    .concat(arc(x, y + h / 2, n, n, Math.PI / 2, -Math.PI / 2, 8)).concat([[x, y]]), { smooth: false }], [[[x + w * 0.7, y + 6], [x + w * 0.7, y + h - 6]], { dash: [6, 8], w: 3, smooth: false }]], { dur: 0.8, w: 4, ...o }); };
// 红印章：圆框＋中心一个字（字取自口播原文），0.17 s 砸入；返回自定义笔画
WB.stamp = (ch, x, y, r, o = {}) => { const dur = MO.PULSE.slam, t0 = (o.at ?? WB.cur) - dur * 0.6;
  const s = WB.custom({ t0, t1: t0 + dur, el: o.el, size: r * 1.1, bb: [x - r - 6, y - r - 6, x + r + 6, y + r + 6], textAt: () => ch, draw(g, q) {
    const k = MO.slamK(q); g.globalAlpha *= clamp(q * 4) * 0.92; g.translate(x, y); g.rotate(-0.18); g.scale(k, k); g.strokeStyle = OR; g.lineWidth = 5;
    g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.stroke(); g.lineWidth = 2; g.beginPath(); g.arc(0, 0, r - 8, 0, Math.PI * 2); g.stroke();
    g.font = `700 ${Math.round(r * 1.05)}px ${FONT}`; g.fillStyle = OR; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(ch, 0, r * 0.06); return null; } });
  WB.texts.push(ch); return s; };
// 图片（画法包的贴纸、插画）：src 须登记在 project.json 的 assets（相对 engine/<片名>/；建工程与 make_timing 写进 EXTRA_ASSETS，引擎启动时载入 IMG），
// 没登记或没载入直接抛错（引擎拒绝启动）。等比放进 (x, y, w, h) 居中。o = {reveal: 'fade'（0.4 s）|'wipe'（自左向右 0.6 s）|'slam'（0.17 s 砸入，jump 'stamp'），
// at（揭开完成时刻）或 t0、dur、outline（沿透明边缘的白描边像素）、outline_col、shadow（true 或 {col, blur, dx, dy}）、credit（来源一行小字，图下右对齐）、credit_size（34）、
// fx/fy（推近焦点，图内 0–1）、z（推近终了倍数，>1 才推，只推图框里面）、zdur（推近秒数，缺省 6；经 WB.ambientT＝装饰动作，QA 锁相机时冻结）、el、until}。返回自定义笔画
const silCache = new Map();
const silhouette = (im, key, dw, dh, ol, col) => { const ck = `${key}|${dw.toFixed(1)}|${dh.toFixed(1)}|${ol}|${col}`; if (silCache.has(ck)) return silCache.get(ck);
  const cv = document.createElement('canvas'); cv.width = Math.ceil(dw + 2 * ol); cv.height = Math.ceil(dh + 2 * ol); const g = cv.getContext('2d'), n = Math.max(12, Math.round(ol * 2));
  for (let i = 0; i <= n; i++) { const a = i / n * Math.PI * 2, r = i === n ? 0 : ol; g.drawImage(im, ol + Math.cos(a) * r, ol + Math.sin(a) * r, dw, dh); }
  g.globalCompositeOperation = 'source-in'; g.fillStyle = col; g.fillRect(0, 0, cv.width, cv.height); silCache.set(ck, cv); return cv; };
WB.image = (src, x, y, w, h, o = {}) => {
  const I = window.IMG || {}, fd = String(window.SCENE_DIR || '').split('/')[0], key = I[src] ? src : I[`${fd}/${src}`] ? `${fd}/${src}` : null;
  if (!key) throw new Error(`WB.image：图片「${src}」没在 project.json 的 assets 里登记（或没载入），引擎拒绝启动`);
  const rev = o.reveal || 'fade';
  if (!['fade', 'wipe', 'slam'].includes(rev)) throw new Error(`WB.image：reveal 只能是 fade、wipe、slam：${rev}`);
  const im = I[key], k = Math.min(w / im.width, h / im.height), dw = im.width * k, dh = im.height * k, dx = x + (w - dw) / 2, dy = y + (h - dh) / 2;
  const dur = o.dur ?? (rev === 'slam' ? MO.PULSE.slam : rev === 'wipe' ? 0.6 : 0.4), t0 = o.at != null ? o.at - dur : (o.t0 ?? WB.cur), t1 = t0 + dur;
  const ol = o.outline || 0, sh = o.shadow === true ? {} : (o.shadow || null), cs = o.credit_size ?? 34, cw = o.credit ? WB.measure(o.credit, cs, BODY) : 0;
  const cbb = o.credit ? [dx + dw - cw - 6, dy + dh + ol + 12, dx + dw + 6, dy + dh + ol + 18 + cs * 1.1] : null;
  const bb = [dx - ol - 24, dy - ol - 24, dx + dw + ol + 24, (cbb ? cbb[3] : dy + dh + ol) + 24];
  const s = WB.custom({ t0, t1, el: o.el, until: o.until ?? null, bb, fit: true, size: cs, img: key, jump: rev === 'slam' ? 'stamp' : undefined,
    textAt: o.credit ? (t => t >= t0 ? { text: o.credit, bb: cbb } : null) : undefined,
    draw(g, q, t) {
      const e = rev === 'slam' ? MO.slamK(q) : 1, cx = dx + dw / 2, cy = dy + dh / 2;
      g.globalAlpha *= rev === 'fade' ? MO.sineInOut(q) : rev === 'slam' ? clamp(q * 4) : 1;
      if (e !== 1) { g.translate(cx, cy); g.scale(e, e); g.translate(-cx, -cy); }
      if (rev === 'wipe') { g.beginPath(); g.rect(bb[0], bb[1], (bb[2] - bb[0]) * MO.sineInOut(q), bb[3] - bb[1]); g.clip(); }
      if (sh) { g.save(); g.shadowColor = sh.col || 'rgba(0,0,0,.22)'; g.shadowBlur = sh.blur ?? 24; g.shadowOffsetX = sh.dx ?? 0; g.shadowOffsetY = sh.dy ?? 10; }
      if (ol) g.drawImage(silhouette(im, key, dw, dh, ol, o.outline_col || '#ffffff'), dx - ol, dy - ol);
      else if (sh) g.drawImage(im, dx, dy, dw, dh);
      if (sh) g.restore();
      const z = o.z > 1 ? 1 + (o.z - 1) * MO.sineInOut(clamp((WB.ambientT(t) - t1) / (o.zdur ?? 6))) : 1;
      if (z !== 1) { const px = dx + dw * (o.fx ?? 0.5), py = dy + dh * (o.fy ?? 0.5); g.save(); g.beginPath(); g.rect(dx, dy, dw, dh); g.clip(); g.translate(px, py); g.scale(z, z); g.translate(-px, -py); }
      if (z !== 1 || ol || !sh) g.drawImage(im, dx, dy, dw, dh);
      if (z !== 1) g.restore();
      if (o.credit) { g.font = `${cs}px ${BODY}`; g.fillStyle = DIM; g.textAlign = 'right'; g.textBaseline = 'alphabetic'; g.fillText(o.credit, dx + dw, cbb[1] + cs * 0.92); }
      return null; } });
  if (o.at == null && o.t0 == null) WB.cur += dur + 0.04;
  return s;
};
// 扁平图标（画法包共用：学术图解的圆形节点、贴纸科普的贴纸……）：WB.icon(g, name, cx, cy, size, o) 在 g 上以 (cx, cy) 为中心、边长 size 的方格里画一个图标，
// 纯绘制、不压进 WB.S（在 WB.custom 的 draw 里调）。图标按 100×100、中心为原点设计；o = {ink（描边，缺省 WB.INK）, fill（平涂，缺省 WB.CARD）,
// accent（点睛色，缺省 WB.OR）, lw（描边宽，世界像素、与 WB.line 的 w 同口径，不随 size 缩放，缺省 2.5）}。名字不在 WB.ICONS 里直接抛错。
const ICON = {
  person(g, S) { g.beginPath(); g.arc(0, -18, 14, 0, Math.PI * 2); S.fs();
    g.beginPath(); g.moveTo(-28, 36); g.lineTo(-28, 20); g.quadraticCurveTo(-28, 4, -12, 4); g.lineTo(12, 4); g.quadraticCurveTo(28, 4, 28, 20); g.lineTo(28, 36); g.closePath(); S.fs(); },
  doc(g, S) { g.beginPath(); g.moveTo(-26, -38); g.lineTo(12, -38); g.lineTo(28, -22); g.lineTo(28, 38); g.lineTo(-26, 38); g.closePath(); S.fs();
    g.beginPath(); g.moveTo(12, -38); g.lineTo(12, -22); g.lineTo(28, -22); S.st();
    g.beginPath(); for (const [y, x1] of [[-6, 16], [8, 16], [22, 4]]) { g.moveTo(-14, y); g.lineTo(x1, y); } S.st(); },
  gear(g, S) { const n = 8, h = Math.PI / n; g.beginPath();
    for (let i = 0; i < n; i++) { const a = i * 2 * h; [[27, a - 0.62 * h], [37, a - 0.36 * h], [37, a + 0.36 * h], [27, a + 0.62 * h]].forEach(([r, b], j) => (i || j ? g.lineTo : g.moveTo).call(g, r * Math.cos(b), r * Math.sin(b))); }
    g.closePath(); S.fs(); g.beginPath(); g.arc(0, 0, 10, 0, Math.PI * 2); S.st(); },
  coins(g, S) { for (const y of [22, 6, -10]) { g.beginPath(); g.moveTo(-28, y); g.lineTo(-28, y + 9); g.ellipse(0, y + 9, 28, 9, 0, Math.PI, 0, true); g.lineTo(28, y); g.ellipse(0, y, 28, 9, 0, 0, Math.PI, true); g.closePath(); S.fs();
    g.beginPath(); g.ellipse(0, y, 28, 9, 0, 0, Math.PI); S.st(); } },
  percent(g, S) { g.beginPath(); g.arc(-17, -17, 11, 0, Math.PI * 2); S.fs(); g.beginPath(); g.arc(17, 17, 11, 0, Math.PI * 2); S.fs();
    g.beginPath(); g.moveTo(26, -30); g.lineTo(-26, 30); S.st(); },
  growth(g, S) { for (const [x, hh] of [[-30, 18], [-10, 32], [10, 48]]) { g.beginPath(); g.rect(x, 36 - hh, 16, hh); S.fs(); }
    g.beginPath(); g.moveTo(-38, 36); g.lineTo(38, 36); S.st();
    g.beginPath(); g.moveTo(-34, -6); g.lineTo(-14, -20); g.lineTo(0, -12); g.lineTo(30, -36); S.st(S.acc); S.head(30, -36, Math.atan2(-24, 30), 12, S.acc); },
  clock(g, S) { g.beginPath(); g.arc(0, 0, 36, 0, Math.PI * 2); S.fs();
    g.beginPath(); for (let k = 0; k < 4; k++) { const a = k * Math.PI / 2; g.moveTo(29 * Math.cos(a), 29 * Math.sin(a)); g.lineTo(34 * Math.cos(a), 34 * Math.sin(a)); } g.moveTo(0, 0); g.lineTo(0, -22); g.moveTo(0, 0); g.lineTo(15, 9); S.st(); },
  check(g, S) { g.beginPath(); g.arc(0, 0, 36, 0, Math.PI * 2); g.fillStyle = S.acc; g.fill();
    g.beginPath(); g.moveTo(-17, 1); g.lineTo(-5, 14); g.lineTo(19, -13); g.save(); g.lineWidth *= 2.2; S.st(S.fill); g.restore(); },
  flag(g, S) { g.beginPath(); g.moveTo(-36, 40); g.lineTo(-8, 40); g.moveTo(-22, 40); g.lineTo(-22, -38); S.st();
    g.beginPath(); g.moveTo(-22, -36); g.lineTo(30, -36); g.lineTo(18, -21); g.lineTo(30, -6); g.lineTo(-22, -6); g.closePath(); S.fs(); },
  chain(g, S) { for (const [dx, dy] of [[-12, 12], [12, -12]]) { g.save(); g.translate(dx, dy); g.rotate(-Math.PI / 4); g.beginPath(); g.roundRect(-25, -11, 50, 22, 11); g.restore(); g.save(); g.lineWidth *= 1.5; S.st(); g.restore(); } },
};
WB.ICONS = Object.keys(ICON);
WB.icon = (g, name, cx, cy, size, o = {}) => {
  const f = ICON[name]; if (!f) throw new Error(`WB.icon：没有图标「${name}」（现有：${WB.ICONS.join('、')}）`);
  const k = size / 100, ink = o.ink ?? INK, fill = o.fill ?? CARD, acc = o.accent ?? OR;
  g.save(); g.translate(cx, cy); g.scale(k, k); g.lineWidth = (o.lw ?? 2.5) / k; g.lineJoin = 'round'; g.lineCap = 'round';
  const S = { fill, acc, fs() { g.fillStyle = fill; g.fill(); g.strokeStyle = ink; g.stroke(); }, st(col = ink) { g.strokeStyle = col; g.stroke(); },
    head(x, y, an, len, col) { g.beginPath(); g.moveTo(x, y); g.lineTo(x - Math.cos(an - 0.45) * len, y - Math.sin(an - 0.45) * len); g.lineTo(x - Math.cos(an + 0.45) * len, y - Math.sin(an + 0.45) * len); g.closePath(); g.fillStyle = col; g.fill(); } };
  f(g, S); g.restore();
};
// Python 风格格式串 "{:.1f}%" / "首验 {:.0f} 对"
WB.fmt = (f, v) => f.replace(/\{:\.(\d+)f\}/g, (m, d) => (+v).toFixed(+d));
// 数字滚动：o = {from, to, fmt, land（落定时刻，全片秒）, dur, col, size, fam, wt, align, el, lead（前缀，用正文字体）}
// count-up 用 expoOut；land 之后停在终值；起动前不画；等宽数字（TY.tabular）防抖。textAt 给 visibleText 报当前显示值。
WB.count = (x, y, o) => {
  const { from = 0, to, fmt = '{:.0f}', land, dur = 1.0, col = OR, size = 56, fam = NUMF, wt = '700', align = 'left', el, slamIn = false } = o;
  const t0 = land - dur, font = `${wt} ${size}px ${fam}`;
  const g = mctx(); g.font = font; const wMax = Math.max(g.measureText(WB.fmt(fmt, from)).width, g.measureText(WB.fmt(fmt, to)).width) + 30;
  const x0 = align === 'right' ? x - wMax : align === 'center' ? x - wMax / 2 : x;
  const val = t => TY.count(t, t0, dur, from, to, MO.expoOut);
  const s = WB.custom({ t0, t1: land, el, size, bb: [x0 - 10, y - size * 1.05, x0 + wMax + 10, y + size * 0.3], draw(gg, q, t) {
    gg.font = font; gg.fillStyle = col; gg.textBaseline = 'alphabetic'; gg.globalAlpha *= clamp((t - t0) / (slamIn ? 0.04 : 0.12));
    if (slamIn) { const k = MO.slamK((t - t0) / MO.PULSE.slam), cx = x0 + wMax / 2, cy = y - size * 0.35; gg.translate(cx, cy); gg.scale(k, k); gg.translate(-cx, -cy); }   // 起滚那一刻整个数字砸进来
    TY.tabular(gg, WB.fmt(fmt, val(t)), x, y, { align }); return null; },
    textAt: t => t < t0 ? null : WB.fmt(fmt, val(t)) });
  s.land = land; WB.texts.push(WB.fmt(fmt, to)); return s;
};
// 按 x 推进长出的曲线（财经图表语法：时间匀速流过，陡处自然画得快）。pts 须 x 递增；phases = [[t0, t1, f0, f1], …]（f 为 x 范围的比例）；
// 线头红点只在长的时候和长完之后到 headUntil 前画。返回自定义笔画（el 用 o.el）。
WB.grow = (pts, phases, o = {}) => {
  const { col = INK, w = 7, dash = null, head = OR, headUntil = 1e9, el } = o;
  const P = DG.hand(pts, { amp: (o.amp ?? 1.6) * WB.STYLE.jitter, seed: o.seed ?? 3, per: 6 }), xa = P[0][0], xb = P[P.length - 1][0];
  const fAt = t => { let f = 0; for (const [a, b, f0, f1] of phases) { if (t < a) break; f = lerp(f0, f1, (o.ease || MO.smooth)(clamp((t - a) / (b - a)))); } return f; };
  const t0 = phases[0][0], t1 = phases[phases.length - 1][1];
  const s = WB.custom({ t0, t1, el, bb: bbOf(P, w + 14), fAt, pts: P, act: t => phases.some(([a, b]) => t >= a && t < b), draw(g, q, t) {
    const f = fAt(t); if (f <= 0) return null; const xe = lerp(xa, xb, f), vis = [P[0]];
    for (let i = 1; i < P.length; i++) { if (P[i][0] <= xe) vis.push(P[i]); else { const a = P[i - 1], b = P[i], u = (xe - a[0]) / (b[0] - a[0] || 1); vis.push([xe, lerp(a[1], b[1], u)]); break; } }
    g.strokeStyle = col; g.lineWidth = w; g.lineJoin = 'round'; g.lineCap = 'round'; if (dash) g.setLineDash(dash);
    g.beginPath(); vis.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.stroke(); g.setLineDash([]);
    const hp = vis[vis.length - 1];
    if (head && t < headUntil) { g.fillStyle = head; g.beginPath(); g.arc(hp[0], hp[1], 13, 0, Math.PI * 2); g.fill(); }
    return null; } });
  s.headAt = t => { const f = fAt(t), xe = lerp(xa, xb, f); return [xe, CH.yAt(P, xe)]; };
  return s;
};
// 手画红圈：把一个世界矩形圈起来（椭圆，首尾略交叉）；dur 0.4–0.6s
WB.ring = (bb, o = {}) => {
  const cx = (bb[0] + bb[2]) / 2, cy = (bb[1] + bb[3]) / 2, rx = o.rx ?? (bb[2] - bb[0]) / 2 + (o.pad ?? 26), ry = o.ry ?? (bb[3] - bb[1]) / 2 + (o.pad ?? 26) * 0.8;
  // o.box：圆角框（6 次超椭圆），包住整块矩形而不压到四角；默认椭圆
  const pts = o.box ? (() => { const a0 = o.a0 ?? -2.4, tn = o.turns ?? 1.05, q = []; for (let k = 0; k <= 96; k++) { const th = a0 + tn * 2 * Math.PI * k / 96, c = Math.cos(th), s = Math.sin(th);
      q.push([cx + rx * Math.sign(c) * Math.pow(Math.abs(c), 1 / 3), cy + ry * Math.sign(s) * Math.pow(Math.abs(s), 1 / 3)]); } return q; })()
    : WB.ell(cx, cy, rx, ry, o.a0 ?? -2.4, o.turns ?? 1.08, o.rot ?? -0.03, 72);
  return WB.line(pts, { col: o.col || OR, w: o.w ?? 5.5, t0: o.t0, dur: o.dur ?? 0.5, amp: 2.2, el: o.el, ease: MO.cubicInOut });
};
// 划掉一串字：一条略斜的手写横线压过字身（0.4–0.5s）
WB.strike = (s, o = {}) => { const y = s.y - s.size * 0.32, x0 = s.x - 8, x1 = s.x + s.w + 8;
  return WB.line([[x0, y + 4], [(x0 + x1) / 2, y - 2], [x1, y - 5]], { col: o.col || OR, w: o.w ?? 6, t0: o.t0, dur: o.dur ?? 0.45, amp: 1.2, el: o.el }); };
// 下划线：字下方一条手写线（红）
WB.under = (s, o = {}) => { const y = s.y + s.size * 0.2, x0 = (o.x0 ?? s.x) - 4, x1 = (o.x1 ?? s.x + s.w) + 4;
  return WB.line([[x0, y], [(x0 + x1) / 2, y + 3], [x1, y - 1]], { col: o.col || OR, w: o.w ?? 6, t0: o.t0, dur: o.dur ?? 0.45, amp: 1.4, el: o.el }); };

// ---------- 相机 ----------
// 关键帧全片秒。WB.move(t0,t1,x,y,z) = 从 t0 时的位置移到 (x,y,z)，t1 到位。本片 creep 默认 0：停留时相机不动。
WB.cam0 = (x, y, z) => { WB.K.length = 0; WB.K.push({ t: 0, x, y, z }); };
WB.move = (t0, t1, x, y, z, o = {}) => {
  const K = WB.K, last = K[K.length - 1];
  if (t0 < last.t - 1e-4) { console.warn(`WB.move: ${t0.toFixed(2)} 早于上一个相机键 ${last.t.toFixed(2)}，顺延`); t0 = last.t; }
  if (t0 > last.t + 1e-3) { const hold = t0 - last.t, cr = o.creep ?? 0; K.push({ t: t0, x: last.x, y: last.y, z: last.z * (1 + Math.min(0.035, cr * hold)), ease: MO.sineInOut }); }
  K.push({ t: Math.max(t1, t0 + 0.05), x, y, z, ease: o.ease || MO.sineInOut });
  if (o.whip) WB.WHIP.push([t0, Math.max(t1, t0 + 0.05)]);
};
WB.camAt = t => CAM.at(WB.K, t);
WB.fit = (a, b, o = {}) => {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; const ext = r => { x0 = Math.min(x0, r[0]); y0 = Math.min(y0, r[1]); x1 = Math.max(x1, r[2]); y1 = Math.max(y1, r[3]); };
  for (const s of WB.S) { if (s.t0 < a || s.t0 >= b || s.nofit || s.kind === 'fill') continue; if (s.kind === 'custom' && !s.fit) continue;
    let bb = s.bb;
    if (!bb && s.dyn) { try { bb = dynUnion(s); } catch (e) { throw dynFail(s, e, `WB.fit [${a.toFixed(2)}, ${b.toFixed(2)}) 取景`); } }   // 建板期间：当场求值、不缓存
    if (bb) ext(bb); }
  (o.add || []).forEach(ext);
  if (x0 > x1) { console.warn(`WB.fit: [${a.toFixed(2)}, ${b.toFixed(2)}) 里没有笔画`); const k = WB.K[WB.K.length - 1]; return [k.x, k.y, k.z]; }
  return WB.frame([x0, y0, x1, y1], o);
};
// 取景一个世界矩形：上下落在屏幕 70–870（字幕带让开）、左右各留 96；返回 [x, y, z, bb]
WB.frame = (bb, o = {}) => {
  const [x0, y0, x1, y1] = bb, pad = o.pad ?? 50, w = x1 - x0 + 2 * pad, h = y1 - y0 + 2 * pad;
  const z = U.clamp(Math.min((W - 192) / w, 800 / h), o.zmin ?? 0.12, o.zmax ?? 1.25);
  return [(x0 + x1) / 2 + (o.dx || 0), (y0 + y1) / 2 + (540 - (o.sy ?? 470)) / z, z, [x0, y0, x1, y1]];
};
WB.declip = (cam, a, b, o = {}) => {
  let [x, y, z, cb] = cam; const z0 = z, M = 30, ok = xx => !cb || (cb[0] >= xx - W / 2 / z + 20 / z && cb[2] <= xx + W / 2 / z - 20 / z);
  for (let it = 0; it < 8; it++) {
    const hw = W / 2 / z, hh = H / 2 / z, v = [x - hw, y - hh, x + hw, y + hh]; let moved = false;
    for (const s of WB.S) {
      if ((s.kind !== 'text' && s.kind !== 'pop') || s.t0 >= b || (s.t0 >= a && s.t0 < b) || !s.bb || s.fadeAt != null) continue;
      const bb = s.bb, inter = !(bb[2] < v[0] || bb[0] > v[2] || bb[3] < v[1] || bb[1] > v[3]); if (!inter) continue;
      const inside = bb[0] >= v[0] + M / z && bb[2] <= v[2] - M / z && bb[1] >= v[1] && bb[3] <= v[3]; if (inside) continue;
      const cx = (bb[0] + bb[2]) / 2, maxS = (o.maxShift ?? 420) / z;
      if (cx < x && bb[2] > v[0] && bb[2] - v[0] + M / z < maxS && ok(x + bb[2] - v[0] + M / z)) { x += bb[2] - v[0] + M / z; moved = true; break; }
      if (cx >= x && bb[0] < v[2] && v[2] - bb[0] + M / z < maxS && ok(x - (v[2] - bb[0] + M / z))) { x -= v[2] - bb[0] + M / z; moved = true; break; }
      if (cb) { const nb = [Math.min(cb[0], bb[0]), cb[1], Math.max(cb[2], bb[2]), cb[3]], z2 = Math.min(z, (W - 192) / (nb[2] - nb[0] + 100));
        if (z2 >= z0 * 0.8 && (nb[0] !== cb[0] || nb[2] !== cb[2])) { cb = nb; x = (nb[0] + nb[2]) / 2; y = y + 0; z = z2; moved = true; break; } }
    }
    if (!moved) break;
  }
  return [x, y, z, cb];
};
WB.shot = (t, dur, a, b, o = {}) => { let c = WB.fit(a, b, o); if (o.declip !== false) c = WB.declip(c, a, b, o); WB.move(t, t + dur, c[0], c[1], c[2], o); return c; };
// 取景一个世界矩形并移过去（本片多用它：版式先定，取景按版式算）；默认再过一遍 declip：t 之前写上板的字在画框边上被切成半截的，
// 把画框横推开让它整个出画，推不开就整个框进来（o.declip=false 关掉；o.cam=[x,y,z] 直接给相机，只做 declip）
WB.shotRect = (t, dur, bb, o = {}) => { let c = o.cam ? [...o.cam, bb] : WB.frame(bb, o); if (o.declip !== false) c = WB.declip(c, t, t, o); WB.move(t, t + dur, c[0], c[1], c[2], o); return c; };
// 远行：途中先拉远再推近（RSA 板上平移），中点速度不停；落点同样过 declip（字不半截）。o.out＝中点缩放相对两端较小者的倍数（默认 0.72）；o.whip 加甩镜模糊
WB.travel = (t, dur, bb, o = {}) => { const c = WB.declip(o.cam ? [...o.cam, bb] : WB.frame(bb, o), t, t, o), a = WB.camAt(t), zm = Math.min(a.z, c[2]) * (o.out ?? 0.72);
  WB.move(t, t + dur / 2, (a.x + c[0]) / 2, (a.y + c[1]) / 2, zm, { ease: p => 2 * MO.sineInOut(p / 2), whip: o.whip });
  WB.move(t + dur / 2, t + dur, c[0], c[1], c[2], { ease: p => 2 * MO.sineInOut(0.5 + p / 2) - 1, whip: o.whip }); return c; };
WB.view = cam => { const hw = W / 2 / cam.z, hh = H / 2 / cam.z; return [cam.x - hw, cam.y - hh, cam.x + hw, cam.y + hh]; };
const camApply = (c, k) => CAM.apply(c, k), toScr = (cam, x, y) => CAM.toScreen(cam, x, y);   // 相机换算用原版 CAM（画布 1920×1080）
WB.toScr = toScr;

// ---------- 屏幕层特效 ----------
WB.fx = (t0, t1, draw) => WB.FX.push({ t0, t1, draw });

// ---------- 章节 ----------
WB.chapter = (id, fn) => { WB.CH[id] = fn; };
WB.build = () => {
  if (WB.built) return; WB.built = true;
  for (const e of ERAS) { const fn = WB.CH[e.id]; if (fn) { const n0 = WB.S.length; fn(e.id); WB.S.slice(n0).forEach(s => (s.ch = e.id)); } }
  WB.K.sort((a, b) => a.t - b.t);
  const hs = WB.S.filter(s => s.handed && (s.kind === 'line' || s.kind === 'text' || s.kind === 'custom'));
  for (const s of hs) if (s.slow && s.t1 - s.t0 < s.slow) { const t0o = s.t0; let lb = s.t1 - s.slow;
    for (const o of hs) if (o !== s && o.t0 < t0o + 1e-6 && o.t1 > lb - 0.03) lb = o.t1 + 0.03;
    s.t0 = Math.min(t0o, lb); }
  // 一支笔同时只能画一笔：后起的那笔（线或普通字）顺延到前一笔写完；顺延不超过 0.35s，自定义动画和重点词不动
  hs.sort((a, b) => a.t0 - b.t0);
  for (let pass = 0; pass < 6; pass++) { let moved = false;
    for (let i = 1; i < hs.length; i++) { const p = hs[i - 1], b = hs[i]; const sh = p.t1 + 0.02 - b.t0;
      if (sh > 0.03 && sh <= 0.35 && b.kind !== 'custom' && !b.emph && !b.pin) { b.t0 += sh; b.t1 += sh; moved = true; }
      else if (sh > 0.03 && b.emph && b.t1 - (p.t1 + 0.02) >= 0.1) { b.t0 = p.t1 + 0.02; moved = true; } }
    hs.sort((a, b) => a.t0 - b.t0); if (!moved) break; }
  // 相机运动期间不起笔：起笔落在运镜 [m0, m1+SETTLE) 里的线、字、弹入、铺面一律顺延到相机停稳 SETTLE 秒之后（引线、camOk 笔画除外——camOk 是否真在慢推里由 qa 的 cam_pen 量）；顺延记进 WB.SHIFT
  WB.MOVES = WB.moves(); WB.SHIFT = [];
  for (let pass = 0; pass < 4; pass++) { let moved = false;
    for (const s of WB.S) { if (s.lead || s.camOk || !['line', 'text', 'pop', 'fill'].includes(s.kind)) continue;
      const m = WB.MOVES.find(([a, b]) => s.t0 > a - 1e-3 && s.t0 < b + WB.SETTLE - 1e-3); if (!m) continue;
      const sh = m[1] + WB.SETTLE - s.t0; WB.SHIFT.push({ el: s.el || null, str: s.str || null, from: +s.t0.toFixed(3), by: +sh.toFixed(3) }); s.t0 += sh; s.t1 += sh; moved = true; }
    if (!moved) break; }
  WB.HS = hs;
  // 建板完成：会动的自定义件求全程位置框的并集当包围盒（缓存）；求不出就明确报错、中止建板
  for (const s of WB.S) if (s.dyn && s.bb == null) { try { s.bb = dynUnion(s); } catch (e) { throw dynFail(s, e, '建板完成后求全程并集'); } }
};
// 相机运动区间（全片秒，相邻两个关键帧位置或缩放不同即在动）：[[t0, t1]…]，首尾相接的并成一段
WB.moves = () => { const K = WB.K, out = []; for (let i = 0; i + 1 < K.length; i++) { const a = K[i], b = K[i + 1];
    if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) < 0.5 && Math.abs(a.z - b.z) < 1e-4) continue;
    if (out.length && Math.abs(out[out.length - 1][1] - a.t) < 1e-3) out[out.length - 1][1] = b.t; else out.push([a.t, b.t]); }
  return out; };
WB.report = () => ERAS.map(e => { const ss = WB.S.filter(s => s.ch === e.id); const T = TIMING.seg[e.id];
  return [e.id, +T.t0.toFixed(2), +(T.t0 + T.dur).toFixed(2), ss.length ? +Math.min(...ss.map(s => s.t0)).toFixed(2) : null, ss.length ? +Math.max(...ss.map(s => s.t1)).toFixed(2) : null, ss.length]; });

// ---------- 画 ----------
// 画法字（WB.STYLE.text 'type'/'fade'）第 i 个字在 t 的不透明度：'type' 第 i 个字从 t0＋(dur−0.12)·i/(n−1) 起 0.12 s 内 0→1（末字正好在 t1 出齐）；'fade' 整串 t0 起 0.3 s
const textA = (s, i, t) => WB.STYLE.text === 'fade' ? clamp((t - s.t0) / 0.3)
  : clamp((t - s.t0 - (s.chars.length > 1 ? Math.max(0, s.t1 - s.t0 - 0.12) * i / (s.chars.length - 1) : 0)) / 0.12);
const drawOne = (g, s, t) => {
  if (t < s.t0 || (s.until != null && t >= s.until)) return null;
  const q = s.t1 > s.t0 ? clamp((t - s.t0) / (s.t1 - s.t0)) : 1;
  if (s.kind === 'line') {
    g.strokeStyle = s.col; g.lineWidth = s.w; if (s.dash) g.setLineDash(s.dash);
    const d = s.len * (s.ease || MO.sineInOut)(q), tip = WB.STYLE.stroke ? WB.STYLE.stroke(g, s, d, t) : DG.drawPartial(g, s.pts, s.cum, d);   // 画法的线笔画钩子
    if (s.dash) g.setLineDash([]); return tip;
  }
  if (s.kind === 'text') {
    g.save(); g.fillStyle = s.col; g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    if (s.rot) { g.translate(s.x, s.y); g.rotate(s.rot); g.translate(-s.x, -s.y); }
    const n = s.chars.length, k = Math.min(n, q * n), done = Math.floor(k); let x = s.x, tip = null;
    const sd = (s.x * 7 + s.y * 3) | 0, jit = i => [U.hash(sd, i) - 0.5, U.hash(sd + 1, i) - 0.5];
    let bump = 1; if (s.emph && t > s.t1) { const u = (t - s.t1) / 0.28; if (u < 1) bump = 1 + 0.07 * Math.sin(u * Math.PI); }
    if (bump !== 1) { const cx = s.x + s.w / 2, cy = s.y - s.size * 0.35; g.translate(cx, cy); g.scale(bump, bump); g.translate(-cx, -cy); }
    if (WB.STYLE.text === 'type' || WB.STYLE.text === 'fade') {   // 画法字：'type' 每字 0.12 s 淡入、上浮 8 px→0；'fade' 整串 0.3 s 淡入；都不抖、不带笔尖
      for (let i = 0; i < n; i++) { const a = textA(s, i, t); if (a <= 0) break;
        g.save(); g.globalAlpha *= a; g.font = WB.cf(s.chars[i], s.size, s.fam, s.wt); g.fillText(s.chars[i], x, s.y + (WB.STYLE.text === 'type' ? 8 * (1 - a) * (1 - a) : 0)); g.restore(); x += s.ws[i]; }
      g.restore(); return null;
    }
    const J = WB.STYLE.jitter;   // 手写字的抖动×画法 jitter（缺省 1）
    const put = (i, xx) => { const [a, b] = jit(i); g.save(); g.font = WB.cf(s.chars[i], s.size, s.fam, s.wt); g.translate(xx + s.ws[i] / 2, s.y + b * s.size * 0.04 * J); g.rotate(a * 0.05 * J); g.fillText(s.chars[i], -s.ws[i] / 2, 0); g.restore(); };
    for (let i = 0; i < n; i++) {
      if (i < done) put(i, x);
      else if (i === done && k < n) {
        const gl = WB.STYLE.glyph ? WB.STYLE.glyph(s, i, k - done) : (so => so ? WB.soAt(so, k - done) : null)(WB.so(s.chars[i], s.size, s.ws[i], s.fam, s.wt));   // 画法的写字遮罩钩子
        if (gl) { const [m, tp] = gl; g.save(); g.translate(x, s.y); g.clip(m); g.translate(-x, -s.y); put(i, x); g.restore(); tip = [x + tp[0], s.y + tp[1]]; }
        else { const zz = DG.zigzag(x - 2, s.y - s.size * 0.95, s.ws[i] + 4, s.size * 1.15, 3), cum = DG.cum(zz), d = cum[cum.length - 1] * (k - done);
          g.save(); g.clip(DG.revealMask(zz, cum, d, s.size * 0.62)); put(i, x); g.restore(); tip = DG.pointAt(zz, cum, d); }
      } else break;
      x += s.ws[i];
    }
    g.restore();
    return tip;
  }
  if (s.kind === 'pop') {
    const e = s.slam ? MO.slamK(q) : MO.backOut(q, 2.4);
    g.save(); g.font = WB.cf('', s.size, s.fam, s.wt); g.fillStyle = s.col; g.textBaseline = 'alphabetic'; g.textAlign = 'center'; g.globalAlpha *= clamp(q * 4);
    g.translate(s.x, s.y - s.size * 0.35); if (s.rot) g.rotate(s.rot); g.scale(e, e); g.fillText(s.str, 0, s.size * 0.35); g.restore(); return null;
  }
  if (s.kind === 'fill') { g.save(); g.globalAlpha *= q; g.fillStyle = s.col; g.fill(s.path); g.restore(); return null; }
  if (s.kind === 'custom') { g.save(); const r = s.draw(g, q, t); g.restore(); return r; }
  return null;
};
// 纸：底色 → 纸纹（屏幕空间，只跟平移不跟缩放，推近时不放大成灰斑）→ 36px 点阵（世界坐标，跟板走）→ 版面光（左上微亮、右下微暖）
const grain = () => PAINT.cached('b_grain', 512, 512, g => { const r = U.rng(11), im = g.createImageData(512, 512);
  for (let i = 0; i < im.data.length; i += 4) { const v = r(); im.data[i] = T.paper.grain[0]; im.data[i + 1] = T.paper.grain[1]; im.data[i + 2] = T.paper.grain[2]; im.data[i + 3] = v < 0.55 ? 0 : Math.round((v - 0.55) / 0.45 * 16); }
  g.putImageData(im, 0, 0); });
// 渐变终点＝同色全透明（缺省主题下与原值 rgba(255,255,255,0)、rgba(190,160,110,0) 相同）
const transp = col => { const g = mctx(); g.fillStyle = '#000'; g.fillStyle = col; const s = g.fillStyle, m = s.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (m) return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},0)`; const r = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/); return r ? `rgba(${r[1]},${r[2]},${r[3]},0)` : 'rgba(0,0,0,0)'; };
const dotTile = () => PAINT.cached('b_dots', 36, 36, g => { g.fillStyle = T.paper.dots; g.beginPath(); g.arc(18, 18, 1.5, 0, Math.PI * 2); g.fill(); });
function drawBoard(c, t, cam) {
  WB.drawT = t;   // 本遍绘制时刻（糊影时每一遍各不相同）：画法的 stroke 钩子、自定义件里的纯绘制函数从这里取，别再借 ground 记
  if (WB.STYLE.ground) { c.save(); WB.STYLE.ground(c, t, cam); c.restore(); }   // 画法包自己的底面（要跟板走就按 cam 换算到世界坐标）
  else {
  c.fillStyle = BOARD; c.fillRect(0, 0, W, H);
  c.save(); const ox = -(((cam.x * cam.z) % 512) + 512) % 512, oy = -(((cam.y * cam.z) % 512) + 512) % 512;
  c.translate(ox, oy); c.fillStyle = c.createPattern(grain(), 'repeat'); c.fillRect(0, 0, W + 512, H + 512); c.restore();
  const dz = clamp((cam.z - 0.22) / 0.3);
  if (dz > 0) { const pat = c.createPattern(dotTile(), 'repeat'); pat.setTransform(new DOMMatrix([cam.z, 0, 0, cam.z, W / 2 - cam.x * cam.z, H / 2 - cam.y * cam.z]));
    c.save(); c.globalAlpha = dz; c.fillStyle = pat; c.fillRect(0, 0, W, H); c.restore(); }
  const g1 = c.createRadialGradient(W * 0.2, 0, 0, W * 0.2, 0, 1200); g1.addColorStop(0, T.paper.light); g1.addColorStop(1, transp(T.paper.light)); c.fillStyle = g1; c.fillRect(0, 0, W, H);
  const g2 = c.createRadialGradient(W, H, 0, W, H, 900); g2.addColorStop(0, T.paper.warm); g2.addColorStop(1, transp(T.paper.warm)); c.fillStyle = g2; c.fillRect(0, 0, W, H);
  }
  const [vx0, vy0, vx1, vy1] = WB.view(cam);
  c.save(); camApply(c, cam); c.lineJoin = 'round'; c.lineCap = 'round';
  let tip = null, col = null;
  for (const s of WB.S) {
    if (t < s.t0) continue;
    const b = s.bb; if (b && (b[2] < vx0 || b[0] > vx1 || b[3] < vy0 || b[1] > vy1)) continue;
    const a = dimAt(s, t); if (a < 1) { c.save(); c.globalAlpha *= a; }
    let p;
    if (s.fadeAt != null && t >= s.fadeAt) {
      const k = (t - s.fadeAt) / (s.fadeDur || 0.3), b = s.bb;
      if (!b) { if (k < 1) { c.save(); c.globalAlpha *= 1 - k; p = drawOne(c, s, t); c.restore(); } }
      else { const x = b[0] - 30 + (b[2] - b[0] + 60) * MO.sineInOut(clamp(k)), sl = (b[3] - b[1]) * 0.25;
        if (k < 1) { c.save(); c.beginPath(); c.moveTo(x + sl, b[1] - 60); c.lineTo(b[2] + 1e4, b[1] - 60); c.lineTo(b[2] + 1e4, b[3] + 60); c.lineTo(x - sl, b[3] + 60); c.closePath(); c.clip(); p = drawOne(c, s, t); c.restore(); } } }
    else p = drawOne(c, s, t);
    if (a < 1) c.restore();
    if (p && t < s.t1 && s.handed) { tip = p; col = s.col; }
  }
  c.restore();
  return { tip, col };
}
WB.draw = (c, t) => {
  if (!WB.built) WB.build();
  WB.lastT = t;
  const lock = WB.lockcam != null, camT = lock ? WB.lockcam : t;
  const cam = WB.camAt(camT);
  const whip = !lock && WB.WHIP.some(([a, b]) => t > a && t < b);
  const cp = lock ? cam : WB.camAt(camT - 1 / 30), vw = WB.view(cam), pts = [[cam.x, cam.y], [vw[0], vw[1]], [vw[2], vw[3]]];
  const disp = pts.map(p => { const a = toScr(cam, p[0], p[1]), b = toScr(cp, p[0], p[1]); return [a[0] - b[0], a[1] - b[1]]; }), dpx = Math.max(...disp.map(d => Math.hypot(d[0], d[1])));
  const buf = () => WB._buf || (WB._buf = (() => { const b = document.createElement('canvas'); b.width = W; b.height = H; return b; })());
  let res;
  if (dpx < 24 || WB.STYLE.motionBlur === false) res = drawBoard(c, t, cam);   // 画法关了糊影：运镜也只画一遍
  else if (whip) {
    const b = buf(), g = b.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); res = drawBoard(g, t, cam);
    const [vx, vy] = disp[0], L = 0.5, m = Math.min(6, Math.max(2, Math.ceil(Math.log2(dpx * L / 2))));
    const b2 = WB._buf2 || (WB._buf2 = (() => { const x = document.createElement('canvas'); x.width = W; x.height = H; return x; })());
    let A = b, B = b2; for (let k = 0; k < m; k++) { const f = L / Math.pow(2, k + 1), gB = B.getContext('2d'); gB.setTransform(1, 0, 0, 1, 0, 0); gB.globalAlpha = 1; gB.fillStyle = BOARD; gB.fillRect(0, 0, W, H); gB.drawImage(A, 0, 0); gB.globalAlpha = 0.5; gB.drawImage(A, vx * f, vy * f); gB.globalAlpha = 1; [A, B] = [B, A]; }
    c.drawImage(A, 0, 0);
  } else {
    const b = buf(), g = b.getContext('2d'), N = Math.min(cam.z < 0.5 ? 6 : 8, Math.ceil(dpx / 10)), sh = Math.min(0.6, 4 * (N - 1) / dpx);
    for (let i = 0; i < N; i++) { const ti = t - (sh / 30) * i / (N - 1); g.setTransform(1, 0, 0, 1, 0, 0); const r = drawBoard(g, ti, WB.camAt(ti)); if (!i) res = r; c.save(); c.globalAlpha = 1 / (i + 1); c.drawImage(b, 0, 0); c.restore(); }
  }
  for (const f of WB.FX) if (t >= f.t0 && t < f.t1) { c.save(); f.draw(c, t, cam); c.restore(); }
  if (WB.PEN && res.tip) { const p = toScr(cam, res.tip[0], res.tip[1]); DG.pen(c, p[0], p[1], res.col || INK, 0); }
  if (WB.STYLE.overlay) { c.save(); WB.STYLE.overlay(c, t, cam); c.restore(); }   // 画法屏幕层（字幕在它之上，由 GLOBAL_OVERLAY 画）
};

// ---------- 给 QA / 验收的读数 ----------
// 当前（默认最近一次画的 t）板上可见的字：写到一半的给已写出的前缀；数字滚动给当前显示值。坐标为画布像素（1920×1080）。
// sid＝该笔画在 WB.S 里的下标（元素身份：qa 的 layout 按它归并，同一串字写在两处是两条笔画、分别计）。
WB.items = (t = WB.lastT) => {
  const cam = WB.camAt(WB.lockcam != null ? WB.lockcam : t), out = [];
  for (let sid = 0; sid < WB.S.length; sid++) { const s = WB.S[sid];
    if (t < s.t0 || (s.until != null && t >= s.until)) continue;
    if (s.fadeAt != null && t >= s.fadeAt + (s.fadeDur || 0.3)) continue;
    let text = null, px = null, bb = s.bb;
    if (s.kind === 'text' && (WB.STYLE.text === 'type' || WB.STYLE.text === 'fade')) { text = s.chars.filter((c, i) => textA(s, i, t) > 0).join(''); px = s.size; }
    else if (s.kind === 'text') { const q = s.t1 > s.t0 ? clamp((t - s.t0) / (s.t1 - s.t0)) : 1; text = s.chars.slice(0, Math.ceil(q * s.chars.length - 1e-9)).join(''); px = s.size; }
    else if (s.kind === 'pop') { text = s.str; px = s.size; bb = s.rb || s.bb; }
    else if (s.kind === 'custom' && s.textAt) { const r = s.textAt(t); if (r && typeof r === 'object') { text = r.text; bb = r.bb || s.bb; } else text = r; px = s.size; }   // textAt 可返回 {text, bb}（会移动的元素给当前框）
    if (!text || !String(text).trim()) continue;
    const a = toScr(cam, bb[0], bb[1]), b = toScr(cam, bb[2], bb[3]), on = !(b[0] < 0 || a[0] > W || b[1] < 0 || a[1] > H);
    out.push({ text: String(text), el: s.el || null, sid, x0: a[0], y0: a[1], x1: b[0], y1: b[1], px: px * cam.z, onScreen: on, t0: s.t0, t1: s.t1, rot: s.rot || 0 });
  }
  return out;
};
window.visibleItems = t => WB.items(t ?? WB.lastT).filter(i => i.onScreen);
window.visibleText = t => window.visibleItems(t).map(i => i.text).join('\n');
// 各具名元素（timeline events[].el）的屏幕包围盒（该元素全部笔画的全幅外框，经 t 时刻相机——设了 lockcam 就用锁定相机——换算，画布像素）
window.elementBoxes = t => {
  t = t ?? WB.lastT; const cam = WB.camAt(WB.lockcam != null ? WB.lockcam : t), m = {};
  for (const s of WB.S) { if (!s.el || !s.bb) continue; const r = m[s.el] || (m[s.el] = [1e9, 1e9, -1e9, -1e9]);
    r[0] = Math.min(r[0], s.bb[0]); r[1] = Math.min(r[1], s.bb[1]); r[2] = Math.max(r[2], s.bb[2]); r[3] = Math.max(r[3], s.bb[3]); }
  for (const k in m) { const r = m[k], a = toScr(cam, r[0], r[1]), b = toScr(cam, r[2], r[3]); m[k] = [a[0], a[1], b[0], b[1]]; }
  return m;
};
// timeline 事件的实际起点（build 之后；起点取登记的笔画 t0）：[{beat, el, do, start, dur}]
window.eventTimes = () => { if (!WB.built) WB.build(); return WB.EV.map(e => Object.assign({ beat: e.beat, el: e.el, do: e.do, start: +evStart(e.ref).toFixed(4), dur: e.dur },
  e.ref && e.ref.land != null ? { land: +e.ref.land.toFixed(4) } : {})); };   // count 另报实际落定时刻
// 笔在动：t 时刻这一笔正在画（线、字、弹入、铺面、擦掉；自定义件看 act(t)，没给就按 [t0, t1)），且笔画框落在画面里、字幕带上沿以上。
// 给 QA 量「口播期间不许连续 ≥1.5 s 没有笔动」（相机动、字幕变都不算笔动）。返回正在动的笔画名单（el 或类型）。
const penOn = (s, t) => {
  if (s.fadeAt != null && t >= s.fadeAt) return t < s.fadeAt + (s.fadeDur || 0.3);
  if (s.nopen || t < s.t0) return false;
  if (s.kind === 'text' && WB.STYLE.text === 'fade') return t < Math.min(s.t1, s.t0 + 0.3);   // 整串淡入：0.3 s 后画面就不变了
  return s.kind === 'custom' && s.act ? s.act(t) : t < s.t1;
};
window.penAt = t => { if (!WB.built) WB.build(); const cam = WB.camAt(t), v = WB.view(cam), yb = cam.y + (BAND - H / 2) / cam.z;
  return WB.S.filter(s => s.bb && penOn(s, t) && !(s.bb[2] < v[0] || s.bb[0] > v[2] || s.bb[3] < v[1] || s.bb[1] > yb)).map(s => s.el || s.kind); };
window.cameraAt = t => WB.camAt(t);

// ---------- 字幕层（底部 200px 带） ----------
const TRIM = /[，。；：、—\s]+$/;
WB.captionAt = t => {
  for (const e of ERAS) { const s = TIMING.seg[e.id]; if (t < s.t0 || t >= s.t0 + s.dur) continue;
    const lt = t - s.t0; for (const c of s.captions) if (lt >= c.start && lt < c.end) return c.text; }
  return null;
};
let previewed = false;
window.GLOBAL_OVERLAY = (ctx, t) => {
  if (PREVIEW_T != null && !previewed && t === 0) { previewed = true; window.renderFrame(PREVIEW_T); const sc = document.getElementById('scrub'), tt = document.getElementById('tt'); if (sc) sc.value = PREVIEW_T; if (tt) tt.textContent = PREVIEW_T.toFixed(3); return; }
  if (T.caption && T.caption.show === false) return;   // project.json theme.caption.show=false：画面不出口播字幕（现场演示版：讲者自己说）
  const raw = WB.captionAt(t); if (!raw) return;
  const text = raw.trim().replace(TRIM, ''); if (!text) return;
  ctx.save();
  const size = T.caption.size, font = `${size}px ${BODY}`; ctx.font = font;
  const tw = ctx.measureText(text).width, lines = tw > T.caption.max_chars * size ? TY.wrap(ctx, text, Math.ceil(tw / 2) + size, font) : [text];
  const lh = size * 1.42, bw = Math.max(...lines.map(l => ctx.measureText(l).width)) + 64, bh = lh * lines.length + 26, cy = H - T.caption.band / 2 - 2;   // 带中线上移 2 px（1080p、带高 200 时＝978）
  if (WB.STYLE.caption) { ctx.save(); WB.STYLE.caption(ctx, text, { x: W / 2 - bw / 2, y: cy - bh / 2, w: bw, h: bh, r: 10, lines, size }); ctx.restore(); }   // 画法的字幕底条
  else { ctx.fillStyle = T.caption.bg; ctx.strokeStyle = LINE; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect(W / 2 - bw / 2, cy - bh / 2, bw, bh, 10); ctx.fill(); ctx.stroke(); }
  ctx.fillStyle = INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  lines.forEach((l, i) => ctx.fillText(l, W / 2, cy - (lines.length - 1) * lh / 2 + i * lh + 1));
  ctx.restore();
};

// ---------- 启动：字体就绪并核过才建板、才置 __ready ----------
const fontsMissing = () => {
  const g = mctx(), probe = 'AIxyz0123①≠测试', miss = [];
  for (const name of T.required_fonts) {   // 字体探测清单＝主题 required_fonts
    g.font = `64px ${fam(name)}, monospace`; const a = g.measureText(probe).width; g.font = '64px monospace'; const b = g.measureText(probe).width;
    if (Math.abs(a - b) < 0.5) miss.push(name);
  }
  return miss;
};
// 画法钩子核对（style.js 已加载之后才核；非法即 console.error，渲染器记为页面错误、非零退出）
const styleBad = () => { const S = WB.STYLE, bad = [];
  if (!['hand', 'type', 'fade'].includes(S.text)) bad.push(`text=${JSON.stringify(S.text)}（只能 hand、type、fade）`);
  if (!(typeof S.jitter === 'number' && isFinite(S.jitter) && S.jitter >= 0)) bad.push(`jitter=${JSON.stringify(S.jitter)}`);
  for (const k of ['ground', 'overlay', 'card', 'stroke', 'glyph', 'caption']) if (S[k] != null && typeof S[k] !== 'function') bad.push(`${k} 不是函数`);
  if (typeof S.motionBlur !== 'boolean') bad.push(`motionBlur=${JSON.stringify(S.motionBlur)}（只能 true、false）`);
  return bad; };
WB.scene = {
  init() {
    if (WB._inited) return; WB._inited = true; WB.HANDI = null;
    { const bad = styleBad(); if (bad.length) console.error('WB.STYLE 画法钩子非法（wb/style.js）：' + bad.join('；')); }
    const ps = [`700 64px ${FONT}`, `64px ${FONT}`, `64px ${BODY}`, `600 64px ${BODY}`, `700 64px ${NUMF}`].map(f => document.fonts.load(f, '测0'));
    const ready = Promise.all(ps).then(() => { const miss = fontsMissing(); if (miss.length) throw new Error('系统字体不在（canvas 会静默回退成别的字体）：' + miss.join('、')); WB.build(); });
    const prep = window.prepare; window.prepare = async t => { await ready; return prep(t); };
  },
  draw(c, lt, t) { WB.draw(c, t); },
};
})();
