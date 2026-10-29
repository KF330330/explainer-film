// B4 · 收尾（口播第 7–8 句）。
// 「秘诀」→ 相机缓推到带的右半（0.9 s；落地时画面里有坐标系右下、「差 30 倍」和箭头，不是空纸），停稳后
// 「早开始」「别中断」随口播一条一条写在带右边（上下两行，右缘对齐坐标系）。
// 「前十年」→ 相机拉远到「标题列＋坐标系＋带」的紧框（约 0.53 倍，图表里最小的字约 35 px；1.2 s，起步快、长尾落定）；
// 「不动」→ 曲线① 前十年那段平线描粗变红（只动线、不加圈）；「攒劲」→ 两条秘诀下各一道红线。写完静持到片尾（≥1.2 s，全片唯一冻结）。
WB.chapter('B4', id => {
  const { OR } = WB, L = WB.L, qb = WB.qb, B = L.band;
  // ================= B4_01：推到秘诀，两条秘诀 =================
  const tc = qb('B4_01', '秘诀');
  WB.shotRect(tc, 0.9, L.chart, { cam: L.Ccam });
  WB.ev('B4_01', 'cam', 'camera', tc, 0.9);
  const [r1x, r1y, r1s] = B.rule1, [r2x, r2y, r2s] = B.rule2;
  const r1 = WB.text('早开始', r1x, r1y, r1s, { t0: Math.max(qb('B4_01', '早开始') + 0.1, tc + 0.9 + WB.SETTLE + 0.03), dur: 0.5, wt: '700', el: 'rule1' });
  WB.ev('B4_01', 'rule1', 'write', r1);
  const r2 = WB.text('别中断', r2x, r2y, r2s, { t0: qb('B4_01', '别中断') + 0.1, dur: 0.5, wt: '700', el: 'rule2' });
  WB.ev('B4_01', 'rule2', 'write', r2);
  // ================= B4_02：拉远到紧框；前十年描红；秘诀下划线；静持 =================
  const tz = qb('B4_02', '前十年');
  WB.shotRect(tz, 1.2, L.all, { cam: L.allCam, ease: MO.longTail, declip: false });
  WB.ev('B4_02', 'cam', 'camera', tz, 1.2);
  const flat = L.c7.filter(([x]) => x <= L.X(10) + 1e-6);
  const hl = WB.line(flat, { t0: Math.max(qb('B4_02', '不动') + 0.1, tz + 1.2 + WB.SETTLE + 0.03), dur: 0.8, w: 18, col: OR, amp: 0.6, el: 'flat_ring', ease: MO.smooth });
  WB.ev('B4_02', 'flat_ring', 'circle', hl);
  const ut = qb('B4_02', '攒劲') + 0.05;
  const u1 = WB.line([[r1.x - 8, r1y + 24], [r1.x + r1.w / 2, r1y + 29], [r1.x + r1.w + 8, r1y + 22]], { t0: ut, dur: 0.2, w: 14, col: OR, amp: 1.2, el: 'rule_under' });
  const u2 = WB.line([[r2.x - 8, r2y + 24], [r2.x + r2.w / 2, r2y + 29], [r2.x + r2.w + 8, r2y + 22]], { t0: ut + 0.22, dur: 0.2, w: 14, col: OR, amp: 1.2, el: 'rule_under' });
  WB.ev('B4_02', 'rule_under', 'underline', [u1, u2], 0.42);
  L.tag();
});
SCENES['B4'] = WB.scene;
