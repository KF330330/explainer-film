// 脚手架最小场景 B0（scripts/new_project.py 按 --title 生成）：第 0 帧板上已有一笔正在画的墨线（首帧不空），
// 随后标题一字一字写出（宋体粗、约 7.5 字/秒，最长 1.4 s）。相机不动：cam0(960, 540, 1) 时世界坐标＝屏幕坐标。
// 写真实分镜时整份重写本文件（范例见 skill 的 templates/styles/whiteboard/sample_scenes/B0.js）。
WB.chapter('B0', id => {
  const title = __TITLE_JSON__, n = [...title].length;
  let size = 124; const w0 = WB.measure(title, size, WB.FONT, '700'); if (w0 > 1500) size = Math.floor(size * 1500 / w0);
  const w = WB.measure(title, size, WB.FONT, '700'), x0 = 960 - w / 2, y = 470;
  WB.line([[x0, y + 62], [x0 + w * 0.5, y + 68], [x0 + w, y + 58]], { t0: -0.6, dur: 1.0, w: 8, col: WB.INK, amp: 1.4 });
  WB.text(title, 960, y, size, { t0: 0.45, dur: Math.min(1.4, Math.max(0.4, n / 7.5)), wt: '700', align: 'center' });
  WB.cam0(960, 540, 1);
});
SCENES['B0'] = WB.scene;
