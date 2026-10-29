// B1 · 坐标系与曲线① 前十年（口播第 1–2 句）。
// 第一句一开讲（3.0 s）相机从标题近景拉远到坐标系（1.1 s），标题缩到板角；同时小曲线的红端点（笔尖）沿一道看不见的弧滑到原点，
// 不留线，停在原点等曲线① 起长（它就是后来曲线① 的红线头）。相机停稳 0.5 s 后：念到「横轴」笔从原点画横轴、「年数」写在箭头右边；
// 念到「纵轴」画纵轴、「多少倍」时写「本金的倍数」在纵轴顶旁。
// 第二句「前面十年几乎是平的」：曲线①（墨，每年 7%）从原点贴着底线慢慢长到 10 年处；线到即在点上打墨点；
// 「每年 7%」随口播写在平线上方；「十年才」→ 横轴 10 年刻度与「10 年」；「翻一倍」→「×2」在点左上砸入。
// 曲线① 是一整条按 x 长出的线：四段生长（B1_02 到 10 年、B2_01 到 20 年再到 30 年、B2_02 到 40 年）在这里一次排好，
// 各段起止记在 L.ph7，B2.js 用它登记事件、排墨点刻度与数字；红线头一直挂到曲线② 起长（L.tC10）时交出去。
// 每个十年统一「线到 → 点 → 刻度 → 数字」；10→20 年那段在「再往后」出口前 0.3 s 起长（×2 落定后不留 1.5 s 死帧）。
WB.chapter('B1', id => {
  const { OR, INK, SOFT, BODY, NUMF } = WB, L = WB.L, qb = WB.qb;
  // ---- 相机：标题近景 → 坐标系（标题缩到板角），停稳再起笔 ----
  const tc = WB.T0('B1');
  WB.shotRect(tc, 1.1, L.chart, { zmax: 0.9 });
  const t1c = tc + 1.1 + WB.SETTLE + 0.02;
  // ---- 曲线① 四段生长的起止（全片秒） ----
  const e20 = TMB.ev('B2_01', 'k20', 'count'), l20 = TMB.landOf(e20);
  const e30 = TMB.ev('B2_01', 'k30', 'count'), l30 = TMB.landOf(e30), s30 = Math.min(l30 - 0.6, Math.max(l30 - 1.3, qb('B2_01', e30.at)));
  const tD = qb('B2_02', '四十年') + 0.1;
  L.ph7 = [
    [qb('B1_02', '前面') + 0.2, qb('B1_02', '平的') + 0.5, 0, 0.25],          // 0→10 年：「前面十年几乎是平的」整句贴着底线爬
    [qb('B2_01', '再往后') - 0.3, qb('B2_01', '二十年') + 0.19, 0.25, 0.5],   // 10→20 年：×2 落定后就接着长，「再往后，线开始抬头」时正在抬
    [l20 + 0.06, Math.min(l20 + 0.86, s30 - 0.55), 0.5, 0.75],                // 20→30 年：×4 落定后长，「8 倍」起滚前 0.55 s 到 30 年
    [tD, tD + 1.2, 0.75, 1],                                                   // 30→40 年
  ];
  L.tC10 = qb('B3_01', '如果') + 0.2;                                          // 曲线② 起长（红线头交给它）
  // ---- 笔尖红点：小曲线红端点 → 原点（随相机拉远一起走，不留线；算引线，不受「停稳再落笔」限制），停在原点直到曲线① 起长 ----
  const [sx, sy] = L.dot0, path = WB.quad([sx, sy], [1720, 560], [1800, 1000], 40), pc = DG.cum(path);
  const pdot = WB.custom({ t0: tc, t1: tc + 1.0, until: L.ph7[0][0] + 0.02, bb: WB.bbOf(path, 20), draw(g, q, t) {
    const [x, y] = DG.pointAt(path, pc, pc[pc.length - 1] * MO.sineInOut(q)); g.fillStyle = OR; g.beginPath(); g.arc(x, y, 13, 0, Math.PI * 2); g.fill(); return null; } });
  pdot.lead = true;
  // ---- 横轴（从原点起笔）、「年数」 ----
  const ax = WB.line([[1800, 1000], [3690, 1000]], { t0: Math.max(qb('B1_01', '横轴') + 0.2, t1c), dur: 0.9, w: 6.5, amp: 1.0, el: 'axis_x', ease: MO.smooth });
  const axh = WB.line([[3660, 983], [3694, 1000], [3660, 1017]], { t0: ax.t1 + 0.02, dur: 0.12, w: 6.5, smooth: false, el: 'axis_x' });
  WB.ev('B1_01', 'axis_x', 'draw', ax);
  const lx = WB.text('年数', 3712, 1024, 66, { t0: Math.max(qb('B1_01', '年数') + 0.2, axh.t1 + 0.04), dur: 0.36, wt: '700', el: 'label_x' });
  WB.ev('B1_01', 'label_x', 'write', lx);
  // ---- 纵轴、「本金的倍数」 ----
  const ay = WB.line([[1800, 1000], [1800, 150]], { t0: Math.max(qb('B1_01', '纵轴') + 0.1, lx.t1 + 0.04), dur: 0.9, w: 6.5, amp: 1.0, el: 'axis_y', ease: MO.smooth });
  const ayh = WB.line([[1783, 182], [1800, 148], [1817, 182]], { t0: ay.t1 + 0.02, dur: 0.12, w: 6.5, smooth: false, el: 'axis_y' });
  WB.ev('B1_01', 'axis_y', 'draw', ay);
  const ly = WB.text('本金的倍数', 1838, 212, 66, { t0: Math.max(qb('B1_01', '多少倍') + 0.1, ayh.t1 + 0.1), dur: 0.7, wt: '700', el: 'label_y' });
  WB.ev('B1_01', 'label_y', 'write', ly);
  // ---- 曲线① ----
  const c7 = WB.grow(L.c7, L.ph7, { el: 'curve7', col: INK, w: 8, head: OR, headUntil: L.tC10, seed: 5, ease: MO.sineInOut });
  WB.ev('B1_02', 'curve7', 'grow', c7, L.ph7[0][1] - L.ph7[0][0]);
  L.dot(10, L.ph7[0][1] + 0.02, 'tick10');                                    // 线到 → 点
  // ---- 每年 7%：写在平线上方 ----
  const r7 = WB.text('每年 7%', 1830, 890, 66, { t0: qb('B1_02', '每年') + 0.25, dur: 0.55, fam: BODY, wt: '600', el: 'rate7' });
  WB.ev('B1_02', 'rate7', 'write', r7);
  L.r7 = r7;
  // ---- 十年才翻一倍：10 年刻度与「10 年」；「×2」在点左上砸入 ----
  const p10 = L.tick(10, qb('B1_02', '十年才') + 0.3, 'tick10');
  WB.ev('B1_02', 'tick10', 'pop', p10, 0.3);
  WB.pop('×2', 2236, 910, 92, { at: qb('B1_02', '翻一倍') + 0.25, col: OR, fam: BODY, wt: '600', slam: true, align: 'right', el: 'tick10' });
  L.tag();
});
SCENES['B1'] = WB.scene;
