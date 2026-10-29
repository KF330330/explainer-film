// 节拍级口播对位 TMB：只在一个节拍的 say 里找词，须恰好出现一次；返回全片秒（含 3 s 片头）。
// TMB.cue(节拍, 词) = 这几个字开始被念出的时刻；TMB.end(节拍, 词) = 念完的时刻；TMB.vo(节拍) = [句首, 句尾]；
// TMB.land(cueId, offset=-0.15) = 子 cue 真实 end + offset（数字落定时刻）；TMB.ev(节拍, el, do) = timeline 里这条事件的原样参数。
// 找不到/不唯一/没有这个节拍 → console.error（render.py 把它算页面错误，渲完非零退出），返回句首时刻让页面还能画。
window.TMB = (() => {
  const B = key => { const b = TIMING.beats[key]; if (!b) { console.error(`TMB: 没有节拍 ${key}`); return null; } return b; };
  function find(key, w, which) {
    const b = B(key); if (!b) return 0;
    const i = b.text.indexOf(w);
    if (i < 0 || b.text.indexOf(w, i + 1) >= 0) { console.error(`TMB: 节拍 ${key} 的口播里「${w}」${i < 0 ? '找不到' : '出现不止一次'}`); return b.start; }
    return which === 'end' ? b.charEnd[i + w.length - 1] : b.charStart[i];
  }
  const land = (cueId, off = -0.15) => { const c = TIMING.cues[cueId]; if (!c) { console.error(`TMB: 没有子 cue ${cueId}`); return 0; } return c.end + off; };
  const ev = (key, el, act) => {
    const e = (TIMING.events[key] || []).find(x => x.el === el && (!act || x.do === act));
    if (!e) console.error(`TMB: 节拍 ${key} 没有事件 ${el}${act ? '·' + act : ''}`);
    return e || {};
  };
  // count 事件的落定时刻：land_cue 的真实 end ＋ land_offset（默认取 timeline motion.land_offset_default，再缺省 -0.15）
  const landOf = e => land(e.land_cue, e.land_offset ?? (TIMING.motion.land_offset_default ?? -0.15));
  return {
    cue: (key, w) => find(key, w, 'start'),
    end: (key, w) => find(key, w, 'end'),
    vo: key => { const b = B(key); return b ? [b.start, b.end] : [0, 0]; },
    land, ev, landOf,
  };
})();
