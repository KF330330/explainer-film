// B3 · 曲线② 与对比块（口播第 5–6 句）。不拉回坐标系（B2 不推近），下移时不画红虚线。
// 「如果」→ 曲线②（红）从原点起长，一路长到「45 倍」开口时到 40 年（「如果把回报率提高到 10%，四十年是」整句都在长），红线头随之交给它；
// 「10%」→「每年 10%」（红）写在「每年 7%」上方；「45 倍」→ 线头右边 ×15→×45（字号放大 1.3 倍，与 ×15 同号）在「四十年是 45 倍」念完时落定。
// 「差的不是」→ 相机下移到「坐标系下半＋正下方的带」（落地时坐标系下半还在画里，不落到空纸）；
// 「3 个百分点」→ 带左写「7% → 10%」；「30 倍」→「差 30 倍」（红、大）砸入右上；
// 「差距」→ 一道红色上扬箭头从「7% → 10%」先贴平再陡升，指到「差 30 倍」下面（1.4 s，画到下一句「所以复利的」）。
WB.chapter('B3', id => {
  const { OR, BODY } = WB, L = WB.L, qb = WB.qb, B = L.band;
  // ================= B3_01：曲线②、每年 10%、×45 =================
  const ph10 = [[L.tC10, qb('B3_01', '45 倍') - 0.05, 0, 1]];
  const c10 = WB.grow(L.c10, ph10, { el: 'curve10', col: OR, w: 8, head: OR, seed: 9, ease: MO.sineInOut });
  WB.ev('B3_01', 'curve10', 'grow', c10, ph10[0][1] - ph10[0][0]);
  const r10 = WB.text('每年 10%', 1830, 795, 66, { t0: qb('B3_01', '10%') + 0.15, dur: 0.75, fam: BODY, wt: '600', col: OR, el: 'rate10' });
  WB.ev('B3_01', 'rate10', 'write', r10);
  L.cnt('B3_01', 'k40b', L.X(40) + 26, L.P10(40)[1] + 34, { size: 120 });
  // ================= B3_02：下移到带，对比块 =================
  const tm = qb('B3_02', '差的');
  WB.shotRect(tm, 0.9, L.chart, { cam: L.Bcam });
  WB.ev('B3_02', 'cam', 'camera', tm, 0.9);
  const [gx0, gy0, gs] = B.pts, [xx, xy, xs] = B.gap;
  const gp = WB.text('7% → 10%', gx0, gy0, gs, { t0: Math.max(qb('B3_02', '3 个百分点') + 0.2, tm + 0.9 + WB.SETTLE + 0.03), dur: 0.7, fam: BODY, wt: '600', el: 'gap_pts' });
  WB.ev('B3_02', 'gap_pts', 'write', gp);
  const gx = WB.pop('差 30 倍', xx, xy, xs, { at: qb('B3_02', '30 倍') + 0.3, slam: true, col: OR, wt: '700', el: 'gap_x' });
  WB.ev('B3_02', 'gap_x', 'pop', gx, 0.4);
  const a0 = [gp.x + gp.w + 28, gy0 - 30], tip = [xx - 70, xy + 42];
  const ga = L.arrowQ(a0, [tip[0] - 20, a0[1] + 6], tip, { t0: qb('B3_02', '差距') + 0.1, dur: 1.4, col: OR, w: 12, head: 36, el: 'gap_arrow' });
  WB.ev('B3_02', 'gap_arrow', 'draw', ga[0]);
  L.tag();
});
SCENES['B3'] = WB.scene;
