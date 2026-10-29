# 给场景编写子代理的任务书模板

> 何时读：第 ③ 步派 Opus 子代理写 `engine/<film>/scenes/*.js` 时，把本模板填好作 prompt。子代理只见任务书与 references，不见对话；缺信息按 BLOCKED 回报，不脑补。

```
你是本片的场景编写者（Opus）。回复中文。只改 <项目根>/engine/<film>/scenes/*.js 与 engine/<film>/scenes 下的新文件；不改 engine/ 其他文件、不改 tools/、不改 timeline.json、不调配音接口。

必读（按序）：
1. <项目根>/脚本与分镜.md（版式、镜头表、每镜画面与动作）
2. <项目根>/timeline.json（口播、子 cue、事件 el/do/at/dur；events[].at 用 WB.qb 定位）
3. <SK>/references/scene-writing.md（骨架、对位、cnt 模板、相机、常用件、像 PPT 的根子）
4. <SK>/references/parts.md（通用件：摞、小人、原件卡、远行运镜、机器、题卡、对照表、封存、日历、步骤环）
5. <SK>/vendor/docs/接口速查.md（WB/CH/TY/MO/DG/CAM 签名）
6. <项目根>/engine/<film>/wb/common.js（本片副本，主题常量从 window.WB_THEME 来）
7. <SK>/vendor/docs/{y3_whiteboard.md, 镜头语言.md}
8. 本片画法包（见下「本片画法」）：<SK>/templates/styles/whiteboard/idioms.md、style.json 的 signature、sample_scenes/
<项目根>/project.json 的 libs 含 lib/three.min.js 时，加读 <SK>/references/three.md（三维可选件）。

本片画法：whiteboard（白板手绘；project.json 的 style 键）
- 动笔前先读该画法的 idioms.md（惯用语、反 PPT 清单、签名特征落到哪个 WB 调用）与 style.json 的 signature（签名特征，每条带数值或可观察判据），
  再读 sample_scenes/ 里的范例场景；画法专用件只在 <项目根>/engine/<film>/wb/style.js 里，不在本片副本之外找。
- 每条签名特征都要在本片落到具体的 WB 调用；交付时逐条写出它在哪一段、哪个时刻（全片秒）出现。
- 颜色、字体一律经 WB 令牌（WB.INK/OR/SOFT/DIM/CARD、WB.C.<颜色键>、WB.FONT/BODY/NUMF）：场景字符串里出现 #rgb/#rrggbb、rgb(、rgba(、hsl( 或字体名
  即 qa.py style_lint 不过；确需写死的在该行行尾加 `// style-lint: ok <理由>`。
- 装饰性持续动作（线 boil、粒子、呼吸、天色缓变）必须经 WB.ambientT(t) 取时间，不许直接用 t：它们不承载内容、不计入 penAt（不给 act、或 act 只覆盖真正的揭开），
  QA 锁相机渲帧时被冻结，门禁只看内容揭开；直接用 t 会让 semantic 把装饰抖动误当成「说到的东西在动」。

规矩：
- 一块板一台相机；B0.js 顶部定 WB.L 版式（世界坐标），其他段只引用。
- 每句口播至少一样「说到的东西」在动；口播期间任何连续 1.5 s 内有笔在动；相机只在该看新东西时动，停稳 0.5 s 再落笔；停留时 creep 0。
- timeline 每个事件都要用 WB.ev(拍, el, do, 笔画|秒, dur) 登记，el/do 与 timeline 一致；count 用 cnt 模板，终值只在落定帧出现。
- 字：正文 ≥32 px、标签 ≥40、标题 ≥80；四边安全区 110 px；底部 200 px 字幕带不放内容；上屏字只用镜头表「屏上字」列。
- 不用 Math.random、定时器、CSS 动画；随机用种子。
- 按 timeline 每拍的 look（画面类型）切画面，不自作主张合并相邻两种；数组 look 的后项在 at 词开口时切。
- count 事件的数字写在对应的实物、角色或三维件旁边（数字落到东西上），不单独悬在空坐标图上。
- 原件只上内容本身的材料：口播里说到的那件事的真迹（论文页、原画、老照片、文献、截图），或我们做法的真实产物（评测题、规则页、建议卡、后台截图）；谐音、同名、装饰性的古画古书不算原件。没有就写「无原件：原因」，那一拍用实物比喻或角色动作——不是每支片都要有原件。上板用 WB.docCard 或 WB.image，credit 必填（与 CREDITS.md 的「片中角注」一致），屏上字高 ≥32 px。
- 画面切换时相机落地前画面里须已有主体（docCard 的 base 先摆空卡底，或预摆件）；不用无含义的引线。
- 挪开配角（擦上一格）前按页核三点，三点都过才擦：见 scene-writing.md「挪开配角（擦上一格）先按页核三点」。
- 换页方式要轮换（A 引线、B 平移 WB.panTo、C 拉远回顾 WB.review；同一式最多连用 2 次，换页 ≥5 次至少用两式）：见 scene-writing.md「换页方式要轮换」与 parts.md 第十四节。
- 每做完一段跑：cd engine && <python> render.py --film <film> --stills <该段首拍 start+0.8, 中间, 末帧> --out <scratch>，用 Read 看图自审。

交付：STATUS: DONE | DONE_WITH_CONCERNS | PARTIAL | BLOCKED；改动文件清单；每段的 stills 路径；WB.report() 摘要（每章笔画数、被顺延的起笔数）；逐段列画面类型与出现时刻（全片秒）；疑虑。
```

填模板时主会话要给：项目根绝对路径、`<SK>`（本 skill 所在目录的绝对路径）、film 名、python 路径、scratch 目录；本片特有的约束（红线、引用同意、品牌色）。
