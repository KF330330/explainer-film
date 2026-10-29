// 通用件（explainer-film 1.3.0，1.3.1 加九件）：new_project.py 复制到 engine/<片名>/wb/parts.js，经 project.json 的 libs 键排在 SCENE_LIBS 最后加载
// （在 wb/common.js、wb/style.js 之后、各段场景之前）。来源：一支早期样片场景里的三个件与两个场景小工具，
// 改成通用签名（样片专属的写法改成参数）。签名、一例用法与经验见 skill 的 references/parts.md。
// 六件：WB.coinDraw（画一枚硬币）、WB.stack（一摞任意物件）、WB.walker（走动的小人）、WB.docCard（原件卡）、WB.trip（远行运镜）、WB.retire（撤笔画）。
// 1.3.1 九件（取自另一支样片的各段场景，写死的版式、时刻、元素名改成参数）：WB.popIn（弹入）、WB.shape（手画形状）、
//   WB.machineDraw／WB.machine（方盒机器）、WB.cardItem（卡片一摞的画法）、WB.compareTable（两列对照表）、WB.sealBox（信封抽屉锁）、WB.calendar（日历）、
//   WB.stepLoop（步骤环箭头）；WB.stack 另挂 geom。
// 1.3.2 一件：WB.roll（里程表式滚数，取代样片里的 L.count；整段夹在「WB.roll 起／止」两行标记之间，可原样搬进旧工程的场景文件）。
// 1.3.3 两件：WB.panTo（平移换页）、WB.review（拉远回顾换页）（取自一支讲解片的换页写法；整段夹在「WB.panTo／WB.review 起／止」两行标记之间，同样可原样搬）。
// 规矩：只在 WB 上挂新名字，不给 common.js 已定义的引擎函数重新赋值；颜色只走 WB.C.*，字体只走 WB.BODY／WB.FONT 主题令牌；不用无种子的随机数（一律 U.rng 带种子）；
// 装饰动作（眨眼、呼吸）走 WB.ambientT；会动的件给 bbAt(t) 或 pos(t)＋ext。整份包在一个函数里，不往全局放顶层名字。
(() => {
const clamp = v => U.clamp(v);
const inv = v => Math.acos(1 - 2 * clamp(v)) / Math.PI;                                                  // MO.sineInOut 的反函数

// ================= WB.coinDraw：画一枚硬币 =================
// WB.coinDraw(g, cx, yt, rx, ry, h, lw, acc)：侧面一圈＋顶面前沿；顶面圆心 (cx, yt)，半轴 rx／ry，厚 h，线宽 lw；
// acc＝最上一枚：顶面描一道强调色细边、再压一圈浅色压纹。纯绘制，不压进 WB.S（在 WB.custom 的 draw 里调；也是 WB.stack 的缺省 item）。
WB.coinDraw = (g, cx, yt, rx, ry, h, lw, acc) => {
  const C = WB.C;
  g.lineJoin = 'round'; g.lineCap = 'round';
  g.beginPath(); g.moveTo(cx - rx, yt); g.lineTo(cx - rx, yt + h); g.ellipse(cx, yt + h, rx, ry, 0, Math.PI, 0, true);
  g.lineTo(cx + rx, yt); g.ellipse(cx, yt, rx, ry, 0, 0, Math.PI, true); g.closePath();
  g.fillStyle = C.card; g.fill(); g.strokeStyle = C.ink; g.lineWidth = lw; g.stroke();
  if (h > lw * 2.5) { g.strokeStyle = C.line; g.lineWidth = Math.max(1.5, lw * 0.45); g.beginPath();   // 侧面滚花：前半圈几道短竖线
    for (const a of [0.35, 0.95, 1.57, 2.19, 2.79]) { const xx = cx + rx * Math.cos(a), yy = ry * Math.sin(a); g.moveTo(xx, yt + yy + lw); g.lineTo(xx, yt + h + yy - lw); } g.stroke(); }
  g.strokeStyle = C.ink; g.lineWidth = lw * 0.8; g.beginPath(); g.ellipse(cx, yt, rx, ry, 0, 0, Math.PI); g.stroke();
  if (acc) { g.strokeStyle = C.line; g.lineWidth = Math.max(1.5, lw * 0.5); g.beginPath(); g.ellipse(cx, yt, rx * 0.66, ry * 0.66, 0, 0, Math.PI * 2); g.stroke();
    g.strokeStyle = C.accent; g.lineWidth = Math.max(2, lw * 0.75); g.beginPath(); g.ellipse(cx, yt, rx - lw * 0.6, ry - lw * 0.45, 0, 0, Math.PI * 2); g.stroke(); }
};

// ================= WB.stack：一摞任意物件 =================
// WB.stack({x, y, n0, n1, t0, t1, el, w=150, h=18, item=WB.coinDraw}) → 自定义件。底部中心 (x, y)；t0 前不画；t0 起已有 n0 件（0.12 s 淡入），
// 件数在 t0–t1 从 n0 缓动（sineInOut）到 n1，取整、逐件落下（第 k 件在数到 k+1 那一刻落地，落地前约 0.2 s 从高处加速落下）；
// 每件由 item(g, cx, yt, rx, ry, h, lw, acc) 画（顶面中心 (cx, yt)、半宽 rx＝w/2、顶面半高 ry≈0.16·w、厚 h、线宽 lw、acc＝已落地的最上一件）：
// 缺省一摞硬币；换成卡片、砖块之类的画法就是「一摞任意物件」。一件厚 h：硬币 h 18 时 15 枚约与 s 94 的小人等高、45 枚约三倍高。
// bbAt(t) 按当时画出的件算（正在落的那件按它的实际位置算）；act(t) 只覆盖 t0–t1；jump:'coins'（qa jumps 认作有意跳变）。
// 另挂 s.topAt(t)（当前摞顶 y）、s.topN(n)（n 件时的摞顶 y），排数字用：数字落定那一刻摞上正好 n 件（「每摞两步」，见 parts.md）。
WB.stack = ({ x, y, n0, n1, t0, t1, el, w = 150, h = 18, item = WB.coinDraw }) => {
  const rx = w / 2, ry = Math.round(w * 0.16), lw = Math.max(3, w * 0.026), D = h * 3 + 40, dn = n1 - n0, span = Math.max(1e-6, t1 - t0);
  const land = k => dn <= 0 ? t0 : t0 + span * inv((k + 1 - n0) / dn);                            // 第 k 件（k ≥ n0）落地时刻
  const fall = dn > 0 ? Math.min(0.22, Math.max(0.12, span / dn * 1.4)) : 0;
  const nAt = t => t < t0 ? n0 : t >= t1 ? n1 : n0 + (dn > 0 ? Math.ceil(dn * MO.sineInOut((t - t0) / span) - 1e-9) : 0);
  const topN = n => y - n * h - ry;
  const items = t => {                                                                             // t 时画出的件：[落下余高, 不透明度]，自下而上
    const st = [];
    for (let k = 0; k < n1; k++) {
      let off = 0, a = 1;
      if (k < n0) a = clamp((t - t0) / 0.12);
      else { const tl = land(k), ts = Math.max(t0, tl - fall); if (t < ts) break; if (t < tl) { const u = (t - ts) / Math.max(1e-6, tl - ts); off = D * (1 - u * u); a = clamp(u * 4); } }
      st.push([off, a]);
    }
    return st;
  };
  const s = WB.custom({ t0, t1: Math.max(t1, t0 + 0.12), el, jump: 'coins',
    bbAt: t => { const st = t < t0 ? [] : items(t); let top = y - ry;
      st.forEach(([off], k) => { top = Math.min(top, y - (k + 1) * h - off - ry); });
      return [x - rx - lw - 6, top - lw - 6, x + rx + lw + 6, y + ry + lw + 6]; },
    act: t => t >= t0 && t < Math.max(t1, t0 + 0.12),
    draw(g, q, t) {
      const st = items(t);
      let top = -1; st.forEach(([off], k) => { if (off === 0) top = k; });
      st.forEach(([off, a], k) => { g.save(); g.globalAlpha *= a; item(g, x, y - (k + 1) * h - off, rx, ry, h, lw, k === top); g.restore(); });
      return null; } });
  s.topAt = t => topN(nAt(t)); s.topN = topN;
  // 1.3.1 另挂 s.geom（只加，不改上面任何行为）：rx、ry、lw、h 同上；itemTop(k)＝第 k 件（从 0 起）落定后的顶面中心 y，就是 item 收到的 yt；
  // 它与 topN(k+1)（k+1 件时外轮廓顶缘）差一个 ry：topN(k+1) = itemTop(k) − ry。外部要算摞上某件的位置，用它，别再自己重算 ry=round(w·0.16)。
  // x、y（底部中心）、item（画法）、nAt(t)（t 时件数）给 WB.sealBox 的 feed（从摞顶飞卡）用。
  s.geom = { rx, ry, lw, h, itemTop: k => y - (k + 1) * h, x, y, item, nAt };
  return s;
};

// ================= WB.walker：走动的小人 =================
// WB.walker({keys:[[t, x, y, pose, expr, tag], …], s=62, el='walker', look, label, blinkUntil}) → 自定义件（TOON.bean 画；不用作者形象）。
// t0＝最早关键帧；位置在相邻两帧之间缓动走过去（脚下随步子轻跳），两帧位置相同＝站着；姿势（rest/talk/point/shrug）与表情（happy/blank/shock）
// 取自关键帧（越界 console.error），换姿势经 TOON.poseAt 快切（0.1 s＋身体回弹）。tag 是这一帧的标签（例如年龄），交给 look 与 label：
//   look(tag) → TOON 造型对象，缺省 tag => ({base:'neutral', shirt: WB.C.accent, pants: WB.C.ink})；
//   label(tag) → 脚下名牌的字或 null，缺省不挂名牌；名牌（圆角框，字号 max(58, 0.6·s)，框宽＝字宽＋0.5·字号）一起步就收起旧字，到站时新字 0.2 s 轻弹出来，
//   textAt 上报 {text, bb}。
// 眨眼按种子（由 el 算）排时刻表 TOON.blinkAt，排到 blinkUntil 为止，缺省取 window.TIMING.total（make_timing 写进 timing.js 的全片时长；
// 与 common.js 动态包围盒求并集的片尾同一来源）；眨眼与呼吸 TOON.alive 一律用 WB.ambientT(t) 取时间（装饰动作，QA 锁相机时冻结）。
// act(t) 只覆盖走动与换姿势的区间；给 pos(t)＋ext（动态包围盒）。关键帧在建板完成后才读（同一个 keys 数组，后面的段可以改或追加）。
// 示例（随年龄变化的存钱小人）＝look: tag => ({base:'neutral', shirt: WB.C.accent, pants: WB.C.ink, hair: tag >= 55 ? WB.C.dim : WB.C.ink, glasses: tag >= 65})、label: tag => tag + ' 岁'。
WB.walker = ({ keys, s = 62, el = 'walker', look = null, label = null, blinkUntil = null }) => {
  const R = s, size = Math.max(58, Math.round(R * 0.6)), font = `600 ${size}px ${WB.BODY}`;
  const POSES = ['rest', 'talk', 'point', 'shrug'], EXPRS = ['happy', 'blank', 'shock'];
  const lookOf = typeof look === 'function' ? look : () => ({ base: 'neutral', shirt: WB.C.accent, pants: WB.C.ink });
  const hasLabel = typeof label === 'function', labelOf = hasLabel ? label : () => null;
  const bad = k => !POSES.includes(k[3] || 'rest') || !EXPRS.includes(k[4] || 'happy');
  let D = null;
  const prep = () => {                                                                              // 建板完成后第一次求位置时才读关键帧（含后面段追加的）
    if (D) return D;
    keys.forEach(k => { if (bad(k)) console.error(`WB.walker ${el}：姿势只能 ${POSES.join('/')}、表情只能 ${EXPRS.join('/')}：${JSON.stringify(k)}`); });
    const K = keys.slice().sort((a, b) => a[0] - b[0]), moving = i => i + 1 < K.length && Math.hypot(K[i + 1][1] - K[i][1], K[i + 1][2] - K[i][2]) > 0.5;
    const walks = []; for (let i = 0; i + 1 < K.length; i++) if (moving(i)) walks.push([K[i][0], K[i + 1][0]]);
    const pk = []; for (const k of K) { const p = k[3] || 'rest', e = k[4] || 'happy'; if (!pk.length || pk[pk.length - 1][1] !== p || pk[pk.length - 1][2] !== e) pk.push([k[0], p, e]); }
    const until = blinkUntil ?? ((window.TIMING && window.TIMING.total) || K[0][0] + 90);              // 眨眼排到哪：缺省＝timing.js 的全片时长
    let sd = 7; for (const ch of el) sd = (sd * 31 + ch.charCodeAt(0)) >>> 0;
    const r = U.rng(sd), blinks = []; for (let b = K[0][0] + 0.8 + r() * 1.5; b < until; b += 2.4 + r() * 1.2) blinks.push(b);
    return (D = { K, moving, walks, pk, blinks });
  };
  const seg = t => { const { K } = prep(); let i = 0; while (i + 1 < K.length && t >= K[i + 1][0]) i++; return i; };
  const state = t => {
    const { K, moving, walks } = prep(), i = seg(t), a = K[i], b = K[i + 1];
    let x = a[1], y = a[2], dir = 0, la = 1, lk = 1;
    if (moving(i) && t > a[0]) {
      const u = clamp((t - a[0]) / (b[0] - a[0])), e = MO.sineInOut(u), dist = Math.hypot(b[1] - a[1], b[2] - a[2]), steps = Math.max(2, Math.round(dist / (R * 0.9)));
      x = U.lerp(a[1], b[1], e); y = U.lerp(a[2], b[2], e) - R * 0.07 * Math.abs(Math.sin(Math.PI * steps * u)); dir = Math.sign(b[1] - a[1]);
      la = 1 - clamp((t - a[0]) / 0.12);                                                           // 起步就收起旧名牌
    } else {
      const w = walks.filter(v => v[1] <= t + 1e-9).pop();                                         // 刚到站：新名牌 0.2 s 轻弹出来
      if (w && t - w[1] < 0.2) { const d = t - w[1]; la = clamp(d / 0.08); lk = 1 + 0.25 * (1 - MO.cubicOut(clamp(d / 0.2))); }
    }
    return { x, y, gy: a[2], dir, tag: a[5], la, lk };
  };
  const plate = st => { const text = labelOf(st.tag); if (text == null || text === '') return null;
    const w = WB.measure(String(text), size, WB.BODY, '600') + size * 0.5, by = st.gy + R * 0.12 + size;
    return { text: String(text), by, w, bb: [st.x - w / 2 - 4, by - size * 1.02, st.x + w / 2 + 4, by + size * 0.36] }; };
  const t0 = Math.min(...keys.map(k => k[0]));
  const ext = hasLabel ? [-Math.max(1.6 * R, size * 1.75), -3.3 * R, Math.max(1.8 * R, size * 1.75), R * 0.12 + size * 1.45]
                       : [-1.6 * R, -3.3 * R, 1.8 * R, R * 0.15];                                    // 不挂名牌时只框小人
  return WB.custom({ t0, t1: t0 + 0.2, el, size,
    pos: t => { const st = state(t); return [st.x, st.y]; }, ext,
    act: t => { const { walks, pk } = prep(); return walks.some(([a, b]) => t >= a && t < b + 0.2) || pk.some((p, i) => i > 0 && t >= p[0] && t < p[0] + 0.3); },
    textAt: t => { const st = state(t); if (st.la < 0.5) return null; const lb = plate(st); return lb ? { text: lb.text, bb: lb.bb } : null; },
    draw(g, q, t) {
      const st = state(t), P = TOON.poseAt(prep().pk, t), at = WB.ambientT(t), C = WB.C;
      const eye = st.dir ? [0.7 * st.dir, 0] : P.pose.r[0] > 1.5 ? [0.55, -0.25] : P.expr === 'shock' ? [0, -0.6] : [0, 0];
      TOON.bean(g, { x: st.x, y: st.y, s: R, char: lookOf(st.tag), pose: P.pose, expr: P.expr, blink: TOON.blinkAt(at, prep().blinks),
        squash: P.squash * TOON.alive(at, R).breathe, look: eye });
      const lb = st.la > 0 ? plate(st) : null;
      if (lb) { g.save(); g.globalAlpha *= st.la; g.translate(st.x, lb.by - size * 0.35); g.scale(st.lk, st.lk); g.translate(-st.x, -(lb.by - size * 0.35));
        g.beginPath(); g.roundRect(st.x - lb.w / 2, lb.by - size * 0.98, lb.w, size * 1.3, size * 0.65); g.fillStyle = C.card; g.fill(); g.strokeStyle = C.soft; g.lineWidth = 3.5; g.stroke();
        g.font = font; g.fillStyle = C.ink; g.textAlign = 'center'; g.textBaseline = 'alphabetic'; g.fillText(lb.text, st.x, lb.by); g.restore(); }
      return null; } });
};

// ================= WB.docCard：原件卡（老画、照片、文献页） =================
// WB.docCard({src, rect:[x, y, w, h], title='', lines=[], credit='', t0, reveal='wipe', until=null, el, base=null, minPx=32})
//   → {face, image, titles, lines, credits, base, bb, t1, colX, colW, lineBB(i, from=0)}。
// rect 是左上角＋宽高 [x, y, w, h]（不是两角坐标）。卡面色底铺满 rect（浅色衬框＋两条胶带），左 55% 用 WB.image 放原件（contain、z 1.06 缓推），
// 右栏上方 title（宋体粗大字，放不下就在「 · 」处折行），下面 lines（每行 ≤14 字），右栏底部右对齐写 credit 小字（放不下按「 · 」、「）」「》」之后、「《」之前折行）。
// t0 起 0.6 s 自左向右擦开（reveal 'fade' 则淡入），until 起整卡消失。图片须在 project.json 的 assets 里登记，credit 必填（与 CREDITS.md「片中角注」一致）。
// 字号：minPx＝屏上最小字高（px）。字高按字号的 0.85 算（qa 口径），最小字号 mn＝⌈⌈minPx/0.85⌉ ÷ z⌉，z＝WB.camAt(t0).z（擦入那一刻的相机缩放，只算一次；
// 缺省 32 px → 字号 ≥38/z，与样片原写法逐字相同）。出处用 mn，正文约 1.5·mn（放不下就缩，不小于 mn），标题约 1.75·mn（不小于 1.2·mn）。
// 相机在 t0 之后还要推近／拉远时，按屏上最小那一刻的 z 自己核一遍（parts.md「区框取景约 0.83 倍」）。右栏正文压到出处时 console.warn（只提醒，不改画面）。
// base：给一个早于 t0 的时刻，就在那时先摆一张空卡底（卡面、边框、两条胶带，与卡面同一画法同一位置；不画放图的衬框，衬框随卡面擦开才出现；0.2 s 淡入，el＝`${el}.base`），
//   相机落地时画面里是等着放原件的空卡、不是空纸；t0 起卡面擦开时空卡底只画刀口右边还没擦到的部分（与擦开互补，胶带不叠两层；fade 时反向淡出），擦完撤掉。
// lines 每项可以是字串（随卡一起印出、不用笔）或对象 {text, el, how:'write'|'pop', t0 | at, dur, rate, col}：'write' 手写（WB.text，墨色），
// 'pop' 整行砸入（WB.pop slam，强调色，at＝砸到底那一刻）。face／图片／标题／出处都打 el。lineBB(i, from) 给第 i 行从第 from 个字起的世界框（圈字用）。
WB.docCard = ({ src, rect, title = '', lines = [], credit = '', t0, reveal = 'wipe', until = null, el, base = null, minPx = 32 }) => {
  if (!['wipe', 'fade'].includes(reveal)) throw new Error(`WB.docCard：reveal 只能是 wipe、fade：${reveal}`);
  if (!(Array.isArray(rect) && rect.length === 4 && rect.every(Number.isFinite))) throw new Error(`WB.docCard：rect 要 [x, y, w, h] 四个数：${JSON.stringify(rect)}`);
  if (base != null && !(Number.isFinite(base) && base < t0)) throw new Error(`WB.docCard：base（空卡底先摆的时刻）须早于 t0（${t0}）：${base}`);
  const I = window.IMG || {}, fd = String(window.SCENE_DIR || '').split('/')[0], im = I[src] || I[`${fd}/${src}`];
  if (!im) throw new Error(`WB.docCard：图片「${src}」没在 project.json 的 assets 里登记（或没载入）`);
  const C = WB.C, [x, y, w, h] = rect, z = WB.camAt(t0).z, mn = Math.ceil(Math.ceil(minPx / 0.85) / z), pad = Math.round(Math.max(36, w * 0.025)), dur = 0.6, t1 = t0 + dur;
  const S = MO.sineInOut, p = t => clamp((t - t0) / dur);
  const X0 = x - 60, XW = w + 120, edgeT = xx => t0 + dur * inv((xx - X0) / XW);                    // 擦开的刀口在 xx 处的时刻
  const show = (g, t) => { if (reveal === 'wipe') { g.beginPath(); g.rect(X0, y - 80, XW * S(p(t)), h + 160); g.clip(); } else g.globalAlpha *= S(p(t)); };
  // 图片区（左 55%）与 contain 后的实际位置
  const ia = [x + pad, y + pad, w * 0.55 - pad * 1.5, h - pad * 2], k = Math.min(ia[2] / im.width, ia[3] / im.height);
  const dw = im.width * k, dh = im.height * k, dx = ia[0] + (ia[2] - dw) / 2, dy = ia[1] + (ia[3] - dh) / 2;
  const colX = x + w * 0.55 + pad * 0.5, colW = x + w - pad - colX;
  const cardFace = (g, matte = true) => {                                                          // 卡面＋边框＋两条胶带，matte 时加衬框（卡面画；空卡底不画，免得先冒出灰框像图没加载）
    g.fillStyle = C.card; g.fillRect(x, y, w, h); g.strokeStyle = C.line; g.lineWidth = 5; g.strokeRect(x, y, w, h);
    if (matte) { g.fillStyle = C.line; g.fillRect(dx - 14, dy - 14, dw + 28, dh + 28); }          // 衬框（画在胶带之下，与 1.3.0 同序）
    for (const [tx, r] of [[x + 90, -0.5], [x + w - 90, 0.5]]) { g.save(); g.translate(tx, y + 6); g.rotate(r); g.fillStyle = C.tape; g.fillRect(-80, -20, 160, 40); g.restore(); }
  };
  const cardBB = [x - 40, y - 40, x + w + 40, y + h + 40];
  const baseS = base == null ? null : WB.custom({ t0: base, t1: base + 0.2, until: until == null ? t1 + 0.05 : Math.min(until, t1 + 0.05), el: el == null ? undefined : `${el}.base`,
    bb: cardBB, jump: 'base', draw(g, q, t) {
      g.globalAlpha *= S(clamp(q));
      if (reveal === 'wipe') { const e = X0 + XW * S(p(t)); g.beginPath(); g.rect(e, y - 80, X0 + XW - e, h + 160); g.clip(); }
      else g.globalAlpha *= 1 - S(p(t));
      cardFace(g, false); return null; } });
  const face = WB.custom({ t0, t1, until, el, bb: cardBB, draw(g, q, t) { show(g, t); cardFace(g); return null; } });
  const ib = [dx - 24, dy - 24, dx + dw + 24, dy + dh + 24], ta = reveal === 'wipe' ? edgeT(ib[0]) : t0, tb = reveal === 'wipe' ? edgeT(ib[2]) : t1;
  const image = WB.image(src, ia[0], ia[1], ia[2], ia[3], { reveal, t0: ta, dur: Math.max(0.05, tb - ta), z: 1.06, fy: 0.42, until, el });
  // 印出来的字（随卡擦开）：一行一个自定义件，textAt 报字与框
  const printed = (text, px, by, size, fam, wt, col, align = 'left', lel = el) => {
    const tw = WB.measure(text, size, fam, wt), x0 = align === 'right' ? px - tw : px, bb = [x0 - 8, by - size * 1.05, x0 + tw + 8, by + size * 0.35];
    return WB.custom({ t0, t1, until, el: lel, size, bb, textAt: () => ({ text, bb }), draw(g, q, t) {
      show(g, t); g.font = WB.cf('', size, fam, wt); g.fillStyle = col; g.textBaseline = 'alphabetic'; g.textAlign = 'left'; g.fillText(text, x0, by); return null; } });
  };
  const fits = (str, size, fam, wt) => WB.measure(str, size, fam, wt) <= colW;
  // 标题：宋体粗，约最小字号的 1.75 倍；整行放不下就在「 · 」处折行，再放不下就缩（不小于 1.2 倍）
  let ts = Math.round(mn * 1.75), tl = [title];
  if (!fits(title, ts, WB.FONT, '700')) tl = title.split(' · ');
  while (ts > Math.round(mn * 1.2) && !tl.every(s2 => fits(s2, ts, WB.FONT, '700'))) ts = Math.max(Math.round(mn * 1.2), ts - 2);
  let yy = y + pad + ts * 0.95;
  const titles = title ? tl.map(s2 => { const c = printed(s2, colX, yy, ts, WB.FONT, '700', C.ink); yy += ts * 1.25; return c; }) : [];
  if (!title) yy += ts * 1.25;
  // 正文行：苹方半粗，约最小字号的 1.5 倍，放不下就缩（不小于最小字号）
  const txt = lines.map(l => typeof l === 'string' ? l : l.text);
  let ls = Math.round(mn * 1.5);
  while (ls > mn && !txt.every(s2 => fits(s2, ls, WB.BODY, '600'))) ls = Math.max(mn, ls - 2);
  yy += -ts * 1.25 + ts * 0.35 + ls * 1.45;
  const LP = [], lineStrokes = lines.map(l => {
    const by = yy; yy += ls * 1.55; LP.push(by);
    if (typeof l === 'string') return printed(l, colX, by, ls, WB.BODY, '600', C.ink);
    if (l.how === 'pop') return WB.pop(l.text, colX, by, ls, { at: l.at ?? l.t0 + 0.1, slam: true, align: 'left', col: l.col ?? C.accent, fam: WB.BODY, wt: '600', el: l.el, until });
    return WB.text(l.text, colX, by, ls, { t0: l.t0 ?? l.at, dur: l.dur, rate: l.rate ?? 14, fam: WB.BODY, wt: '600', col: l.col ?? C.ink, el: l.el, until });
  });
  // 出处：最小字号、暗色，右栏底部右对齐；先按「 · 」再按「）」「》」之后、「《」之前切块，贪心排进右栏宽度
  const cs = mn, toks = [];
  String(credit).split(' · ').forEach((sg, i) => sg.split(/(?<=[）》])|(?=《)/).filter(Boolean).forEach((part, j) => toks.push([j ? '' : i ? ' · ' : '', part])));
  const cl = []; let cur = '';
  for (const [sep, part] of toks) { const cand = cur ? cur + sep + part : part; if (!cur || fits(cand, cs, WB.BODY, '')) cur = cand; else { cl.push(cur); cur = part; } }
  if (cur) cl.push(cur);
  const cb = y + h - pad * 0.75;
  const credits = credit ? cl.map((c, i) => printed(c, colX + colW, cb - (cl.length - 1 - i) * cs * 1.3, cs, WB.BODY, '', C.dim, 'right')) : [];
  const textBot = LP.length ? LP[LP.length - 1] + ls * 0.35 : yy - ls * 1.45, credTop = credit ? cb - (cl.length - 1) * cs * 1.3 - cs * 1.05 : y + h - pad * 0.5;
  if (textBot > credTop - 4) console.warn(`WB.docCard ${el || src}：右栏字排不下（正文底 ${Math.round(textBot)} 压到出处顶 ${Math.round(credTop)}；最小字号 ${mn}，由 minPx ${minPx} 与 t0 时相机缩放 z ${z.toFixed(3)} 定）——` +
    '加高 rect、少写一行或缩短出处，或让 t0 时相机推得更近（parts.md「区框取景」）');
  const lineBB = (i, from = 0) => { const s2 = txt[i], a = colX + WB.measure(s2.slice(0, from), ls, WB.BODY, '600'), b = colX + WB.measure(s2, ls, WB.BODY, '600');
    return [a - 6, LP[i] - ls * 0.95, b + 6, LP[i] + ls * 0.25]; };
  return { face, image, titles, lines: lineStrokes, credits, base: baseS, bb: [x, y, x + w, y + h], t1, colX, colW, lineBB };
};

// ================= WB.trip：远行运镜（不做 declip） =================
// WB.trip(t, dur, rect, o={}) → 落点 [x, y, z, bb]。同 WB.travel（途中先拉远再推近、中点速度不停），但落点就是 WB.frame(rect, o)，不过 declip——
// 不让已撤掉（until）的字把相机推歪。rect 是两角坐标 [x0, y0, x1, y1]（同 WB.frame，不是 docCard 的 [x, y, w, h]）；
// o.out＝中点缩放相对两端较小者的倍数（缺省 0.72）、o.whip 加甩镜模糊，其余键（pad、zmin、zmax、dx、sy）原样交给 WB.frame。
// 运镜照例登记 WB.ev(拍, 'cam', 'camera', t, dur)。
WB.trip = (t, dur, rect, o = {}) => {
  const c = WB.frame(rect, o), a = WB.camAt(t), zm = Math.min(a.z, c[2]) * (o.out ?? 0.72);
  WB.move(t, t + dur / 2, (a.x + c[0]) / 2, (a.y + c[1]) / 2, zm, { ease: p => 2 * MO.sineInOut(p / 2), whip: o.whip });
  WB.move(t + dur / 2, t + dur, c[0], c[1], c[2], { ease: p => 2 * MO.sineInOut(0.5 + p / 2) - 1, whip: o.whip });
  return c;
};

// ================= WB.retire：在 t 撤掉一批笔画 =================
// WB.retire(n0, t)：把 WB.S.slice(n0)（n0 起新压进的笔画）在 t 统一撤掉（设 until；已有更早 until 的不改）。相机离开某个区之后用：
// 进区前记 const n0 = WB.S.length，区里的东西画完后 WB.retire(n0, 离开时刻)。
WB.retire = (n0, t) => WB.S.slice(n0).forEach(s => { s.until = s.until == null ? t : Math.min(s.until, t); });

// =====================================================================================================
// 1.3.1：取自样片的九件。上屏字一律由调用者写（WB.text／WB.pop），件不自带字。
// =====================================================================================================
const box4 = b => Array.isArray(b) && b.length === 4 && b.every(Number.isFinite);
const spline = (P, n = 14) => {                                                                    // Catmull-Rom 平滑折线（收自样片 L.spline）
  const out = [];
  for (let i = 0; i < P.length - 1; i++) {
    const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
    for (let j = 0; j < n; j++) { const t = j / n, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map(c => 0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3))); }
  }
  out.push(P[P.length - 1]); return out;
};

// ================= WB.popIn：弹入 =================
// WB.popIn(s, t0, dur, ax, ay) → s：给一个自定义件套一层「t0 起 dur 秒从锚点 (ax, ay) 放大回弹出现」（MO.backOut(u, 2.2)，前 1/4 段淡入）；
// act 补上 [t0, t0+dur)（原有的 act 照留），jump 没设就记 'pop'（qa 的 jumps 认作有意跳变）。机器、日历、锁、小人都用它，锚点一般取底边中心或中心。
WB.popIn = (s, t0, dur, ax, ay) => {
  const d0 = s.draw, a0 = s.act;
  s.draw = function (g, q, t) {
    const u = clamp((t - t0) / dur);
    if (u < 1) { const k = Math.max(0.001, MO.backOut(u, 2.2)); g.globalAlpha *= clamp(u * 4); g.translate(ax, ay); g.scale(k, k); g.translate(-ax, -ay); }
    return d0.call(this, g, q, t);
  };
  s.act = t => (t >= t0 && t < t0 + dur) || (a0 ? a0(t) : false);
  if (!s.jump) s.jump = 'pop';
  return s;
};

// ================= WB.shape：手画形状 =================
// WB.shape(type, x, y, r, o={}) → WB.sketch 的结果 {s, t0, t1}：手画一个形状，type 'circle' 圆、'tri' 三角、'square' 方块，中心 (x, y)、半径 r（对照表里的答案）。
// o 原样交给 WB.sketch（t0、dur、el；col 缺省 WB.C.ink；w 缺省 r/6，r 36 时为 6）。
WB.shape = (type, x, y, r, o = {}) => {
  const e = r / 18;                                                                                 // 收口处多走一点，首尾接上（r 36 时 2）
  const P = type === 'circle' ? [[WB.circ(x, y, r, 1.04)]]
    : type === 'tri' ? [[[[x, y - r], [x + r * 0.95, y + r * 0.75], [x - r * 0.95, y + r * 0.75], [x, y - r - e]], { smooth: false }]]
    : type === 'square' ? [[[[x - r * 0.82, y - r * 0.82], [x + r * 0.82, y - r * 0.82], [x + r * 0.82, y + r * 0.82], [x - r * 0.82, y + r * 0.82], [x - r * 0.82, y - r * 0.82 - e]], { smooth: false }]]
    : null;
  if (!P) throw new Error(`WB.shape：type 只能是 circle、tri、square：${type}`);
  return WB.sketch(P, { w: Math.max(2, r / 6), col: WB.C.ink, ...o });
};

// ================= WB.machineDraw／WB.machine：方盒机器 =================
// WB.machineDraw(g, [x, y, w, h], {face=1, flash=0, busy=null, slot=true, slotR=false})：只画不登记（同 WB.coinDraw，在 WB.custom 的 draw 里调）。
//   方盒底边站在 y+h（两只脚），屏幕（面 C.board）、两个按钮＋一道散热线；face＝屏上眼睛与嘴的亮度 0..1，flash＝屏幕闪光 0..1（铺一层 C.wash），
//   busy＝屏幕下沿进度条 0..1（null 不画），slot＝顶上的进纸口（缺省画，同样片），slotR＝右侧出口（缺省不画；做完的东西从右边出来时开）。线宽 max(3, w·0.0214)（280 宽时约 6）；屏框、按钮、脚高、圆角按 280 宽时的样片值等比缩放。
WB.machineDraw = (g, box, o = {}) => {
  const { face = 1, flash = 0, busy = null, slot = true, slotR = false } = o;
  const C = WB.C, [x, y, w, h] = box, k = w / 280, lw = Math.max(3, w * 0.0214), bh = h - 22 * k;
  g.lineJoin = 'round'; g.lineCap = 'round';
  g.fillStyle = C.ink; g.fillRect(x + w * 0.14, y + bh - 2 * k, w * 0.16, 24 * k); g.fillRect(x + w * 0.7, y + bh - 2 * k, w * 0.16, 24 * k);   // 两只脚
  g.beginPath(); g.roundRect(x, y, w, bh, 24 * k); g.fillStyle = C.card; g.fill(); g.strokeStyle = C.ink; g.lineWidth = lw; g.stroke();
  if (slot) { g.fillStyle = C.ink; g.beginPath(); g.roundRect(x + w * 0.3, y - 8 * k, w * 0.4, 16 * k, 6 * k); g.fill(); }                 // 顶上的进纸口
  const sx = x + w * 0.13, sy = y + bh * 0.12, sw = w * 0.74, sh = bh * 0.46;
  g.beginPath(); g.roundRect(sx, sy, sw, sh, 14 * k); g.fillStyle = C.board; g.fill();
  if (flash) { g.save(); g.globalAlpha *= flash; g.fillStyle = C.wash; g.fill(); g.restore(); }
  g.strokeStyle = C.ink; g.lineWidth = lw * 0.75; g.stroke();
  if (face) { g.save(); g.globalAlpha *= face; g.fillStyle = C.ink; const ey = sy + sh * 0.4;
    for (const s of [-1, 1]) { g.beginPath(); g.arc(sx + sw / 2 + s * sw * 0.18, ey, w * 0.032, 0, Math.PI * 2); g.fill(); }
    g.strokeStyle = C.ink; g.lineWidth = lw * 0.75; g.beginPath(); g.arc(sx + sw / 2, ey + sh * 0.08, sw * 0.16, 0.25 * Math.PI, 0.75 * Math.PI); g.stroke(); g.restore(); }
  if (busy != null) { g.fillStyle = C.accent; g.fillRect(sx + sw * 0.12, sy + sh * 0.8, sw * 0.76 * clamp(busy), sh * 0.08); }
  g.strokeStyle = C.soft; g.lineWidth = lw * 2 / 3; g.beginPath(); g.arc(x + w * 0.3, y + bh * 0.78, w * 0.06, 0, Math.PI * 2); g.stroke();   // 两个按钮＋一道散热线
  g.beginPath(); g.arc(x + w * 0.5, y + bh * 0.78, w * 0.06, 0, Math.PI * 2); g.stroke();
  g.beginPath(); g.moveTo(x + w * 0.66, y + bh * 0.78); g.lineTo(x + w * 0.86, y + bh * 0.78); g.stroke();
  if (slotR) { g.fillStyle = C.ink; g.fillRect(x + w - 8 * k, y + bh * 0.62, 14 * k, bh * 0.2); }                                         // 右侧出口
};
// WB.machine({box, el, t0, until=null, pop=0.4, faceAt=null, flashAt=[], flashDur=0.45, busy=null, hopAt=[], slotR=false}) → 自定义件（画法同 machineDraw，slotR 原样透传）。
//   pop＝秒数：t0 起 WB.popIn（锚点在底边中心）；null：t0 直接出现。faceAt(t) → 0..1（缺省恒 1；它在变的时刻自动算进 act）。
//   flashAt：每个时刻屏幕闪一次（sin 脉冲 flashDur 秒）。busy：[b0, b1]——进度条在 b0–b1 走满，满格停 0.3 s 后收起（与样片同）；
//   [b0, 收起后 0.1 s) 都在 act 里，件带 jump，收起那一下 qa 认作有意跳变（样片里这一下没登记）。hopAt：每个时刻一跳（以底边中心缩放 1+0.18·sin，0.45 s，同时闪）。
//   act 由以上窗口合成；静态 bb＝box 外扩（有 hopAt 时按跳起的 1.18 倍再外扩）。
WB.machine = ({ box, el, t0, until = null, pop = 0.4, faceAt = null, flashAt = [], flashDur = 0.45, busy = null, hopAt = [], slotR = false }) => {
  if (!box4(box)) throw new Error(`WB.machine：box 要 [x, y, w, h] 四个数：${JSON.stringify(box)}`);
  if (busy != null && !(Array.isArray(busy) && busy.length === 2 && busy.every(Number.isFinite) && busy[1] > busy[0])) throw new Error(`WB.machine：busy 要 [起, 止] 两个数且止晚于起：${JSON.stringify(busy)}`);
  const [x, y, w, h] = box, k = w / 280, HOP = 0.45, HOLD = 0.3, ax = x + w / 2, ay = y + h;
  const within = (list, d, t) => list.some(a => t >= a && t < a + d);
  const pulse = (list, d, t) => { let v = 0; for (const a of list) if (t >= a && t < a + d) v = Math.max(v, Math.sin(Math.PI * (t - a) / d)); return v; };
  const faceMoving = t => !!faceAt && Math.abs(faceAt(t + 0.02) - faceAt(t - 0.02)) > 1e-4;
  const bOff = busy ? busy[1] + HOLD : null;                                                        // 进度条收起的时刻
  const e = hopAt.length ? 0.18 : 0, ends = [t0 + (pop || 0), ...flashAt.map(a => a + flashDur), ...hopAt.map(a => a + HOP)];
  if (busy) ends.push(bOff);
  const s = WB.custom({ t0, t1: Math.max(...ends), until, el, jump: 'pop',
    bb: [x - w * e / 2 - 20 * k, y - h * e - 30 * k, x + w + w * e / 2 + 20 * k, y + h + 10 * k],
    act: t => faceMoving(t) || within(flashAt, flashDur, t) || within(hopAt, HOP, t) || (!!busy && t >= busy[0] && t < bOff + 0.1),
    draw(g, q, t) {
      const hop = pulse(hopAt, HOP, t);
      if (hop) { const kk = 1 + 0.18 * hop; g.translate(ax, ay); g.scale(kk, kk); g.translate(-ax, -ay); }
      const bv = busy && t >= busy[0] && t < bOff ? (t - busy[0]) / (busy[1] - busy[0]) : null;
      WB.machineDraw(g, box, { face: faceAt ? faceAt(t) : 1, flash: Math.max(pulse(flashAt, flashDur, t), hop), busy: bv, slotR });
      return null; } });
  if (pop != null && pop > 0) WB.popIn(s, t0, pop, ax, ay);
  return s;
};

// ================= WB.cardItem：卡片一摞的画法（WB.stack 的 item） =================
// WB.cardItem({rules, mark=null, thin=false, accEdge}) → item(g, cx, yt, rx, ry, h, lw, acc)。合并样片三种画法，缺省值随画法走（每种缺省＝样片原样）：
//   缺省＝题卡：顶面＋厚边，顶面 rules 道横线（缺省 3，最后一道短），acc（已落地的最上一张）描强调色边（accEdge 缺省 true）；
//   mark:'tick'＝做完的卡：顶面一个墨色勾（rules 缺省 0、accEdge 缺省 false）；
//   thin:true＝考卷（薄纸）：只有最上一张画强调色题头线＋rules 道通栏横线（rules 缺省 2、accEdge 缺省 false）。
//   显式给的 rules、accEdge 照用。颜色 C.card／ink／accent／line；圆角按半宽比例（题卡 0.035·rx，薄纸 0.027·rx）。
WB.cardItem = ({ rules = null, mark = null, thin = false, accEdge = null } = {}) => {
  if (mark != null && mark !== 'tick') throw new Error(`WB.cardItem：mark 只能是 'tick' 或 null：${mark}`);
  const nr = rules ?? (thin ? 2 : mark ? 0 : 3), edge = accEdge ?? !(thin || mark);
  const fr = (i, a, b) => nr > 1 ? a + (b - a) * i / (nr - 1) : a;                                  // 第 i 道横线在顶面上的位置（比例）
  return (g, cx, yt, rx, ry, h, lw, acc) => {
    const C = WB.C;
    g.beginPath(); g.roundRect(cx - rx, yt - ry, rx * 2, ry + h, rx * (thin ? 0.027 : 0.035)); g.fillStyle = C.card; g.fill();
    g.strokeStyle = acc && edge ? C.accent : C.ink; g.lineWidth = lw; g.stroke();
    if (thin) {
      if (acc) { g.lineWidth = Math.max(2, lw * 0.55); g.strokeStyle = C.accent; g.beginPath(); g.moveTo(cx - rx * 0.75, yt - ry * 0.7); g.lineTo(cx - rx * 0.1, yt - ry * 0.7); g.stroke();
        if (nr > 0) { g.strokeStyle = C.line; g.beginPath(); for (let i = 0; i < nr; i++) { const yy = yt - ry * (1 - fr(i, 0.45, 0.7)); g.moveTo(cx - rx * 0.75, yy); g.lineTo(cx + rx * 0.75, yy); } g.stroke(); } }
    } else if (nr > 0) {
      g.strokeStyle = C.line; g.lineWidth = Math.max(2, lw * 0.5); g.beginPath();
      for (let i = 0; i < nr; i++) { const yy = yt - ry + ry * fr(i, 0.3, 0.8); g.moveTo(cx - rx * 0.7, yy); g.lineTo(cx + rx * (nr > 1 && i === nr - 1 ? 0.2 : 0.7), yy); }
      g.stroke();
    }
    if (mark === 'tick') { g.strokeStyle = C.ink; g.lineWidth = Math.max(3, lw * 0.9); g.lineCap = 'round'; g.lineJoin = 'round';
      g.beginPath(); g.moveTo(cx - ry * 0.5, yt - ry * 0.5); g.lineTo(cx - ry * 0.1, yt - ry * 0.15); g.lineTo(cx + ry * 0.6, yt - ry * 0.85); g.stroke(); }
  };
};

// ================= WB.compareTable：两列对照表 =================
// WB.compareTable({rect:[x0, y0, x1], hy, rh, n, cx:[左列, 右列, 标记列], cl:[分隔线 x…], left:[type…], right:[type…], heads=[], tPre, tRight, tMarks, tRings,
//   el={table:'table', ticks:'ticks', cross:'cross'}}) → {rowY(i), bad, strokes:{frame, left, right, marks, rings}, t1}。
//   表顶 y0、表头下沿 hy、行高 rh、n 行（表底＝hy + rh·n）；left、right 是每行的形状（WB.shape 的 type），bad＝left[i] !== right[i] 的行号（自动算）。
//   tPre 起 0.2 s 画表框（外框、表头线、分隔线、行线），左列形状每个间隔 0.06 s 跟着画（el＝`${el.table}_e`）——表框与左列是镜头外预摆，不占「一支笔」（handed false）；
//   tRight 起右列逐行（每个 0.16 s、间隔 0.2 s）；tMarks 起标记列：一致打勾、不一致打叉（每个 0.18 s、间隔 0.21 s）；tRings 起只给叉画红圈（每个 0.25 s、间隔 0.29 s），
//   红圈框只在标记格内（格窄时自动收小），不跨列。勾、叉、形状、红圈按 rh 的比例取（rh 100 时依次 76、64、36、圈框 68×68 外扩 10），线宽同比。
//   heads[i]＝(g, [x, y, w, h]) => void：画第 i 列的表头图标（x、w 是第 i 格的左缘与宽，y、h 是表顶到表头线），裁在格内，用一个 nopen 的 custom 登记（并进 strokes.frame）。
//   表头写不写字由调用者定（上屏字 ≤8）。el 可只给要改的键。
WB.compareTable = ({ rect, hy, rh, n, cx, cl, left, right, heads = [], tPre, tRight, tMarks, tRings, el = {} }) => {
  if (!(Array.isArray(rect) && rect.length === 3 && rect.every(Number.isFinite))) throw new Error(`WB.compareTable：rect 要 [x0, y0, x1] 三个数：${JSON.stringify(rect)}`);
  if (!(Number.isInteger(n) && n >= 1 && Array.isArray(left) && Array.isArray(right) && left.length === n && right.length === n)) throw new Error(`WB.compareTable：left、right 要各 n（${n}）项`);
  if (!(Array.isArray(cx) && cx.length === 3 && cx.every(Number.isFinite) && Array.isArray(cl) && cl.every(Number.isFinite))) throw new Error('WB.compareTable：cx 要 [左列, 右列, 标记列] 三个数，cl 要分隔线 x 的数组');
  if (![hy, rh, tPre, tRight, tMarks, tRings].every(Number.isFinite)) throw new Error('WB.compareTable：hy、rh、tPre、tRight、tMarks、tRings 都要是数');
  const C = WB.C, E = { table: 'table', ticks: 'ticks', cross: 'cross', ...el }, [x0, y0, x1] = rect, k = rh / 100, yb = hy + rh * n, xs = [x0, ...cl, x1];
  const rowY = i => hy + rh * (i + 0.5);
  const bad = []; for (let i = 0; i < n; i++) if (left[i] !== right[i]) bad.push(i);
  const fr = WB.sketch([
    [[[x0, y0], [x1, y0], [x1, yb], [x0, yb], [x0, y0 - 2 * k]], { smooth: false, w: 6 * k }],
    [[[x0, hy], [x1, hy]], { smooth: false, w: 5 * k }],
    ...cl.map(c => [[[c, y0], [c, yb]], { smooth: false, w: 4 * k }]),
    ...Array.from({ length: n - 1 }, (_, j) => [[[x0 + 12 * k, hy + rh * (j + 1)], [x1 - 12 * k, hy + rh * (j + 1)]], { smooth: false, w: 3 * k, col: C.line }]),
  ], { t0: tPre, dur: 0.2, el: E.table });
  fr.s.forEach(s => { s.handed = false; });                                                       // 镜头外预摆：不占「一支笔」
  const frame = fr.s.slice();
  heads.forEach((fn, i) => { if (typeof fn !== 'function' || i + 1 >= xs.length) return;
    const a = xs[i], b = xs[i + 1], m = 4 * k, cell = [a, y0, b - a, hy - y0];
    frame.push(WB.custom({ t0: tPre, t1: tPre + 0.05, el: E.table, nopen: true, bb: [a + m, y0 + m, b - m, hy - m],
      draw(g) { g.beginPath(); g.rect(a + m, y0 + m, b - a - 2 * m, hy - y0 - 2 * m); g.clip(); fn(g, cell); return null; } })); });
  const LS = [], RS = [], marks = [];
  left.forEach((sh, i) => WB.shape(sh, cx[0], rowY(i), 36 * k, { t0: tPre + 0.22 + i * 0.06, dur: 0.05, el: E.table + '_e' }).s.forEach(s => { s.handed = false; LS.push(s); }));
  right.forEach((sh, i) => RS.push(...WB.shape(sh, cx[1], rowY(i), 36 * k, { t0: tRight + i * 0.2, dur: 0.16, el: E.table }).s));
  for (let i = 0; i < n; i++) { const t = tMarks + i * 0.21, y = rowY(i);
    marks.push(...(bad.includes(i) ? WB.cross(cx[2], y, 64 * k, { t0: t, dur: 0.18, el: E.ticks, w: 9 * k }) : WB.tick(cx[2], y + 4 * k, 76 * k, { t0: t, dur: 0.18, el: E.ticks, w: 9 * k })).s); }
  // 红圈：圈住标记格里的叉，横向不出格（圈的半宽＝框半宽＋pad，再留线宽）
  const mc = xs.findIndex((v, i) => i + 1 < xs.length && cx[2] >= v && cx[2] <= xs[i + 1]), cL = mc >= 0 ? xs[mc] : x0, cR = mc >= 0 ? xs[mc + 1] : x1;
  const pad = 10 * k, rw = 10 * k, half = Math.max(12 * k, Math.min(34 * k, Math.min(cx[2] - cL, cR - cx[2]) - pad - rw));
  const rings = bad.map((i, j) => { const y = rowY(i); return WB.ring([cx[2] - half, y - 38 * k, cx[2] + half, y + 30 * k], { t0: tRings + j * 0.29, dur: 0.25, el: E.cross, pad, w: rw }); });
  return { rowY, bad, strokes: { frame, left: LS, right: RS, marks, rings }, t1: Math.max(...[...RS, ...marks, ...rings].map(s => s.t1)) };
};

// ================= WB.sealBox：信封、抽屉、锁（封存） =================
// WB.sealBox({env:{cx, cy, w, h}, cab:[x, y, w, h], t:{cab, env, close, drawer, lock}, open=null, el='seal', feed=null})
//   → {tray, env, cards, stamp, cabinet, lock, envAt(t), t1}。侧面看的文件柜（抽屉朝左拉出）＋信封（中心 cx, cy）。
//   时刻：t.cab 起柜子与拉开的托盘自上而下显现 0.35 s；t.env 起信封 popIn 0.25 s（盖子开着朝上）；t.close 起盖子 0.15 s 合上，+0.25 红火漆砸上（slam，无字），
//   火漆跟着信封走；t.drawer 起信封 0.3 s 沿弧线滑进托盘，+0.3 托盘 0.35 s 推回柜里；t.lock 起锁 popIn 0.3 s，挂在抽屉把手上。
//   托盘纵向位置、拉出距离 open（缺省 cab.w·0.737）、锁与火漆尺寸都按 cab、env 的比例推（cab 380×270、env 260×160 时与样片一致）。
//   内部固定按「托盘 → 信封 → 卡片 → 火漆 → 柜子 → 锁」创建：柜子压住推进去的托盘与信封。
//   feed={stack, n, at}（可选）：at 起从 stack（一个 WB.stack，用它的 geom）摞顶飞 n 张进信封口（间隔 0.12 s、每张 0.55 s，最后 20% 淡出），用摞自己的 item 画。
//     stack 传「拿走之前」那一摞；摞要少几件，照 parts.md 经验：旧摞设 until＝at，再在 at − 0.12 新建一摞件数更少的静态摞。不给 feed 时 cards 为 null。
//   el 依次为 `${el}.tray/.env/.cards/.stamp/.cab/.lock`。运镜与 WB.ev 由调用者登记。
WB.sealBox = ({ env, cab, t, open = null, el = 'seal', feed = null }) => {
  if (!(env && [env.cx, env.cy, env.w, env.h].every(Number.isFinite))) throw new Error(`WB.sealBox：env 要 {cx, cy, w, h}：${JSON.stringify(env)}`);
  if (!box4(cab)) throw new Error(`WB.sealBox：cab 要 [x, y, w, h] 四个数：${JSON.stringify(cab)}`);
  if (!(t && ['cab', 'env', 'close', 'drawer', 'lock'].every(key => Number.isFinite(t[key])))) throw new Error(`WB.sealBox：t 要 {cab, env, close, drawer, lock} 五个时刻：${JSON.stringify(t)}`);
  const C = WB.C, E = env, [Cx, Cy, Cw, Ch] = cab, k = Cw / 380, kv = Ch / 270, se = E.w / 260, OPEN = open ?? Cw * 0.737;
  const tDr2 = t.drawer + 0.3, tDrE = tDr2 + 0.35, tStamp = t.close + 0.25, trayY = [Cy + 20 * kv, Cy + 190 * kv], TL = OPEN + 50 * k;
  const dxAt = tt => OPEN * (1 - MO.sineInOut(clamp((tt - tDr2) / (tDrE - tDr2))));                // 托盘伸出柜子左侧的长度
  const reveal = (g, tt) => { const p = MO.sineInOut(clamp((tt - t.cab) / 0.35)); g.beginPath(); g.rect(Cx - OPEN - 80 * k, Cy - 30 * kv, Cw + OPEN + 120 * k, (Ch + 60 * kv) * p); g.clip(); };
  // 托盘（侧面看：托盘底＋抽屉面板＋把手）
  const tray = WB.custom({ t0: t.cab, t1: tDrE, el: `${el}.tray`, jump: 'pop', act: tt => (tt >= t.cab && tt < t.cab + 0.35) || (tt >= tDr2 && tt < tDrE),
    bbAt: tt => [Cx - 60 * k - dxAt(tt), trayY[0] - 10 * k, Cx + 20 * k, trayY[1] + 10 * k],
    draw(g, q, tt) { reveal(g, tt); const fx = Cx - 16 * k - dxAt(tt);
      g.fillStyle = C.card; g.strokeStyle = C.ink; g.lineWidth = 5 * k;
      g.beginPath(); g.rect(fx, trayY[1] - 14 * k, TL, 14 * k); g.fill(); g.stroke();
      g.beginPath(); g.rect(fx, trayY[0], 16 * k, trayY[1] - trayY[0]); g.fill(); g.stroke();
      g.beginPath(); g.arc(fx - 14 * k, (trayY[0] + trayY[1]) / 2, 12 * k, 0, Math.PI * 2); g.fillStyle = C.ink; g.fill();
      return null; } });
  // 信封：t.drawer 前停在 (cx, cy)；之后 0.3 s 滑进托盘，再跟着托盘推进柜子
  const envAt = tt => {
    if (tt < t.drawer) return [E.cx, E.cy];
    const u = MO.sineInOut(clamp((tt - t.drawer) / 0.3)), tx = Cx - OPEN + 150 * k, ty = trayY[1] - 14 * k - E.h / 2;
    return [U.lerp(E.cx, tx, u) + (OPEN - dxAt(tt)), U.lerp(E.cy, ty, u) - E.h * 0.4375 * Math.sin(Math.PI * u)];
  };
  const flapAt = tt => 1 - 2 * MO.sineInOut(clamp((tt - t.close) / 0.15));                         // 1＝开（尖朝上），−1＝合（尖朝下）
  const envS = WB.custom({ t0: t.env, t1: tDrE, el: `${el}.env`, act: tt => (tt >= t.close && tt < t.close + 0.15) || (tt >= t.drawer && tt < tDrE),
    bbAt: tt => { const [x, y] = envAt(tt); return [x - E.w / 2 - 8 * se, y - E.h / 2 - E.h * 0.6, x + E.w / 2 + 8 * se, y + E.h / 2 + 8 * se]; },
    draw(g, q, tt) { const [x, y] = envAt(tt), w = E.w, h = E.h, x0 = x - w / 2, y0 = y - h / 2, f = flapAt(tt);
      g.lineJoin = 'round'; g.lineWidth = 5 * se; g.strokeStyle = C.ink;
      if (f > 0) { g.beginPath(); g.moveTo(x0, y0); g.lineTo(x, y0 - h * 0.55 * f); g.lineTo(x0 + w, y0); g.closePath(); g.fillStyle = C.card; g.fill(); g.stroke(); }
      g.beginPath(); g.rect(x0, y0, w, h); g.fillStyle = C.card; g.fill(); g.stroke();
      g.strokeStyle = C.soft; g.lineWidth = 3.5 * se; g.beginPath(); g.moveTo(x0, y0 + h); g.lineTo(x, y0 + h * 0.45); g.lineTo(x0 + w, y0 + h); g.stroke();
      if (f <= 0) { g.strokeStyle = C.ink; g.lineWidth = 5 * se; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x, y0 - h * 0.55 * f); g.lineTo(x0 + w, y0); g.fillStyle = C.card; g.fill(); g.stroke(); }
      return null; } });
  WB.popIn(envS, t.env, 0.25, E.cx, E.cy + E.h / 2);
  // 卡片：从摞顶飞进信封口（可选）
  let cards = null;
  if (feed) {
    const G = feed.stack && feed.stack.geom, nf = feed.n, at = feed.at;
    if (!G) throw new Error('WB.sealBox：feed.stack 要是 WB.stack 建的摞（带 geom）');
    const N = G.nAt(at);
    if (!(Number.isInteger(nf) && nf >= 1 && nf <= N && Number.isFinite(at))) throw new Error(`WB.sealBox：feed.n 要是 1..${N}（at 时摞上的件数）的整数、feed.at 要是数：${nf}、${at}`);
    const end = at + (nf - 1) * 0.12 + 0.55;
    const flyAt = (tt, i) => { const a = at + i * 0.12, u = MO.sineInOut(clamp((tt - a) / 0.55));
      return { u, x: U.lerp(G.x, E.cx, u), y: U.lerp(G.itemTop(N - 1 - i), E.cy - E.h * 0.3, u) - E.h * 0.75 * Math.sin(Math.PI * u), k: U.lerp(1, 0.75, u) }; };
    cards = WB.custom({ t0: at, t1: end, until: end, el: `${el}.cards`, jump: 'pop', act: tt => tt >= at && tt < end,
      bbAt: tt => { let b = null; for (let i = 0; i < nf; i++) { const f = flyAt(tt, i), rx = G.rx * f.k + 10 * se, r = [f.x - rx, f.y - G.ry - 10 * se, f.x + rx, f.y + G.h + 10 * se]; b = b ? WB.union(b, r) : r; } return b; },
      draw(g, q, tt) { if (tt >= end) return null;
        for (let i = nf - 1; i >= 0; i--) { const f = flyAt(tt, i); if (f.u >= 1) continue; g.save(); g.globalAlpha *= 1 - clamp((f.u - 0.8) / 0.2);
          G.item(g, f.x, f.y, G.rx * f.k, G.ry * f.k, G.h, G.lw, i === 0); g.restore(); }
        return null; } });
  }
  // 红火漆印：盖合后砸在信封盖尖上，跟着信封走（不写字）
  const SR = E.w * 46 / 260, PS = MO.PULSE.slam;
  const stamp = WB.custom({ t0: tStamp - PS * 0.6, t1: tStamp + PS * 0.4, el: `${el}.stamp`, jump: 'stamp',
    bbAt: tt => { const [x, y] = envAt(tt), r = SR + 12 * se; return [x - r, y - r, x + r, y + r]; },
    draw(g, q, tt) { const [x, y] = envAt(tt), kk = MO.slamK(q); g.globalAlpha *= clamp(q * 4); g.translate(x, y + 6 * se); g.rotate(-0.18); g.scale(kk, kk);
      g.beginPath(); for (let i = 0; i <= 48; i++) { const a = i / 48 * Math.PI * 2, r = SR * (1 + 0.07 * Math.sin(a * 9)); i ? g.lineTo(r * Math.cos(a), r * Math.sin(a)) : g.moveTo(r, 0); }
      g.closePath(); g.fillStyle = C.accent; g.fill(); g.strokeStyle = C.card; g.lineWidth = 4 * se; g.beginPath(); g.arc(0, 0, SR * 0.62, 0, Math.PI * 2); g.stroke(); return null; } });
  // 文件柜：压在托盘、信封、火漆上面画（推进去的部分被它挡住）
  const cabinet = WB.custom({ t0: t.cab, t1: t.cab + 0.35, el: `${el}.cab`, bb: [Cx - 20 * k, Cy - 20 * kv, Cx + Cw + 10 * k, Cy + Ch + 30 * kv],
    draw(g, q, tt) { reveal(g, tt); g.lineJoin = 'round';
      g.fillStyle = C.ink; g.fillRect(Cx + 24 * k, Cy + Ch - 4 * kv, 26 * k, 26 * k); g.fillRect(Cx + Cw - 50 * k, Cy + Ch - 4 * kv, 26 * k, 26 * k);
      g.beginPath(); g.rect(Cx, Cy, Cw, Ch); g.fillStyle = C.card; g.fill(); g.strokeStyle = C.ink; g.lineWidth = 6 * k; g.stroke();
      g.strokeStyle = C.line; g.lineWidth = 4 * k; g.beginPath(); g.moveTo(Cx + 30 * k, trayY[1] + 18 * kv); g.lineTo(Cx + Cw - 30 * k, trayY[1] + 18 * kv); g.stroke();
      g.fillStyle = C.card; g.strokeStyle = C.ink; g.lineWidth = 5 * k; g.beginPath(); g.rect(Cx - 16 * k, trayY[1] + 30 * kv, 16 * k, Cy + Ch - trayY[1] - 44 * kv); g.fill(); g.stroke();   // 下面那只抽屉的面板
      return null; } });
  // 锁：抽屉推回后挂在把手上
  const lx = Cx - 30 * k, ly = (trayY[0] + trayY[1]) / 2 + 18 * kv;
  const lock = WB.custom({ t0: t.lock, t1: t.lock + 0.3, el: `${el}.lock`, bb: [lx - 50 * k, ly - 60 * k, lx + 50 * k, ly + 80 * k],
    draw(g) { g.lineJoin = 'round'; g.strokeStyle = C.ink; g.lineWidth = 7 * k; g.beginPath(); g.arc(lx, ly + 6 * k, 24 * k, Math.PI, 0); g.stroke();
      g.beginPath(); g.roundRect(lx - 36 * k, ly + 6 * k, 72 * k, 60 * k, 8 * k); g.fillStyle = C.accent; g.fill(); g.lineWidth = 5 * k; g.stroke();
      g.fillStyle = C.card; g.beginPath(); g.arc(lx, ly + 30 * k, 7 * k, 0, Math.PI * 2); g.fill(); g.fillRect(lx - 3 * k, ly + 32 * k, 6 * k, 18 * k); return null; } });
  WB.popIn(lock, t.lock, 0.3, lx, ly);
  return { tray, env: envS, cards, stamp, cabinet, lock, envAt, t1: Math.max(tDrE, lock.t1, stamp.t1, cards ? cards.t1 : -Infinity) };
};

// ================= WB.calendar：日历（翻页＝时间过去） =================
// WB.calendar({rect:[x, y, w, h], t0, flips=[], fd=0.22, pop=0.3, grid=[3, 4], el}) → 自定义件。墙上挂的日历：强调色顶条、两个挂环、一页格子（grid＝[行, 列]，不写日期）。
//   t0 起 popIn pop 秒（锚点在中心；pop 为 null 时直接出现）；flips 里每个时刻翻一页（fd 秒：上一页按 cos(π·u) 绕顶边收起，过半后画成压扁的条，不盖住上方的字）。
//   顶条、格子、挂环都按 rect 比例算（220×230 时与样片一致）；act 覆盖 pop 与各翻页窗口，jump:'pop'。
WB.calendar = ({ rect, t0, flips = [], fd = 0.22, pop = 0.3, grid = [3, 4], el }) => {
  if (!box4(rect)) throw new Error(`WB.calendar：rect 要 [x, y, w, h] 四个数：${JSON.stringify(rect)}`);
  if (!(Array.isArray(grid) && grid.length === 2 && grid.every(v => Number.isInteger(v) && v >= 1))) throw new Error(`WB.calendar：grid 要 [行, 列] 两个正整数：${JSON.stringify(grid)}`);
  const C = WB.C, [kx, ky, kw, kh] = rect, sx = kw / 220, sy = kh / 230, s = Math.min(sx, sy), [nr, nc] = grid, TB = 44 * sy, PT = 40 * sy, cs = 4 / nc, rs = 3 / nr;
  const page = g => { g.fillStyle = C.card; g.fillRect(kx, ky + PT, kw, kh - PT); g.strokeStyle = C.ink; g.lineWidth = 5 * s; g.strokeRect(kx, ky + PT, kw, kh - PT);
    g.strokeStyle = C.line; g.lineWidth = 3 * s; g.beginPath();
    for (let r = 0; r < nr; r++) for (let c = 0; c < nc; c++) g.rect(kx + (22 + c * 46 * cs) * sx, ky + (70 + r * 50 * rs) * sy, 30 * cs * sx, 30 * rs * sy);
    g.stroke(); };
  const cal = WB.custom({ t0, t1: Math.max(t0 + (pop || 0.05), ...flips.map(f => f + fd)), el, jump: 'pop', bb: [kx - 20 * sx, ky - 30 * sy, kx + kw + 20 * sx, ky + kh + 20 * sy],
    act: t => flips.some(f => t >= f && t < f + fd),
    draw(g, q, t) {
      g.fillStyle = C.accent; g.fillRect(kx, ky, kw, TB); g.strokeStyle = C.ink; g.lineWidth = 5 * s; g.strokeRect(kx, ky, kw, TB);
      page(g);
      const f = flips.find(v => t >= v && t < v + fd);
      if (f != null) { const u = (t - f) / fd, hh = (kh - PT) * Math.cos(Math.PI * u), y0 = ky + PT;      // 上一页绕顶边翻上去
        g.save(); g.fillStyle = C.card; g.strokeStyle = C.ink; g.lineWidth = 5 * s;
        if (hh > 0) { g.fillRect(kx, y0, kw, hh); g.strokeRect(kx, y0, kw, hh); } else { const hb = -hh * 0.3; g.fillStyle = C.line; g.fillRect(kx, y0 - hb, kw, hb); g.strokeRect(kx, y0 - hb, kw, hb); }
        g.restore(); }
      g.fillStyle = C.ink; for (const x of [kx + 50 * sx, kx + kw - 50 * sx]) { g.beginPath(); g.roundRect(x - 7 * sx, ky - 22 * sy, 14 * sx, 40 * sy, 7 * s); g.fill(); }
      return null; } });
  if (pop != null && pop > 0) WB.popIn(cal, t0, pop, kx + kw / 2, ky + kh / 2);
  return cal;
};

// ================= WB.stepLoop：步骤环箭头（把板上已写好的步骤字依次连起来） =================
// WB.stepLoop({labels, at, dur, ends=null, back=null, w=null, head=null, wash=0.35, col=WB.C.accent, el='loop'}) → {arrows, washes, back, t1}。
//   labels：已写好的步骤字笔画（WB.text 的返回，有 bb、size），按步骤顺序；第 i 段箭头从 labels[i] 指向 labels[i+1]，at[i] 起笔、时长 dur[i]；
//   每段实际起笔＝max(at[i], 上一段箭头头画完 + 0.05)。ends[i]＝[[x0, y0], [x1, y1], bend] 时用给定端点与弯度；null（或整个 ends 为 null）时取两个字框相对的边缘中点、直线。
//   箭头到哪一步，那一步的字就涂一道淡红（WB.fill，颜色 C.wash；wash＝涂色时长（秒），不是透明度——淡红的深浅来自 C.wash 本身，同样片 B4.js:69；
//   第 1 步在第一段起笔时就亮）——远景下细箭头读不出变化时靠它。
//   back＝{at, dur, via:[[x, y]…]}：回环箭头（via 是整条路径的折点，必给；Catmull-Rom 平滑），起笔同样不早于上一段结束 + 0.05，箭头头 0.07 s。
//   杆粗 w、箭头长 head 缺省按 labels[0] 的字号算（168 号字时为 30、110）。arrows[i]＝WB.arrow 的 [杆, 头]；back＝[线, 头] 或 null。
//   el：箭头与淡红 `${el}_arrow`，回环 `${el}_back`。WB.ev 由调用者登记。
WB.stepLoop = ({ labels, at, dur, ends = null, back = null, w = null, head = null, wash = 0.35, col = WB.C.accent, el = 'loop' }) => {
  if (!(Array.isArray(labels) && labels.length >= 2 && labels.every(s => s && box4(s.bb)))) throw new Error('WB.stepLoop：labels 要至少两个带 bb 的步骤字笔画');
  const ns = labels.length - 1;
  if (!(Array.isArray(at) && Array.isArray(dur) && at.length === ns && dur.length === ns)) throw new Error(`WB.stepLoop：at、dur 要各 ${ns} 项（labels 数 − 1）`);
  if (back && !(Array.isArray(back.via) && back.via.length >= 2)) throw new Error('WB.stepLoop：back 要给 via（回环路径的折点，至少两个）');
  const size = labels[0].size || 168, AW = w ?? size * 30 / 168, AH = head ?? size * 110 / 168, C = WB.C;
  const edge = (A, B) => {                                                                          // 两个字框相对的边缘中点
    const a = A.bb, b = B.bb, gx = Math.max(b[0] - a[2], a[0] - b[2]), gy = Math.max(b[1] - a[3], a[1] - b[3]);
    const acx = (a[0] + a[2]) / 2, acy = (a[1] + a[3]) / 2, bcx = (b[0] + b[2]) / 2, bcy = (b[1] + b[3]) / 2;
    if (gx >= gy) return bcx >= acx ? [[a[2], acy], [b[0], bcy]] : [[a[0], acy], [b[2], bcy]];
    return bcy >= acy ? [[acx, a[3]], [bcx, b[1]]] : [[acx, a[1]], [bcx, b[3]]];
  };
  const hi = (s, t0) => { const b = s.bb, f = (s.size || size) / 168;
    return WB.fill(U.poly([[b[0] - 6 * f, b[1] + 14 * f], [b[2] + 6 * f, b[1] + 14 * f], [b[2] + 6 * f, b[3] + 4 * f], [b[0] - 6 * f, b[3] + 4 * f]]), C.wash, wash, { t0, el: `${el}_arrow`, bb: b }); };
  const arrows = [], washes = [];
  let prev = -Infinity;
  for (let i = 0; i < ns; i++) {
    const e = ends && ends[i] ? ends[i] : null, [a, b] = e ? [e[0], e[1]] : edge(labels[i], labels[i + 1]);
    const ar = WB.arrow(a, b, { t0: Math.max(at[i], prev + 0.05), dur: dur[i], col, w: AW, head: AH, bend: e ? (e[2] ?? 0) : 0, el: `${el}_arrow` });
    arrows.push(ar); prev = ar[1].t1;
    if (i === 0) washes.push(hi(labels[0], ar[0].t0));
    washes.push(hi(labels[i + 1], ar[1].t1 + 0.02));
  }
  let bk = null;
  if (back) {
    const P = spline(back.via, 10);
    const line = WB.line(P, { t0: Math.max(back.at, prev + 0.05), dur: back.dur, w: AW, col, amp: 2.2, el: `${el}_back`, ease: MO.cubicInOut });
    const e = P[P.length - 1], pp = P[P.length - 5], an = Math.atan2(e[1] - pp[1], e[0] - pp[0]);
    const hd = WB.line([[e[0] - Math.cos(an - 0.5) * AH, e[1] - Math.sin(an - 0.5) * AH], e, [e[0] - Math.cos(an + 0.5) * AH, e[1] - Math.sin(an + 0.5) * AH]],
      { t0: line.t1 + 0.01, dur: 0.07, w: AW, col, smooth: false, el: `${el}_back` });
    bk = [line, hd];
  }
  return { arrows, washes, back: bk, t1: Math.max(prev, ...washes.map(s => s.t1), bk ? bk[1].t1 : -Infinity) };
};

// ==== WB.roll 起（里程表式滚数，1.3.2）
// WB.roll(x, y, {from, to, fmt, land, dur, col=WB.C.accent, size=92, fam=WB.BODY, wt='600', el, center=false, follow=null, step=0.1, hold=0.1})
//   → 自定义件，另挂 land、cellsAt(t)、win。版式同早期样片的 L.count：fmt 按唯一一处 {:.0f} 拆成前缀、后缀；
//   数位等宽（'0' 的字宽）、右缘固定，位数增加时前缀跟着左移；center 按最宽值居中；(x, y)＝左端（center 时为中点）与基线；from、to 是整数且 0 ≤ from ≤ to。
// 步：从空白（from−1，不显示）滚到 to−1，共 N＝to−from 步。t0＝land−dur、T＝land−hold−t0，第 i 步在 e_i＝t0＋T·(1−√(1−(i+1)/N)) 滚完（先密后疏，
//   最后一步正好在 land−hold 滚完），只在 [e_i−d_i, e_i] 里滚（d_i＝min(step, e_i−e_{i−1})，e_{−1}＝t0），进度走 smoothstep；两步之间各位停在对齐位置，
//   进位的高位与个位同一进度一起滚。[land−hold, land) 停在 to−1；land 起 to 整块出现并轻顿 0.24 s；起跳 0.08 s 淡入。N＝0 时落定前什么都不画。
// 边缘渐变遮罩：数位窗口 [y−size, y+0.3·size]，上下各一条 0.22·size 的渐变带（窗口边上透明度 0，线性升到带内侧 1）。只有正在滚的数位走遮罩：
//   旧字上移 r·1.15·size、新字从下方 (1−r)·1.15·size 进来；滚动的数位离开对齐位越远越淡（透明度 (1−|dy|)²：旧字 (1−r)²、新字 r²），叠在边缘渐变之上，
//   滚到一半露出的半截笔画只剩淡影。两字先画进离屏画布（窗口矩形裁切兜底），destination-in 叠遮罩，再画回板上；
//   离屏画布按当前变换（相机、follow）开在屏幕像素上，画回时不重采样；遮罩逐像素按世界 y 算透明度（只有透明度，不用颜色）。停住的数位、前缀、后缀直接 fillText。
// cellsAt(t) → 每个可见数位 [{ch, dy, moving, k, x, a}]（dy 以 1.15·size 为 1，旧字 −r、新字 1−r；k＝从个位起第几位；x＝格中心；a＝(1−|dy|)²，停住的为 1）；win＝{top, bottom, band}；都是世界坐标、未加 follow。
// textAt：t0 前 null；land 起 to；其间报已滚完的值（不小于 from；N＝0 时落定前什么都不画，报 null）；给 follow 时报 {text, bb}。follow(t) → [dx, dy]：整块平移，bbAt 跟着走。
// 这一段（两行标记之间）原样搬进样片的 B0.js：只用 WB、U、MO、document 与 JS 内建对象，不用 parts.js 的私有名字，顶层只有这一句赋值。
WB.roll = (x, y, o = {}) => {
  const { from, to, fmt, land, dur, col = WB.C.accent, size = 92, fam = WB.BODY, wt = '600', el, center = false, follow = null, step = 0.1, hold = 0.1 } = o;
  const bad = m => { throw new Error(`WB.roll ${el || '(无 el)'}：${m}`); };
  if (typeof fmt !== 'string' || fmt.split('{:.0f}').length !== 2 || (fmt.match(/\{:\.\d+f\}/g) || []).length !== 1) bad(`fmt 要有且只有一处 {:.0f}：${JSON.stringify(fmt)}`);
  if (!(Number.isSafeInteger(from) && Number.isSafeInteger(to) && from >= 0 && from <= to)) bad(`from、to 要是安全整数（≤ Number.MAX_SAFE_INTEGER）且 0 ≤ from ≤ to：${from}、${to}`);
  if (!(Number.isFinite(land) && Number.isFinite(dur) && Number.isFinite(step) && Number.isFinite(hold) && step > 0 && hold >= 0 && dur > hold))
    bad(`land、dur 要是有限数，step > 0、0 ≤ hold < dur：land ${land}、dur ${dur}、step ${step}、hold ${hold}`);
  if (follow != null && typeof follow !== 'function') bad('follow 要是函数 t → [dx, dy]');
  const t0 = land - dur, font = `${wt} ${size}px ${fam}`, [pre, post] = fmt.split('{:.0f}');
  const g0 = document.createElement('canvas').getContext('2d'); g0.font = font;
  const dw = g0.measureText('0').width, pw = g0.measureText(pre).width, nd = String(to).length;
  const wMax = pw + nd * dw + g0.measureText(post).width;
  if (center) x -= wMax / 2;
  const xr = x + pw + nd * dw, S = 1.15 * size, top = y - size, bot = y + 0.3 * size, band = 0.22 * size;   // 数字右缘（固定）、一格位移、数位窗口
  const N = to - from, T = land - hold - t0;                         // 步的时刻按 t 现算，不按步数建数组（to 很大也不卡）
  const E = i => i === N - 1 ? land - hold : t0 + T * (1 - Math.sqrt(1 - (i + 1) / N));   // 第 i 步滚完的时刻
  const D = i => Math.min(step, E(i) - (i ? E(i - 1) : t0));          // 第 i 步滚动时长
  const done = t => {                                                 // 已滚完的步数＝E(i) ≤ t 的 i 的个数：先按反函数估，再用 E 逐个校正到 E(lo−1) ≤ t < E(lo)
    let lo = Math.min(N, Math.max(0, Math.floor(N * (1 - (1 - U.clamp((t - t0) / T)) ** 2))));
    while (lo > 0 && E(lo - 1) > t) lo--;
    while (lo < N && E(lo) <= t) lo++;
    return lo;
  };
  const sm = u => u * u * (3 - 2 * u), fade = dy => (1 - Math.abs(dy)) * (1 - Math.abs(dy));   // 离开对齐位越远越淡
  const dig = (n, k) => n < from ? '' : (k === 0 || n >= Math.pow(10, k)) ? String(Math.floor(n / Math.pow(10, k)) % 10) : '';
  const cells = t => {                                                // t 时：n＝对齐位置上的值（from−1＝空白），r＝这一步的进度（0＝没在滚）；各格 a＝对齐的字、b＝下一个字
    let n = to, r = 0;
    if (t < land) { const lo = done(t); n = from - 1 + lo;
      if (lo < N) { const ei = E(lo), di = D(lo); if (t > ei - di) r = sm((t - ei + di) / di); }
      if (r >= 1) { n++; r = 0; } }                                   // 离 e_i 只差浮点误差时 smoothstep 已取整到 1：算这一步滚完
    const out = []; for (let k = 0; k < nd; k++) { const a = dig(n, k), b = dig(n + 1, k); out.push({ k, x: xr - (k + 0.5) * dw, a, b, r: r > 0 && a !== b ? r : 0 }); }
    return { n, r, out };
  };
  const cellsAt = t => { if (t < t0 || (N === 0 && t < land)) return [];
    const res = []; for (const c of cells(t).out) {
      if (c.r > 0) { if (c.a) res.push({ ch: c.a, dy: -c.r, moving: true, k: c.k, x: c.x, a: fade(-c.r) }); if (c.b) res.push({ ch: c.b, dy: 1 - c.r, moving: true, k: c.k, x: c.x, a: fade(1 - c.r) }); }
      else if (c.a) res.push({ ch: c.a, dy: 0, moving: false, k: c.k, x: c.x, a: fade(0) }); }
    return res; };
  let buf = null;
  const roll1 = (g, c) => {                                           // 一格在滚：离屏画旧字、新字 → destination-in 叠遮罩 → 画回板上
    const m = g.getTransform(), X0 = c.x - dw / 2 - 2, X1 = c.x + dw / 2 + 2;
    const P = [[X0, top], [X1, top], [X0, bot], [X1, bot]].map(([px, py]) => [m.a * px + m.c * py + m.e, m.b * px + m.d * py + m.f]);
    const ox = Math.max(0, Math.floor(Math.min(...P.map(p => p[0])))), oy = Math.max(0, Math.floor(Math.min(...P.map(p => p[1]))));
    const w = Math.min(g.canvas.width, Math.ceil(Math.max(...P.map(p => p[0])))) - ox, h = Math.min(g.canvas.height, Math.ceil(Math.max(...P.map(p => p[1])))) - oy;
    if (!(w > 0 && h > 0)) return;
    if (!buf) buf = [document.createElement('canvas'), document.createElement('canvas')];
    for (const cv of buf) if (cv.width < w || cv.height < h) { cv.width = Math.max(cv.width, w); cv.height = Math.max(cv.height, h); }
    const [A, M] = buf, ac = A.getContext('2d'), mg = M.getContext('2d');
    ac.setTransform(1, 0, 0, 1, 0, 0); ac.globalCompositeOperation = 'source-over'; ac.globalAlpha = 1; ac.clearRect(0, 0, w, h);
    ac.save(); ac.setTransform(m.a, m.b, m.c, m.d, m.e - ox, m.f - oy); ac.beginPath(); ac.rect(X0, top, X1 - X0, bot - top); ac.clip();   // 窗口矩形裁切（兜底：裁切线上遮罩已是 0）
    ac.font = font; ac.fillStyle = col; ac.textAlign = 'center'; ac.textBaseline = 'alphabetic';
    if (c.a) { ac.globalAlpha = fade(-c.r); ac.fillText(c.a, c.x, y - c.r * S); }
    if (c.b) { ac.globalAlpha = fade(1 - c.r); ac.fillText(c.b, c.x, y + (1 - c.r) * S); }
    ac.globalAlpha = 1; ac.restore();
    const im = mg.createImageData(w, h), D = im.data, mi = m.inverse();   // 遮罩：每个屏幕像素中心换回世界 y，按上下渐变带取透明度
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) { const px = ox + i + 0.5, py = oy + j + 0.5, wy = mi.b * px + mi.d * py + mi.f;
      D[(j * w + i) * 4 + 3] = Math.round(255 * U.clamp(Math.min(wy - top, bot - wy) / band)); }
    mg.putImageData(im, 0, 0);
    ac.globalCompositeOperation = 'destination-in'; ac.drawImage(M, 0, 0, w, h, 0, 0, w, h); ac.globalCompositeOperation = 'source-over';
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(A, 0, 0, w, h, ox, oy, w, h); g.restore();
  };
  const bb0 = [x - 10, y - size * 1.05, x + wMax + 10, y + size * 0.3], sh = t => { const [dx, dy] = follow(t); return [bb0[0] + dx, bb0[1] + dy, bb0[2] + dx, bb0[3] + dy]; };
  const s = WB.custom({ t0, t1: land, el, size, ...(follow ? { bbAt: sh } : { bb: bb0 }), draw(g, q, t) {
    if (N === 0 && t < land) return null;
    if (follow) { const [dx, dy] = follow(t); g.translate(dx, dy); }
    g.font = font; g.fillStyle = col; g.textBaseline = 'alphabetic'; g.textAlign = 'center'; g.globalAlpha *= U.clamp((t - t0) / 0.08);
    if (t >= land) { const u = (t - land) / 0.24; if (u < 1) { const k = 1 + 0.06 * Math.sin(u * Math.PI), cx = x + wMax / 2, cy = y - size * 0.35; g.translate(cx, cy); g.scale(k, k); g.translate(-cx, -cy); } }
    const { n, r, out } = cells(t);
    for (const c of out) { if (c.r > 0) roll1(g, c); else if (c.a) g.fillText(c.a, c.x, y); }
    let nc = n < from ? String(from).length : String(n).length;           // 前缀跟着位数左移（进位那一步随进度滑过去）
    if (r > 0 && n >= from && String(n + 1).length > nc) nc += r;
    g.textAlign = 'right'; g.fillText(pre, xr - nc * dw, y); if (post) { g.textAlign = 'left'; g.fillText(post, xr, y); }
    return null; },
    textAt: t => { if (t < t0 || (N === 0 && t < land)) return null;
      const v = WB.fmt(fmt, t >= land ? to : Math.max(from, cells(t).n)); return follow ? { text: v, bb: sh(t) } : v; } });
  s.land = land; s.cellsAt = cellsAt; s.win = { top, bottom: bot, band }; WB.texts.push(WB.fmt(fmt, to)); return s;
};
// ==== WB.roll 止

// ==== WB.panTo／WB.review 起（换页两式，1.3.3）
// 换页三式里的 B 平移、C 拉远回顾（A 引线＝WB.lead＋WB.trip／WB.travel；三式的时刻规矩见 parts.md 第十四节）。原型取自一支讲解片的平移进页与拉远回顾。
// 落点 to 两种写法：[x, y, z]＝相机位（WB.frame、WB.trip 返回的 [x, y, z, bb] 也认）；[x0, y0, x1, y1]＝两角矩形，先过 WB.frame(to, o)（o 的 pad、zmin、zmax、dx、sy 原样交给它）。
// WB.panTo(t, dur=1.2, to, o={}) → {t1, ready, cam}：从 WB.camAt(t) 用 MO.sineInOut 直线移到落点，途中不拉远（z 在两端之间单调）。
// WB.review(t, to, o={}) → {t1, ready, cam}：拉远 o.out（缺省 1.2 s）到全貌机位 o.overview（必填：相机位或矩形；矩形按 WB.frame 的缺省取景，o 的取景键只管 to），
//   停 o.hold（缺省 1.0 s），再推进 o.in（缺省 1.3 s）到 to；拉远、推进各是一段 sineInOut 直线运镜。
// t1＝落地时刻（最后一个相机键的时刻）；ready＝t1 + WB.SETTLE + 0.02（下一页的正文从这里起笔）；cam＝落点（给矩形时就是 WB.frame(to, o) 的返回值，否则 [x, y, z]）。
// 两件都不调 WB.ev：同 WB.trip，由调用方登记 WB.ev(拍, 'cam', 'camera', t, 总时长)。参数不对就抛错（「WB.panTo」「WB.review」开头），抛错时一个相机键都不压。
// 只用 WB、MO：旧工程（工程里的 parts.js 是旧副本）要用，把这一段原样贴进场景文件即可。
{
  const num = v => typeof v === 'number' && Number.isFinite(v);
  const camOf = (who, v, o) => {                                                                     // 落点 → 相机；不合法抛错
    const bad = why => new Error(`${who}：${why}，收到 ${JSON.stringify(v)}`);
    if (!Array.isArray(v) || !v.slice(0, 3).every(num)) throw bad('要是相机位 [x, y, z] 或矩形 [x0, y0, x1, y1]');
    if (v.length === 4 && num(v[3])) {
      if (!(v[2] > v[0] && v[3] > v[1])) throw bad('矩形要 x1 > x0、y1 > y0');
      return WB.frame(v, o);
    }
    if (v.length !== 3 && !(v.length === 4 && Array.isArray(v[3]))) throw bad('要是相机位 [x, y, z] 或矩形 [x0, y0, x1, y1]');
    if (!(v[2] > 0)) throw bad('相机缩放 z 要大于 0');
    return [v[0], v[1], v[2]];
  };
  const secs = (who, pairs) => pairs.forEach(([k, v, z]) => { if (!num(v) || (z ? v < 0 : v <= 0)) throw new Error(`${who}：${k} 要是${z ? '不小于 0' : '大于 0'}的秒数，收到 ${v}`); });
  const go = (t, dur, cam) => {                                                                     // 一段 sineInOut 直线运镜；落地＝最后一个相机键
    WB.move(t, t + dur, cam[0], cam[1], cam[2], { ease: MO.sineInOut });
    const t1 = WB.K[WB.K.length - 1].t;
    return { t1, ready: t1 + WB.SETTLE + 0.02, cam };
  };
  WB.panTo = (t, dur, to, o = {}) => {
    const d = dur ?? 1.2;
    if (!num(t)) throw new Error(`WB.panTo：起镜 t 要是秒数，收到 ${t}`);
    secs('WB.panTo', [['dur', d]]);
    return go(t, d, camOf('WB.panTo', to, o));
  };
  WB.review = (t, to, o = {}) => {
    if (!num(t)) throw new Error(`WB.review：起镜 t 要是秒数，收到 ${t}`);
    if (o.overview == null) throw new Error('WB.review：o.overview（全貌机位：相机位 [x, y, z] 或矩形 [x0, y0, x1, y1]）必填');
    const out = o.out ?? 1.2, hold = o.hold ?? 1.0, tin = o.in ?? 1.3;
    secs('WB.review', [['o.out', out], ['o.hold', hold, true], ['o.in', tin]]);
    const ov = camOf('WB.review（o.overview）', o.overview, {}), cam = camOf('WB.review', to, o);   // 先全部核完再压相机键
    const a = go(t, out, ov);
    return go(a.t1 + hold, tin, cam);
  };
}
// ==== WB.panTo／WB.review 止
})();
