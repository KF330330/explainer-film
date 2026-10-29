# 通用件：templates/parts.js（1.3.0 六件＋1.3.1 九件＋1.3.2 一件＋1.3.3 两件）

> 何时读：派场景代理前（任务书里写「必读 parts.md」）；场景里要摆实物摞、走动的小人、原件卡，或跨区远行运镜时；讲流程的片子要机器、题卡、对照表、封存、日历、步骤环时（五～十二节）；数字要里程表式滚上去时（十三节）；全片按页排、要换页时（十四节）。

`new_project.py` 把 `templates/parts.js` 复制到 `engine/<片名>/wb/parts.js`，经 `project.json` 的 `libs` 排在 SCENE_LIBS 最后加载（`wb/common.js`、`wb/style.js` 之后，场景之前），场景里直接用 `WB.<件名>`。
1.3.0 六件、1.3.1 九件分别取自两支样片的场景，样片专属的写法、写死的版式与时刻都改成了参数，缺省值取样片里的值。工程里那份是**副本**：升级 skill 不会改已有工程；要用新版就手动重拷，拷前看一眼工程有没有改过它。
各件都只在 WB 上挂新名字、颜色只走 `WB.C.*`、不用无种子随机数；**上屏字由调用者定，件不自带字**（标签、步骤字、表头字用 `WB.text`／`WB.pop` 自己写）；场景代码照旧守 `scene-brief.md` 的规矩。

## 一、WB.stack：一摞任意物件（数字落到东西上）

`WB.stack({x, y, n0, n1, t0, t1, el, w=150, h=18, item=WB.coinDraw})` → 自定义件；另挂 `topAt(t)`（当前摞顶 y）、`topN(n)`（n 件时的摞顶 y）。

- 底部中心 `(x, y)`；t0 前不画，t0 起已有 n0 件（0.12 s 淡入）；t0–t1 件数从 n0 缓动到 n1，第 k 件在数到 k+1 那一刻落地（落地前约 0.2 s 从高处加速落下）。
- `item(g, cx, yt, rx, ry, h, lw, acc)` 画一件：顶面中心 `(cx, yt)`、半宽 `rx = w/2`、顶面半高 `ry ≈ 0.16·w`、厚 `h`、线宽 `lw`，`acc` 为真＝已落地的最上一件（加强调）。缺省 `WB.coinDraw`（一枚硬币，也可单独在 `WB.custom` 的 draw 里调）。
- 包围盒 `bbAt(t)` 跟着摞高走；`act` 只覆盖 t0–t1；带 `jump:'coins'`（qa 的 jumps 认作有意跳变）。摞本身不报字，旁边的数字用 `WB.count`（或场景自己的数字模板），登记 `count` 事件。
- **`geom`（1.3.1，只加不改）**：`s.geom = {rx, ry, lw, h, itemTop(k), x, y, item, nAt(t)}`。`itemTop(k) = y − (k+1)·h` 是第 k 件（从 0 起）落定后的顶面中心 y，就是 item 收到的 `yt`；它和 `topN(k+1)`（k+1 件时外轮廓顶缘）差一个 `ry`：`topN(k+1) = itemTop(k) − ry`。要算摞上某一件的位置（抽卡、飞卡的起点）用它，别再自己重算 `ry = round(w·0.16)`。`x、y、item、nAt` 给 `WB.sealBox` 的 `feed` 用。卡片摞的画法用 `WB.cardItem`（第八节）。

```js
const e = TMB.ev('B2_01', 'k10', 'count'), land = TMB.landOf(e);                                       // 数字落定时刻（timeline 的 land_cue）
const s10 = WB.stack({ x: L.X3(10), y: L.base3, n0: 1, n1: 2, t0: land - 1.0, t1: land, el: 'stack10' });   // 最后一枚与 ×2 同一帧落定
const k10 = WB.count(L.X3(10), s10.topN(2) - 60, { from: e.from, to: e.to, fmt: e.fmt, land, dur: 1.0, align: 'center', el: 'k10' });   // 数字写在摞顶上方
WB.ev('B2_01', 'k10', 'count', k10, 1.0);
// 一摞题卡：换 item 就行（卡片顶面＋厚边，最上一张描强调色边）
const card = (g, cx, yt, rx, ry, h, lw, acc) => { g.beginPath(); g.roundRect(cx - rx, yt - ry, rx * 2, ry + h, 6);
  g.fillStyle = WB.C.card; g.fill(); g.strokeStyle = acc ? WB.C.accent : WB.C.ink; g.lineWidth = lw; g.stroke(); };
WB.stack({ x: 900, y: 2200, n0: 3, n1: 4, t0, t1, el: 'pile', w: 260, h: 16, item: card });
```

## 二、WB.walker：走动的小人

`WB.walker({keys:[[t, x, y, pose, expr, tag], …], s=62, el='walker', look=tag=>造型, label=tag=>字|null, blinkUntil=window.TIMING.total})` → 自定义件（`pos(t)`＋`ext`、`textAt`、`act`）。

- 相邻两帧位置不同＝缓动走过去（脚下随步子轻跳），相同＝站着；`pose` 只能 `rest/talk/point/shrug`、`expr` 只能 `happy/blank/shock`（越界 console.error）。换姿势经 `TOON.poseAt` 快切。
- `tag` 是这一帧的标签，交给 `look` 与 `label`：`look` 缺省 `tag => ({base:'neutral', shirt: WB.C.accent, pants: WB.C.ink})`；`label` 缺省不挂名牌，给了就在脚下挂圆角名牌（字号 max(58, 0.6·s)），起步收起旧字、到站 0.2 s 弹出新字，`textAt` 报 `{text, bb}`。
- 眨眼按 el 定的种子排时刻表，排到 `blinkUntil`（缺省全片时长 `TIMING.total`）；眨眼与呼吸走 `WB.ambientT`（QA 锁相机时冻结）。`act` 只覆盖走动与换姿势。
- 口播结束后画面里还有 `WB.walker`、TOON 角色眨眼呼吸，或三维装饰摆动时，`still_video_source` 设 `noambient_draft`；否则片尾噪声会把阈值 K 抬高（曾有样片被抬到 99）。
- 关键帧在建板完成后才读：同一个 `keys` 数组，后面的段可以改某一项或追加（如收尾时让书桌边的小人抬手）。不许用作者形象（`char:'author'`）。

```js
WB.walker({ keys: L.keys3, s: 94, el: 'saver',                       // 例：存钱小人，年龄名牌、55 岁起灰发、65 岁戴眼镜
  look: tag => ({ base: 'neutral', shirt: WB.C.accent, pants: WB.C.ink, hair: tag >= 55 ? WB.C.dim : WB.C.ink, glasses: tag >= 65 }),
  label: tag => tag + ' 岁' });
WB.walker({ keys: [[t0, 520, 1000, 'talk', 'happy']], s: 90, el: 'expert', look: () => ({ base: 'neutral', shirt: WB.C.accent, pants: WB.C.ink, glasses: true }) });
```

## 三、WB.docCard：原件卡（内容本身的材料：论文页、原画、老照片、文献、产物截图）

什么能上这张卡，以 `templates/脚本与分镜.md` 第 5 行、`scene-brief.md`、`templates/CREDITS.md` 里的长版说法为准：只上内容本身的材料，谐音、同名、装饰性古画古书不算；没有就写「无原件：原因」，不用这张卡。

`WB.docCard({src, rect:[x, y, w, h], title='', lines=[], credit='', t0, reveal='wipe', until=null, el, base=null, minPx=32})`
→ `{face, image, titles, lines, credits, base, bb, t1, colX, colW, lineBB(i, from=0)}`。

- `rect` 是**左上角＋宽高**。卡面铺满 rect（衬框＋两条胶带），左 55% 放原件（contain、缓推到 1.06 倍），右栏：标题（宋体粗，放不下在「 · 」处折行）、正文行、右下角出处小字。t0 起 0.6 s 自左向右擦开（`reveal:'fade'` 淡入），`until` 起整卡消失。
- 图片必须登记在 `project.json` 的 `assets`，并在 `CREDITS.md` 有一行；`credit` 必填，写成「片中角注」那一句。
- **字号**：`minPx`＝屏上最小字高。最小字号 `mn = ⌈⌈minPx/0.85⌉ ÷ z⌉`，z 取 `WB.camAt(t0).z`（擦入那一刻，只算一次）；出处用 mn，正文约 1.5·mn，标题约 1.75·mn。右栏正文压到出处时 console.warn——这时加高 rect、删一行、缩短出处，或让 t0 时相机推得更近（见经验 2）。
- **`base`**：给一个早于 t0 的时刻（不早于就报错），那时先摆一张空卡底（同一画法同一位置，0.2 s 淡入，el＝`<el>.base`）。空卡底只画卡面、边框和两条胶带，不画放图的灰色衬框（1.3.1 起；衬框随卡面擦开一起出现——1.3.0 的空卡底先冒出一块灰框，两次审片都说像图没加载）；t0 擦开时空卡底只留刀口右边还没擦到的部分，擦完撤掉。用途：相机落到这一区时画面里已有一张等着放原件的空卡，不停在空纸上（「落地画面须已有主体」）。
- `lines` 每项是字串（随卡印出）或 `{text, el, how:'write'|'pop', t0|at, dur, rate, col}`（手写／整行砸入）。`lineBB(i, from)` 给第 i 行从第 from 个字起的世界框，圈字用。

下例只示调用；图要和标题对得上（标题写遗嘱，就放遗嘱原页的图，不放人物肖像）。

```js
const card = WB.docCard({ src: 'img/franklin_1785.jpg', rect: L.card5, title: '1789 年 · 富兰克林的遗嘱',
  lines: [{ text: '按 5% 放贷滚存', how: 'pop', at: tF + 0.75, col: WB.C.ink, el: 'will1' }],
  credit: '约瑟夫·杜普莱西斯《本杰明·富兰克林像》约 1785 · 公有领域 · 维基共享资源', t0: tF, base: L.tCamB5 - 0.3, el: 'doc_franklin' });
[card.face, card.image, ...card.titles, ...card.credits, ...card.lines].forEach(s => { s.camOk = true; });   // 落地后慢推中擦入时标 camOk
WB.ev('B4_01', 'doc_franklin', 'wipe', card.face, 0.6);
```

## 四、WB.trip 与 WB.retire

- `WB.trip(t, dur, rect, o={})` → 落点 `[x, y, z, bb]`：同 `WB.travel`（途中先拉远再推近、中点不停），但**不做 declip**，落点就是 `WB.frame(rect, o)`——已撤掉的字不会把相机推歪。`rect` 是**两角坐标** `[x0, y0, x1, y1]`（同 `WB.frame`，与 docCard 的 rect 不同）；`o.out` 中点缩放倍数（缺省 0.72）、`o.whip` 甩镜模糊，其余键交给 `WB.frame`。照例 `WB.ev(拍, 'cam', 'camera', t, dur)`。
- `WB.retire(n0, t)`：`WB.S.slice(n0)` 的笔画在 t 一起撤掉（已有更早 until 的不改）。进区前记 `const n0 = WB.S.length`，离开这一区、相机落到别处后撤：收尾拉远时旧区的东西不会露在画里。

```js
const n3 = WB.S.length;  /* …区三的摞、小人、数字… */
WB.trip(L.tCamB3, 0.9, L.R2); WB.ev('B3_01', 'cam', 'camera', L.tCamB3, 0.9);
WB.retire(n3, L.tCamB3 + 1.0);                                       // 相机回到区二之后撤掉区三
```

## 五、WB.popIn：弹入（1.3.1）

`WB.popIn(s, t0, dur, ax, ay)` → s：给一个自定义件套一层「t0 起 dur 秒从锚点 `(ax, ay)` 放大回弹出现」（`MO.backOut(u, 2.2)`，前 1/4 段淡入）；`act` 补上 `[t0, t0+dur)`（原有 act 照留），`jump` 没设就记 `'pop'`。

- 锚点：站在地上的东西（机器、小人、锁）取底边中心或挂点，挂在墙上的（日历）取中心。`WB.machine`、`WB.calendar`、`WB.sealBox` 内部已用它，不用再套。
- 上屏字由调用者定，件不自带字。

```js
const exp = WB.walker({ keys: L.expKeys, s: 82, el: 'expert', look: () => ({ base: 'neutral', shirt: WB.C.accent, pants: WB.C.ink, glasses: true }) });
WB.popIn(exp, tE, 0.35, E.x, E.y);                                   // 「最懂行」老手从脚底弹出
WB.ev('B1_02', 'expert', 'pop', exp, 0.35);
```

## 六、WB.shape：手画形状（1.3.1）

`WB.shape(type, x, y, r, o={})` → `WB.sketch` 的结果 `{s, t0, t1}`：`type` 为 `'circle'`、`'tri'`、`'square'`，中心 `(x, y)`、半径 `r`；`o` 原样交给 `WB.sketch`（`t0`、`dur`、`el`，`col` 缺省 `WB.C.ink`，`w` 缺省 `r/6`）。别的 type 直接报错。

- 用途：「答案」这类抽象的东西用形状代替（对照表里老手和机器各画一个形状，一样就对、不一样就错），不用写字。
- 上屏字由调用者定，件不自带字。

```js
WB.shape('tri', 1350, 1850, 36, { t0: tSys + 0.2, dur: 0.16, el: 'table' });
```

## 七、WB.machineDraw 与 WB.machine：方盒机器（1.3.1）

`WB.machineDraw(g, [x, y, w, h], {face=1, flash=0, busy=null, slot=true, slotR=false})`：只画不登记（同 `WB.coinDraw`，在 `WB.custom` 的 draw 或表头回调里调）。方盒底边站在 `y+h`（两只脚），屏幕面 `C.board`、两个按钮＋一道散热线；`face` 屏上眼睛与嘴的亮度 0..1、`flash` 屏幕闪光 0..1（铺一层 `C.wash`）、`busy` 屏幕下沿进度条 0..1（null 不画）、`slot` 顶上的进纸口（缺省画，同样片）、`slotR` 右侧出口（缺省不画；做完的东西从机器右边出来时开）。线宽 `max(3, w·0.0214)`（280 宽时约 6），屏框、按钮、脚、圆角按 280 宽时的样片值等比缩放。

`WB.machine({box, el, t0, until=null, pop=0.4, faceAt=null, flashAt=[], flashDur=0.45, busy=null, hopAt=[], slotR=false})` → 自定义件（`slotR` 原样透传给 machineDraw）：

- `pop` 秒数：t0 起 `WB.popIn`（锚点底边中心）；`null` 直接出现。`faceAt(t)` → 0..1，缺省恒 1（它在变的时刻自动并进 `act`）。
- `flashAt` 每个时刻屏幕闪一次（sin 脉冲 `flashDur` 秒）；`hopAt` 每个时刻一跳（以底边中心放大到 1.18 倍再回来，0.45 s，同时闪）。
- `busy: [b0, b1]`：进度条在 b0–b1 走满，满格停 0.3 s 后收起（与样片同）；`[b0, 收起后 0.1 s)` 都在 `act` 里，件带 `jump`，收起那一下 qa 认作有意跳变。
- `act` 由以上窗口合成；静态 `bb`＝box 外扩（有 `hopAt` 时按 1.18 倍再外扩）。
- 上屏字由调用者定，件不自带字（「出考卷」那类红字自己写在机器上方）。

```js
const M = [1010, 650, 280, 350];                                      // 区一：x 1010–1290，底边＝地面 y 1000
const mac = WB.machine({ box: M, el: 'machine', t0: tMac, pop: 0.4, faceAt: t => U.clamp((t - tFace) / 0.35), flashAt: [tIn] });
WB.ev('B1_01', 'machine', 'pop', mac, 0.4);
WB.machine({ box: [3990, 1780, 320, 370], el: 'machine4', t0: pre, pop: null, flashAt: [tAin], busy: [tFlow, tFlow + 1.2], slotR: true });   // 「机器自己」跑进度条，做完的卡从右侧出口出来
```

## 八、WB.cardItem：卡片一摞的画法（1.3.1）

`WB.cardItem({rules, mark=null, thin=false, accEdge})` → `WB.stack` 的 item 函数 `(g, cx, yt, rx, ry, h, lw, acc)`。合并样片三种画法，**缺省值随画法走**（每种缺省＝样片原样），显式给的 `rules`、`accEdge` 照用：

| 调用 | 画法 | rules 缺省 | accEdge 缺省 | 样片原名 |
|---|---|---|---|---|
| `WB.cardItem()` | 题卡：顶面＋厚边，顶面横线（最后一道短），最上一张描强调色边 | 3 | true | `L.cardItem` |
| `WB.cardItem({mark:'tick'})` | 做完的卡：顶面一个墨色勾 | 0 | false | `L.doneItem` |
| `WB.cardItem({thin:true})` | 考卷（薄纸）：只有最上一张画强调色题头线＋通栏横线 | 2 | false | `L.paperItem` |

- 颜色 `C.card／ink／accent／line`；圆角按半宽比例。`mark` 只认 `'tick'`。
- 上屏字由调用者定，件不自带字。

```js
const qA = WB.stack({ x: 3480, y: 650, n0: 12, n1: 12, t0: tPre2, t1: tPre2, el: 'qstack', w: 340, h: 24, item: WB.cardItem() });
WB.stack({ x: 4440, y: 2150, n0: 1, n1: 8, t0: tEnough, t1: tEnough + 0.7, el: 'done', w: 220, h: 22, item: WB.cardItem({ mark: 'tick' }) });
```

## 九、WB.compareTable：两列对照表（1.3.1）

`WB.compareTable({rect:[x0, y0, x1], hy, rh, n, cx:[左列, 右列, 标记列], cl:[分隔线 x…], left:[type…], right:[type…], heads=[], tPre, tRight, tMarks, tRings, el={table:'table', ticks:'ticks', cross:'cross'}})`
→ `{rowY(i), bad, strokes:{frame, left, right, marks, rings}, t1}`。

- 表顶 `y0`、表头下沿 `hy`、行高 `rh`、`n` 行（表底＝`hy + rh·n`）；`left`、`right` 是每行的形状（`WB.shape` 的 type），`bad`＝`left[i] !== right[i]` 的行号，自动算。
- 时刻：`tPre` 起 0.2 s 画表框（外框、表头线、分隔线、行线），左列形状每个间隔 0.06 s 跟着画（el＝`${el.table}_e`）——表框与左列是镜头外预摆，不占「一支笔」；`tRight` 起右列逐行（每个 0.16 s、间隔 0.2 s）；`tMarks` 起标记列一致打勾、不一致打叉（每个 0.18 s、间隔 0.21 s）；`tRings` 起只给叉画红圈（每个 0.25 s、间隔 0.29 s）。
- 勾、叉、形状、红圈按 `rh` 的比例取（rh 100 时依次 76、64、36、圈框 68×68 外扩 10），线宽同比。红圈只在标记格内，格窄时自动收小，不跨列。
- `heads[i]＝(g, [x, y, w, h]) => void` 画第 i 列的表头图标（第 i 格，表顶到表头线），裁在格内，用一个 `nopen` 的 custom 登记，并进 `strokes.frame`。表头要一跳一闪的，另用 `WB.machine({…, pop: null, hopAt: [t]})` 摆在表头格里。
- 上屏字由调用者定，件不自带字（表头写不写字由调用者定，上屏字 ≤8）。`el` 可只给要改的键。运镜与 `WB.ev` 由调用者登记。

```js
const T = WB.compareTable({ rect: [300, 1680, 2350], hy: 1800, rh: 100, n: 5, cx: [650, 1350, 2025], cl: [1000, 1700],
  left: ['circle', 'tri', 'square', 'circle', 'tri'], right: ['circle', 'tri', 'circle', 'circle', 'square'],
  heads: [(g, [x, y, w, h]) => { TOON.bean(g, { x: x + w / 2, y: y + h + 60, s: 50, char: { base: 'neutral', shirt: WB.C.accent, pants: WB.C.ink, glasses: true }, pose: TOON.POSES.rest, expr: 'happy' }); }],
  tPre: L.tCam3 - 0.6, tRight: tSys, tMarks: tTick, tRings: tRing });
WB.machine({ box: [1300, 1692, 100, 104], el: 'table', t0: L.tCam3 - 0.6, pop: null, hopAt: [tSysIcon] });   // 机器那一列的表头：「让系统」时一跳
WB.ev('B2_02', 'table', 'draw', T.strokes.right, 1.0);
WB.ev('B2_02', 'ticks', 'draw', T.strokes.marks, 1.0);
WB.ev('B2_02', 'cross', 'circle', T.strokes.rings, 0.64);
```

## 十、WB.sealBox：信封、抽屉、锁（1.3.1）

`WB.sealBox({env:{cx, cy, w, h}, cab:[x, y, w, h], t:{cab, env, close, drawer, lock}, open=null, el='seal', feed=null})`
→ `{tray, env, cards, stamp, cabinet, lock, envAt(t), t1}`。侧面看的文件柜（抽屉朝左拉出）＋信封。

- 时刻：`t.cab` 起柜子与拉开的托盘自上而下显现 0.35 s；`t.env` 起信封 popIn 0.25 s（盖子开着朝上）；`t.close` 起盖子 0.15 s 合上，+0.25 红火漆砸上（slam，无字），火漆跟着信封走；`t.drawer` 起信封 0.3 s 沿弧线滑进托盘，+0.3 托盘 0.35 s 推回柜里；`t.lock` 起锁 popIn 0.3 s，挂在抽屉把手上。
- 托盘纵向位置、拉出距离 `open`（缺省 `cab.w·0.737`）、锁与火漆尺寸都按 `cab`、`env` 的比例推（cab 380×270、env 260×160 时与样片一致）。
- 内部固定按「托盘 → 信封 → 卡片 → 火漆 → 柜子 → 锁」创建：柜子压住推进去的托盘与信封。
- `feed={stack, n, at}`（可选）：at 起从 `stack` 摞顶飞 n 张进信封口（间隔 0.12 s、每张 0.55 s，最后 20% 淡出），用摞自己的 item 画，起点取 `stack.geom`。`stack` 传「拿走之前」那一摞；摞要变少照经验 9 换摞。不给 feed 时 `cards` 为 null。
- el 依次为 `${el}.tray/.env/.cards/.stamp/.cab/.lock`（`WB.dimEl(el, …)` 能一起压淡）。上屏字由调用者定，件不自带字（「封存答案」自己写在柜子上方）。

```js
const P2 = { x: 2520, y: 1080, w: 230, h: 16 };
L.pile2a.until = tCards;                                               // 旧摞（5 张）撤掉，早 0.12 s 换 3 张的静态摞
WB.stack({ x: P2.x, y: P2.y, n0: 3, n1: 3, t0: tCards - 0.12, t1: tCards - 0.12, el: 'pile2', w: P2.w, h: P2.h, item: WB.cardItem() });
const sb = WB.sealBox({ env: { cx: 2840, cy: 1000, w: 260, h: 160 }, cab: [3270, 820, 380, 270],
  t: { cab: L.tCab, env: tEnv, close: tSeal, drawer: tDrawer, lock: tLock }, feed: { stack: L.pile2a, n: 2, at: tCards } });
WB.ev('B2_01', 'seal.cards', 'slide', sb.cards, 0.6);
WB.ev('B2_01', 'seal.stamp', 'pin', tSeal, 0.4);
WB.ev('B2_01', 'seal.lock', 'pop', sb.lock, 0.3);
```

## 十一、WB.calendar：日历（1.3.1）

`WB.calendar({rect:[x, y, w, h], t0, flips=[], fd=0.22, pop=0.3, grid=[3, 4], el})` → 自定义件：墙上挂的日历，强调色顶条、两个挂环、一页格子（`grid`＝[行, 列]），不写日期。

- t0 起 popIn `pop` 秒（锚点在中心；`pop: null` 直接出现）；`flips` 里每个时刻翻一页（`fd` 秒：上一页按 `cos(π·u)` 绕顶边收起，过半后画成压扁的条，不盖住上方的字）。
- 顶条、格子、挂环按 rect 比例算（220×230 时与样片一致）；`act` 覆盖 pop 与各翻页窗口，`jump:'pop'`。
- 用途：「够久」「过了一段时间」——翻页就是时间过去，不必写日期。上屏字由调用者定，件不自带字。

```js
const cal = WB.calendar({ rect: [3480, 1630, 220, 230], t0: tCal, flips: [tCal + 0.32, tCal + 0.56], el: 'calendar' });
WB.ev('B3_02', 'calendar', 'pop', cal, 0.5);
```

## 十二、WB.stepLoop：步骤环箭头（1.3.1）

`WB.stepLoop({labels, at, dur, ends=null, back=null, w=null, head=null, wash=0.35, col=WB.C.accent, el='loop'})` → `{arrows, washes, back, t1}`。

- `labels`：板上已写好的步骤字笔画（`WB.text` 的返回，有 `bb`、`size`），按步骤顺序。第 i 段箭头从 `labels[i]` 指向 `labels[i+1]`，`at[i]` 起笔、时长 `dur[i]`；实际起笔＝`max(at[i], 上一段箭头头画完 + 0.05)`。
- `ends[i]＝[[x0, y0], [x1, y1], bend]` 时用给定端点与弯度（绕开日历之类）；为 null（或整个 `ends` 为 null）时取两个字框相对的边缘中点、直线。
- 箭头到哪一步，那一步的字就涂一道淡红（`WB.fill`，颜色 `C.wash`；第 1 步在第一段起笔时就亮）。`wash`＝涂色时长（秒，缺省 0.35），**不是透明度**：淡红的深浅来自 `C.wash` 本身（`WB.fill(…, C.wash, 0.35, …)` 的第三个参数是时长）。
- `back={at, dur, via:[[x, y]…]}`：回环箭头，`via` 是整条路径的折点（必给，Catmull-Rom 平滑），起笔同样不早于上一段结束 + 0.05，箭头头 0.07 s。
- 杆粗 `w`、箭头长 `head` 缺省按 `labels[0]` 的字号算（168 号字时 30、110）。`arrows[i]`＝`WB.arrow` 的 `[杆, 头]`；`back`＝`[线, 头]` 或 null。el：箭头与淡红 `${el}_arrow`，回环 `${el}_back`。
- 起笔间隔是建件时排的；建板时「一支笔」规则会把和别的手写笔画重叠的笔画往后顺延，相邻的笔画可能被链式挤后——同一时段别再排别的手写笔画。
- 上屏字由调用者定，件不自带字（步骤字、收尾那句红字自己写）。`WB.ev` 由调用者登记。

```js
const loop = WB.stepLoop({ labels: [1, 2, 3, 4, 5].map(n => L.steps[n]),
  at: [Math.max(ok7, qb('B4_02', '再对答案') + 0.1), qb('B4_02', '签字') + 0.1, qb('B4_02', '才放手') + 0.15, qb('B4_02', '放手了') + 0.1], dur: [0.3, 0.45, 0.45, 0.4],
  ends: [[[2060, 1112], [1990, 1335]], [[2385, 1468], [2840, 1468]], [[3440, 1468], [4040, 1468]], [[4655, 1505], [4645, 2555], -160]],   // 样片手排的端点；④→⑤ 沿区四右缘下行、让开日历
  back: { at: qb('B4_02', '也要'), dur: 0.65, via: [[4030, 2600], [3700, 2410], [2700, 2398], [1400, 2392], [400, 2380], [140, 2160], [112, 1660], [170, 1330], [480, 1218], [1100, 1200], [1520, 1168], [1745, 1020]] } });
WB.ev('B4_02', 'loop_arrow', 'draw', [...loop.arrows.flat(), ...loop.washes], loop.arrows[3][1].t1 - loop.arrows[0][0].t0);
WB.ev('B4_02', 'loop_back', 'draw', loop.back[0], 0.65);
```

## 十三、WB.roll：里程表式滚数（1.3.2）

`WB.roll(x, y, {from, to, fmt, land, dur, col=WB.C.accent, size=92, fam=WB.BODY, wt='600', el, center=false, follow=null, step=0.1, hold=0.1})` → 自定义件；另挂 `land`、`cellsAt(t)`、`win`。`from`、`to` 是安全整数（≤ `Number.MAX_SAFE_INTEGER`，超出就抛错）。

- **和 `WB.count` 的分工**：要里程表的画面感（数位一格一格往上滚、进位时高位跟着一起滚）用 `WB.roll`；要干净的原地换字（表格里的读数、不抢戏的小数字）用 `WB.count`（`scene-writing.md` 的 cnt 模板）。
- 版式同早期样片的 `L.count`：`fmt` 按唯一一处 `{:.0f}` 拆成前缀、后缀（没有或多于一处就抛错）；数位等宽（按 `'0'` 的字宽）、右缘固定，位数增加时前缀跟着左移；`center` 按最宽值居中；`(x, y)` 是左端（center 时为中点）与基线。`from`、`to` 须是整数且 `0 ≤ from ≤ to`，否则抛错。
- 步：从空白滚到 `to−1`，共 `to−from` 步，先密后疏（第 i 步在 `t0＋T·(1−√(1−(i+1)/N))` 滚完，`t0＝land−dur`、`T＝dur−hold`），最后一步正好在 `land−hold` 滚完；每步只滚 `step` 秒（两步挨得比这还近时更短），两步之间各位停在对齐位置。`[land−hold, land)` 停在 `to−1`，**终值只在 land 那一帧整块出现**，并轻顿 0.24 s；起跳 0.08 s 淡入。`from = to` 时落定前什么都不画。
- 数位窗口 `[y−size, y+0.3·size]`，上下各一条 `0.22·size` 的渐变带（窗口边上透明度 0，线性升到带内侧 1）：滚动的数位在碰到窗口边之前就淡没，看不到硬切的边。滚动的数位还离开对齐位越远越淡（透明度 `(1−|dy|)²`：出去的字 `(1−r)²`、进来的字 `r²`），叠在边缘渐变之上——滚到一半露出的半截笔画只剩淡影，读起来是在滚，不会像「×2⁴₋」那样看成一个上下错开的怪数。停住的数位、前缀、后缀直接写字，对齐时与普通写字逐像素相同。滚动的数位先画进离屏画布再叠渐变，离屏画布按当前相机开在屏幕像素上，推拉镜头时也不糊。
- `follow(t) → [dx, dy]`：整块跟着平移（三维街区上的数字），`bbAt` 与 `textAt` 的框跟着走。`textAt` 报已滚完的值（不小于 from），land 起报 to；`from = to` 时落定前报 null。
- `cellsAt(t)` → 每个可见数位 `[{ch, dy, moving, k, x, a}]`（dy 以 `1.15·size` 为 1，滚动格两项：出去的字 −r、进来的字 1−r；k＝从个位起第几位；a＝`(1−|dy|)²`，停住的为 1）；`win = {top, bottom, band}`。都是世界坐标、未加 follow，给测试用。
- 整段夹在 `// ==== WB.roll 起（里程表式滚数，1.3.2）` 与 `// ==== WB.roll 止` 两行之间，只用 `WB`、`U`、`MO`、`document`：旧工程（工程里的 parts.js 是旧副本）要用，把这一段原样贴进场景文件即可。
- **别用早期样片那种 `L.count` 写法**：滚到一半数位硬切成半截、上下错开（审片截到过「×2」的 2 只露上半截、沉在下面）。
- `WB.ev` 由调用者登记 `count` 事件（件上有 `land`，qa 的 count_land 按它核）。

```js
// rcnt 模板：起跳＝念到那个数（落定前 0.6–1.3 s 之间），落定＝land_cue 末尾＋offset
const rcnt = (beat, el, x, y, o = {}) => {
  const e = TMB.ev(beat, el, 'count'), land = TMB.landOf(e);
  const t0 = Math.min(land - 0.6, Math.max(land - 1.3, qb(beat, e.at)));
  const n = WB.roll(x, y, { from: e.from, to: e.to, fmt: e.fmt, land, dur: land - t0, el, ...o });
  WB.ev(beat, el, 'count', n, land - t0); return n;
};
const k40 = rcnt('B2_02', 'k40', 1180, 640, { size: 116, center: true });   // 摞顶上方居中；三维街区上的数字另给 follow
```

## 十四、换页三式（1.3.3）

全片按页排（每页一块版式，页与页在板上并排）时，从一页换到下一页有三种做法。**要轮换着用**：同一式最多连用 2 次，全片换页 ≥5 次时至少用两式（规矩见 `scene-writing.md`「换页方式要轮换」）。一支 11 次换页全用引线的片子，观众说「看多了腻」，改成引线 3、平移 5、拉远回顾 3 后才顺。

| 式 | 用什么 | 镜头 |
|---|---|---|
| A 引线 | 现有 `WB.lead`（笔领相机的虚线）加 `WB.trip`／`WB.travel` | 先画引线，相机沿引线远行：途中先拉远再推近（常用 1.6 s、`out` 0.6） |
| B 平移 | `WB.panTo` | 直线平移 1.2 s，途中不拉远 |
| C 拉远回顾 | `WB.review` | 拉远到全貌（z 约 0.16–0.23），停一下再推进；拉远、停、推进合计 ≤4.2 s（常用 1.2＋1.0＋1.3＝3.5 s） |

**三式共用的时刻规矩**：

- 起镜 `tCam = max(上一拍句尾 + 0.05, 上一页最后一笔写完 + 1.0)`；算「最后一笔」时不算引线（`s.lead` 为真，或 el 里带 lead 的笔画）——引线是领相机的，不是上一页的结论。
- 起镜不晚于本拍句首 + 0.4：`tCam = Math.min(本拍句首 + 0.4, 上式)`。
- 本页第一样东西（页顶通栏线、轴、空卡底）两种合规做法，二选一：
  1. **起镜前预摆**：这几笔的 `t0` 早于起镜时刻 `tCam`，且画在上一镜取景框之外（同第十五节经验 7「表顶放在上一镜取景框之外，好预摆」）——观众看不见预摆的过程，落地时画面里已有主体。可另加 `handed: false`（不占「一支笔」，免得被一支笔规则顺延进运镜）。
  2. 放不到上一镜取景框之外的，就从件返回的 `ready`（落地 + `WB.SETTLE` + 0.02）起笔，接受落地瞬间短暂的空纸。
- **不要在运镜途中起笔（含 `camOk`）**：qa 的 `cam_pen` 量 `camOk` 笔画时要起笔后 0.3 s 内相机够慢（缩放 ≤0.05/秒、平移 ≤40 px/秒），换页运镜远超这个上限（1.3.3 开发时在新建白板工程上实测：落地前 0.4 s 起笔，平移 1700–2800 px/秒），qa 必 FAIL。原型片用的就是运镜中预摆（`camOk`），全链 qa 的 `cam_pen` 因此 FAIL 了 27 笔。
- 本页正文从件返回的 `ready`（落地 + `WB.SETTLE` + 0.02）起笔。

**B 平移：`WB.panTo(t, dur=1.2, to, o={})` → `{t1, ready, cam}`**

- `to` 两种写法：`[x, y, z]` 是相机位（`WB.frame`、`WB.trip` 返回的 `[x, y, z, bb]` 也认）；`[x0, y0, x1, y1]` 是两角矩形，先过 `WB.frame(to, o)`（`o` 的 `pad`、`zmin`、`zmax`、`dx`、`sy` 原样交给它）。
- 从 `WB.camAt(t)` 用 `MO.sineInOut` 直线移过去，xy 走直线、z 在两端之间单调（不拉远）。`dur` 给 `undefined` 或 `null` 时取 1.2。
- `t1` 是落地时刻（最后一个相机键的时刻），`ready = t1 + WB.SETTLE + 0.02`；`cam` 是落点（给矩形时就是 `WB.frame(to, o)` 的返回值，否则 `[x, y, z]`）。

```js
// 平移进页（原型的通栏线是运镜中 camOk 预摆，这里改成合规的起镜前预摆）
const tCam = Math.min(vo('S6_01')[0] + 0.4, Math.max(vo('S5_24')[1] + 0.05, prevEnd + 1.0));    // prevEnd：上一页最后一笔（不算引线）
const p = WB.panTo(tCam, 1.2, L.page(6));                                                       // L.page(n)：本片版式里第 n 页的两角矩形
WB.ev('S6_01', 'cam', 'camera', tCam, 1.2);
WB.line([[X(0), Y(112)], [X(2400), Y(112)]], { t0: tCam - 0.6, dur: 0.5, w: 5, col: WB.SOFT, smooth: false, handed: false, el: 's6.rule' });   // 起镜前预摆：t0 早于起镜，这条线在上一镜取景框之外
const ttl = WB.text('核心竞争力', X(0), Y(85), 64, { t0: p.ready, wt: '700', el: 's6.title' });
```

**C 拉远回顾：`WB.review(t, to, o={})` → `{t1, ready, cam}`**

- 先拉远 `o.out`（缺省 1.2 s）到全貌机位 `o.overview`，停 `o.hold`（缺省 1.0 s），再推进 `o.in`（缺省 1.3 s）到 `to`；拉远、推进各是一段 `MO.sineInOut` 直线运镜。
- `o.overview` 必填：相机位或两角矩形；矩形按 `WB.frame` 的缺省取景（`o` 里的取景键只管 `to`）。全貌框住已经走过的几页加下一页的页框，z 约 0.16–0.23。
- 返回值同 `panTo`：`t1` 是推进到位的时刻，`ready`、`cam` 同上。
- 停留期间相机完全不动，`WB.moves()` 不把它算作运镜（拉远、推进是两段运镜）。

```js
// 拉远回顾，进第 2 页
const OV = [L.PG(1).x, L.PG(1).y, L.PG(2).x + 2400, L.PG(2).y + 1100];                         // 全貌：上一页整页＋下一页页框
const r = WB.review(tCam, L.pgD(2, 380), { overview: OV });                                     // 落点给相机位
WB.ev('S3_01', 'cam', 'camera', tCam, 1.2 + 1.0 + 1.3);
```

**A 引线**：用现成的 `WB.lead(a, b, t0, dur)` 从上一页的结论词画淡墨虚引线指向下一页第一格，再 `WB.trip(tCam, 1.6, rect, { out: 0.6 })` 沿线远行（签名见第四节；落点要过 declip 时用 `WB.travel`），落地后 0.4 s 用 `WB.fade` 擦掉引线。

```js
// 引线，进第 3 页
const tL = vo('S3_06')[1] + 0.05;                                                                // 引线起笔
WB.lead([w.x + w.w + 14, w.y - w.size * 0.35], [X3(60), Y3(400)], tL, 0.9, { col: WB.SOFT, el: 's3.lead2' });   // w：上一页最后一个锚词
const tCam = Math.min(vo('S3_07')[0] + 0.4, Math.max(tL + 0.75, vo('S3_06')[1] + 0.05, w.t1 + 1.0));
const c = WB.trip(tCam, 1.6, L.page(3), { out: 0.6 });
WB.ev('S3_07', 'cam', 'camera', tCam, 1.6);
WB.fade(WB.S.filter(s => s.el === 's3.lead2'), tCam + 1.6 + 0.4, 0.4);
```

- 两件都不调 `WB.ev`：同 `WB.trip`，由调用方登记 `WB.ev(拍, 'cam', 'camera', t, 总时长)`。参数不对就抛错（「WB.panTo」「WB.review」开头），抛错时一个相机键都不压。
- 整段夹在 `// ==== WB.panTo／WB.review 起（换页两式，1.3.3）` 与 `// ==== WB.panTo／WB.review 止` 两行之间，只用 `WB`、`MO`：旧工程（工程里的 parts.js 是旧副本）要用，把这一段原样贴进场景文件即可。

## 十五、经验（审片抓到过）

来自摞、小人、原件卡那支样片：

1. **实物量不能先于数字到位——「每摞两步」**：相机到这一区时摞先停在上一档（n0＝上一个倍数），念到数字时随 `count` 事件逐件长到终值，最后一件与数字同一帧落定（`t1`＝数字落定时刻）。摞先长满、数字后到，观众会先看到答案。
2. **区框取景要比区框紧约 0.83 倍**：docCard 按 t0 时的相机缩放定字号，屏上字高保住 32 px；取景越远，世界里的字就越大，右栏越挤，标题、正文、出处会互相压住（出 console.warn）。样片区五的取景框缩到区框的约 0.83 倍（相机推近约 1.2 倍），卡上的小字才既够 32 px 又排得下。t0 之后还要再推拉的，按屏上最小那一刻核。
3. **尺寸与对齐在 1080p 静帧上量，不看缩略图**：名牌与摞底是否同一行、小人手是否碰到摞边、字有没有被画框切半截，`render.sh stills` 出整帧用 Read 看；缩略图和接触表会掩盖这类错位。
4. **同一个量在两种画法里比例一致**：摞高与坐标图纵轴用同一个线性比例（×45 的摞约是 ×15 的 3 倍高，图上 ×45 的点也约是 ×15 的 3 倍高）；一边线性一边对数，观众会读出两个不同的倍数。
5. **画面会引出的错误算术要堵**：两摞并排时观众会自己去减（45 − 15 = 30），口播说「差 30 倍」就在旁边写出那道减法，说明这是本金倍数之差，免得被读成「一个是另一个的 30 倍」。

来自机器、题卡、对照表那支样片（1.3.1）：

6. **红圈只圈叉、不跨列**：对不上的那一行，红圈只圈标记格里的叉，不连机器那一列的形状一起圈；圈框跨两列时圈会压到分隔线和底框，看着像圈了整张表。`WB.compareTable` 已把圈限在标记格内。
7. **表顶放在上一镜取景框之外，好预摆**：表框与左列在相机离开上一区之前就画好（`tPre` 早于运镜），表顶要在上一镜取景框下缘之外（样片表顶 y 1680，上一镜下缘约 y 1571），否则预摆的过程会被观众看见。
8. **远景下细箭头读不出变化，要逐步涂淡红**：收尾拉到 0.234 倍看全板时，30 粗的箭头在屏上只剩约 7 px，观众看不出箭头走到了哪一步；箭头到哪一步就把那一步的字涂一道淡红，`WB.stepLoop` 已内置。
9. **摞要「拿走几件」时换摞**：`WB.stack` 只会往上长。要拿走几件，把旧摞设 `until`（拿走那一刻），再在早 0.12 s 处新建一摞件数更少的静态摞（`n0 = n1`）；两摞重叠的 0.12 s 里画面与旧摞一样，换的那一刻不跳。样片里用了 5 次（其中两处是换成接着长的摞）。
10. **进度条结束要进 act**：进度条收起那一下是画面突变，不进 `act`、不带 `jump`，qa 的 jumps 会报未登记的跳变（样片里漏过）。`WB.machine` 的 `busy` 已把收起那一刻算进 `act`。
