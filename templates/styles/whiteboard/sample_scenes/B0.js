// B0 · 片头（3 s，无口播）＋ 全片版式 WB.L（各段共用的世界坐标；脚本与分镜.md 第一节）。
// 第 0 帧板上已经有一段正在画的「上翘小曲线」（先平后翘，正是复利的形状），线头红点砸下，再一笔一画写「复利曲线」（宋体粗）。相机停在标题近景。
//
// 版式（世界坐标）：整块板收紧成「标题列＋坐标系＋坐标系正下方一条带」，相机每次移动落地时画面里都还有上一处的东西，
// 收尾拉远只拉到这三块的紧框（约 0.53 倍，图表里最小的字约 35 px）：
//  标题列 x 1160–1680：「复利曲线」在上、小曲线在下，紧贴纵轴左边（B1 起相机拉远时标题缩到板角）；
//  坐标系 L.chart：横轴 年数 0→40 ＝ x 1800→3600（每年 45 px）；纵轴 倍数 1→50 ＝ y 1000→200，平移对数 y ∝ ln((m+9)/10)：
//    底部近似线性、顶部压缩；7% 曲线 10 年处只抬 42 px（几乎平），40 年处恰在 ×15（y≈606），10% 恰在 ×45（y≈238）；
//  坐标系正下方的带（y 1210–1560）：左边对比块（7% → 10%、上扬箭头、差 30 倍），右边两条秘诀（早开始／别中断，右缘对齐坐标系）。
// 场景共用的小工具（只在场景里用，不改 wb/common.js）：
//  L.count / L.cnt：数字滚动——里程表式，每位数字在格子里往上滚；起滚时数字从空白滚进来（不先停在起始值），
//    落定前最多滚到「终值减一」，落定那一帧终值整块出现并轻顿 0.24 s；落定时刻＝TMB.landOf(e)。
//  L.dot / L.tick：每个十年统一一个顺序——线长到 → 点上打墨点 → 横轴刻度与「N 年」 → 数字。
//  L.arrowQ：按给定控制点画一支二次曲线箭头（先贴平、后陡升的「上扬」形状）。
//  L.tag：记下每笔的原定起笔时刻（_t0），build 之后与 t0 比，就能数出被「一支笔只画一笔」顺延的笔数。
(() => {
const L = WB.L = {};
const LN = Math.log(5.9);
L.X = yr => 1800 + 45 * yr;                                   // 年数 → 世界 x
L.Y = m => 1000 - 800 * Math.log((m + 9) / 10) / LN;          // 倍数 → 世界 y（1→1000，50→200）
const curve = r => { const o = []; for (let i = 0; i <= 80; i++) { const yr = i / 2; o.push([L.X(yr), L.Y(Math.pow(1 + r, yr))]); } return o; };
L.c7 = curve(0.07);                                           // 曲线① 每年 7%（墨）
L.c10 = curve(0.10);                                          // 曲线② 每年 10%（红）
L.P7 = yr => [L.X(yr), L.Y(Math.pow(1.07, yr))];              // 7% 曲线上 yr 年那一点
L.P10 = yr => [L.X(yr), L.Y(Math.pow(1.10, yr))];
// ---- 标题列 ----
L.titleAt = [1160, 320, 130];                                 // 「复利曲线」左缘、基线、字号（宋体粗）
L.doodle = (() => { const o = []; for (let i = 0; i <= 32; i++) { const u = i / 32; o.push([1170 + 350 * u, 640 - 240 * (Math.exp(3.2 * u) - 1) / (Math.exp(3.2) - 1)]); } return o; })();
L.dot0 = L.doodle[L.doodle.length - 1];                       // 小曲线的红端点（B1 开讲时它滑到原点）
// ---- 坐标系正下方的带 ----
L.band = { pts: [1760, 1520, 110], gap: [2800, 1340, 150], rule1: [3460, 1340, 130], rule2: [3460, 1510, 130] };
// ---- 机位 ----
L.title = [1150, 180, 1700, 660];                             // B0 标题近景（取景框）
L.chart = [1150, 120, 3850, 1110];                            // B1–B3_01 坐标系（含标题列，约 0.62 倍）
// 右侧数字从上到下叠着 ×45、×15、×8、刻度字，取景的上缘只能落在它们之间的缝里（字不切半截、不贴上边）：
L.Bcam = [2833, 1135, 0.74];                                  // B3_02 下移：坐标系＋对比块（左缘 x≈1536，小曲线整个出画；上缘 y≈405，×45 整个出画、×15 离上边约 114 px）
L.Ccam = [3340, 1253, 0.95];                                  // B4_01 推到秘诀：左缘 x≈2330（「7% → 10%」整个出画），上缘 y≈685（×15 整个出画、×8 整个在画里）
L.all = [1150, 140, 3850, 1560];                              // 全板（标题列＋坐标系＋带）
// 全板机位：内容上沿 y 140 落在屏幕 115、下沿 y 1560 落在 865；左右在 110 px 安全区内
L.allCam = (() => { const [x0, top, x1, bot] = L.all, z = Math.min(1700 / (x1 - x0), 750 / (bot - top)); return [(x0 + x1) / 2, top + (540 - 115) / z, z]; })();
// ---- 数字滚动（终值只在落定那一帧出现） ----
L.count = (x, y, o) => {
  const { from, to, fmt, land, dur, col = WB.OR, size = 92, fam = WB.BODY, wt = '600', el } = o;
  const t0 = land - dur, font = `${wt} ${size}px ${fam}`, [pre, post = ''] = fmt.split('{:.0f}');
  const g0 = document.createElement('canvas').getContext('2d'); g0.font = font;
  const dw = g0.measureText('0').width, pw = g0.measureText(pre).width, nd = String(Math.max(from, to)).length;
  const xr = x + pw + nd * dw, wMax = pw + nd * dw + g0.measureText(post).width;                 // xr：数字右缘（固定）
  const last = to - 1, v0 = from - 0.6, ease = p => 1.5 * p - 0.5 * p * p;                        // 从「空白」（起始值下面 0.6 格）滚起
  const vAt = t => v0 + (last - v0) * ease(U.clamp((t - t0) / dur));
  const shown = t => t >= land ? to : Math.max(from, Math.floor(vAt(t) + 1e-9));
  const dig = (n, k) => (n < from) ? '' : (k === 0 || n >= Math.pow(10, k)) ? String(Math.floor(n / Math.pow(10, k)) % 10) : '';
  const s = WB.custom({ t0, t1: land, el, size, bb: [x - 10, y - size * 1.05, x + wMax + 10, y + size * 0.3], draw(g, q, t) {
    g.font = font; g.fillStyle = col; g.textBaseline = 'alphabetic'; g.textAlign = 'center'; g.globalAlpha *= U.clamp((t - t0) / 0.08);
    if (t >= land) { const u = (t - land) / 0.24; if (u < 1) { const k = 1 + 0.06 * Math.sin(u * Math.PI), cx = x + wMax / 2, cy = y - size * 0.35; g.translate(cx, cy); g.scale(k, k); g.translate(-cx, -cy); } }   // 落定那一帧轻顿
    const v = t >= land ? to : vAt(t), n = Math.floor(v + 1e-9), fr = t >= land ? 0 : v - n;
    let cells = n < from ? String(from).length : String(n).length;                     // 正在进位到多一位时，位数在 [len, len+1] 之间平滑过渡
    if (n >= from && fr > 0 && String(n + 1).length > cells) cells += fr;
    for (let kk = 0; kk < nd; kk++) {
      const cx = xr - (kk + 0.5) * dw, p = Math.pow(10, kk), r = n < from ? fr : (n % p === p - 1 ? fr : 0), a = dig(n, kk), b = dig(n + 1, kk);
      if (!r || a === b) { if (a) g.fillText(a, cx, y); continue; }
      g.save(); g.beginPath(); g.rect(cx - dw / 2 - 2, y - size * 0.95, dw + 4, size * 1.22); g.clip();
      if (a) g.fillText(a, cx, y - r * size * 1.15); if (b) g.fillText(b, cx, y + (1 - r) * size * 1.15); g.restore();
    }
    g.textAlign = 'right'; g.fillText(pre, xr - cells * dw, y); if (post) { g.textAlign = 'left'; g.fillText(post, xr, y); }
    return null; },
    textAt: t => t < t0 ? null : WB.fmt(fmt, shown(t)) });
  s.land = land; WB.texts.push(WB.fmt(fmt, to)); return s;
};
// cnt 模板：起跳＝念到那个数（落定前 0.6–1.3 s 之间），落定＝land_cue 末尾＋offset
L.cnt = (beat, el, x, y, o = {}) => {
  const e = TMB.ev(beat, el, 'count'), land = TMB.landOf(e);
  const t0 = Math.min(land - 0.6, Math.max(land - 1.3, WB.qb(beat, e.at)));
  const n = L.count(x, y, { from: e.from, to: e.to, fmt: e.fmt, land, dur: land - t0, el, ...o });
  WB.ev(beat, el, 'count', n, land - t0); return n;
};
L.tag = () => WB.S.forEach(s => { if (s._t0 == null) s._t0 = s.t0; });
// 十年一组：线长到那一刻 7% 曲线上打墨点（L.dot）；念到「N 年」时横轴上一道短刻 → 「N 年」砸入 → 一道淡虚线从刻度连到点（L.tick）
L.dot = (yr, t, el) => { const [x, py] = L.P7(yr);
  return WB.custom({ t0: t, t1: t + 0.17, el, bb: [x - 14, py - 14, x + 14, py + 14], draw(g, q) {
    g.fillStyle = WB.INK; g.beginPath(); g.arc(x, py, 9 * MO.slamK(q, 1.8), 0, Math.PI * 2); g.fill(); return null; } }); };
L.tick = (yr, at, el) => WB.group(el, () => {
  const x = L.X(yr), [, py] = L.P7(yr);
  WB.line([[x, 986], [x, 1016]], { t0: at - 0.14, dur: 0.08, w: 6, col: WB.SOFT, smooth: false });
  const p = WB.pop(`${yr} 年`, x, 1084, 66, { at, col: WB.SOFT, fam: WB.BODY, wt: '600', slam: true });
  if (986 - py > 40) WB.line([[x, 984], [x, py + 16]], { t0: at + 0.06, dur: 0.22, w: 3, col: WB.DIM, dash: [8, 10], smooth: false, handed: false });
  return p;
});
L.arrowQ = (a, c, b, o) => {
  const pts = WB.quad(a, c, b, 30), s1 = WB.line(pts, { t0: o.t0, dur: o.dur, col: o.col, w: o.w, amp: 1.2, el: o.el });
  const e = pts[pts.length - 1], p = pts[pts.length - 4], an = Math.atan2(e[1] - p[1], e[0] - p[0]), h = o.head ?? 36;
  const s2 = WB.line([[e[0] - Math.cos(an - 0.5) * h, e[1] - Math.sin(an - 0.5) * h], e, [e[0] - Math.cos(an + 0.5) * h, e[1] - Math.sin(an + 0.5) * h]],
    { t0: s1.t1 + 0.01, dur: 0.08, col: o.col, w: o.w, smooth: false, el: o.el });
  return [s1, s2];
};
})();

WB.chapter('B0', id => {
  const { OR, INK } = WB, L = WB.L;
  // 上翘小曲线：先贴着平、后面翘起来（第 0 帧已画到约四成）；线头红点砸下，B1 开讲时红点滑走（见 B1.js）
  const d = WB.line(L.doodle, { t0: -0.55, dur: 1.4, w: 9, col: INK, amp: 1.2, ease: MO.sineInOut });
  const [ex, ey] = L.dot0;
  const rd = WB.custom({ t0: d.t1, t1: d.t1 + 0.17, bb: [ex - 20, ey - 20, ex + 20, ey + 20], draw(g, q) { g.fillStyle = OR; g.beginPath(); g.arc(ex, ey, 14 * MO.slamK(q, 1.6), 0, Math.PI * 2); g.fill(); return null; } });
  rd.until = WB.T0('B1');
  const [tx, ty, ts] = L.titleAt;
  WB.text('复利曲线', tx, ty, ts, { t0: d.t1 + 0.12, rate: 6, wt: '700' });
  const c = WB.frame(L.title, { zmax: 1.1 });
  WB.cam0(c[0], c[1], c[2]);
  L.tag();
});
SCENES['B0'] = WB.scene;
