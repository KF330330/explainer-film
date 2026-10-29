# 画法 whiteboard · 白板手绘 —— 场景惯用语

> 给场景编写代理读（`references/scene-brief.md`「本片画法」）。白板＝`templates/common.js` 的缺省画法，`style.js` 只记名字、钩子全缺省；
> 骨架、对位、相机与常用件的完整写法见 `references/scene-writing.md`，范例场景在本目录 `sample_scenes/`（复利曲线片 B0–B4）。

## 惯用语

- 一整块板、一台相机：`B0.js` 顶部定 `WB.L` 版式（世界坐标），各段只往板上排笔画与相机键；转场＝相机在板上移动。
- 念到才起笔：`t0 = Math.max(WB.qb(拍, '词') + 0.1~0.3, 上一笔.t1 + 0.04)`；每个 timeline 事件 `WB.ev(拍, el, do, 笔画, dur)` 登记。
- 字：标题宋体粗（`WB.FONT`，`wt: '700'`，约 7.5 字/秒）、标签与正文苹方（`WB.BODY`，14–16 字/秒）、大数字 `WB.NUMF` 或苹方粗；重点词 `WB.pop(..., { slam: true })` 砸入。
- 颜色只用令牌：`WB.INK`（正文、轴、线）、`WB.OR`（唯一强调红：重点词、数字、线头点、圈与下划线）、`WB.SOFT`／`WB.DIM`（刻度、辅助虚线）、`WB.CARD`（卡面）。
- 线：`WB.line`（手抖、按笔速画）、`WB.grow`（按 x 推进的曲线，财经图表语法）、`WB.arrow`／`WB.lead`（引线可在运镜里画）、`WB.ring`／`WB.under`／`WB.strike`。
- 数字：落定时刻用 `TMB.landOf`、终值只在落定帧出现。要里程表式滚数用 `WB.roll`＋rcnt 模板（`references/parts.md` 第十三节）；`sample_scenes/B0.js` 的 `L.count`／`L.cnt` 是早期写法（滚到一半数位硬切成半截），只看它怎么取落定时刻，不照抄滚动画法。
- 收尾：拉远到全板紧框，静持 ≥1.2 s（全片唯一允许的冻结）；拉远在末句口播里做完，末 cue 结束 +0.2 s 起到片尾不再有任何运动（见 `references/scene-writing.md`「相机」节）。

## 反 PPT 清单

- 不要每镜同一个动作（每句换一种动词：画、写、砸、滚、圈、划、长）；不要一镜多个东西同时入场。
- 不要装饰性假动：全员呼吸、字漂浮、匀速慢推；相机停留时 creep 0，画面的「活」只来自正在写的字、正在画的线、正在滚的数。
- 不要三张卡像 bullet；不要拐点堆红（红只给本句的重点）；不要贴边裁半；不要无内容推拉；不要笔比相机先动。
- 装饰性持续动作若真要加，必须经 `WB.ambientT(t)` 取时间（QA 锁相机时冻结），且不能代替内容揭开。

## 签名特征落到哪个 WB 调用

| style.json signature | 落在 |
|---|---|
| 暖纸板面＋纸纹＋点阵、版面光 | `WB.STYLE.ground = null` → `common.js` 的 `drawBoard` 纸面（主题 `board`、`paper.*`） |
| 墨＋唯一强调红 | 场景里只用 `WB.INK`／`WB.OR`／`WB.SOFT`／`WB.DIM`（主题 `ink`、`accent`、`soft`、`dim`）；style_lint 挡住写死的颜色 |
| 笔顺手写、字微转微抖 | `WB.STYLE.text = 'hand'`、`jitter = 1` → `WB.text`／`WB.pop`（`drawOne` 的笔顺遮罩与 `put` 抖动） |
| 线带手抖、按笔速、一支笔 | `WB.line`（`DG.hand` amp×jitter、`SPEED`）；`WB.build` 的「一支笔同时只画一笔」顺延 |
| 一块板一台相机、停稳再起笔 | `WB.shotRect`／`WB.travel`／`WB.move`（creep 0）；`WB.build` 把运镜里的起笔顺延到 `WB.SETTLE` 之后 |
| 念到才起笔、1.5 s 内有笔动 | `WB.qb`＋`WB.ev`；QA `semantic`、`pen_idle` |
| 数字落定、砸入 | `L.cnt`／`WB.count`（`TMB.landOf`）、`WB.pop({ slam: true })`；QA `count_land` |
| 字幕带纸卡底 | 主题 `caption.*` → `GLOBAL_OVERLAY` |
