# 机器检查与门禁（qa.py）

> 何时读：草稿或成片跑完 `qa.py` 看 `out/qa.json` 时；某一项 FAIL 要定修法时；给新片标定阈值时。

## 硬门禁（任一 FAIL 不交付）

| 项 | 判什么 | 不过怎么修 |
|---|---|---|
| `pen_idle` | 口播期间（首 cue 到末 cue）每 0.05 s 采样，`penAt(t)` 为空且相机不动的连续段 ≥1.5 s 即 FAIL | 给那句加一笔句意相关的小动作（圈 0.6–1.2 s、下划线、描红），不加装饰性假动 |
| `semantic` | timeline 每个事件在 `[start, start+dur]` 的 25%/75% 取两帧（同一相机 `lockcam`、遮字幕带），元素框内任一通道差 >12 的像素数 ≥ `qa_config.semantic_threshold`；**每拍至少一个事件过**，完全没登记事件的拍 FAIL | 事件没登记 → 补 `WB.ev`；动作太小 → 加大或换动作；元素在画面外 → 相机先到位 |
| `count_land` | 页面登记的落定时刻与 `land_cue.end+offset` 之差 ≤0.1 s | 用 cnt 模板；`land_cue` 要落在数字所在子 cue |
| `cam_pen` | 画面内笔画的 `t0` 不落在运镜区间及其后 `settle`（0.5 s）内 | 起笔改到 `运镜末 + settle` 之后 |
| `still_flagged` | 审片人标过的死帧处（`qa_config.still_flagged.spots`，按 [节拍, 字] 锚点）：处内任一 1.2 s 窗，12 fps 逐帧对变化像素累计 ≥0.4%（640 宽灰度、差 >12、遮字幕带） | 同 pen_idle |
| `still_video` | 成片逐帧（12 fps）口播期间连续静止 ≤1.5 s（阈值 K 用片尾静持段噪声标定：片尾静持段＝末 cue 结束 +0.2 s 到片尾前 0.1 s，K＝该段相邻帧变化像素最大值的 3 倍；这段里有运镜或动作，K 会被抬高到全片判静止，所以收尾拉远必须在末句口播里做完）；画法有线 boil 等装饰性持续动作时，`qa_config.still_video_source` 设 `"noambient_draft"`：先 `render.sh draft --noambient` 出无装饰草稿，still_video 与 still_flagged 量它。口播结束后画面里还有 `WB.walker`、TOON 角色眨眼呼吸，或三维装饰摆动时，`still_video_source` 设 `noambient_draft`；否则片尾噪声会把阈值 K 抬高（曾有样片被抬到 99） | 同上 |
| `jumps` | 上游 `gates/qa.py` 报的跳变逐条能对上相机运动／砸入／数字落定／带 `jump` 字段的笔画（画法包专用件），对不上的 FAIL | 查是不是漏登记的砸入或闪烁 |
| `style_lint` | 只在有 `style` 键的新格式工程跑：`engine/<film>/scenes/*.js` 的字符串里不得有 `#rgb`／`#rrggbb`、`rgb(`／`rgba(`／`hsl(` 与字体名（颜色字体一律经 WB 令牌） | 改用 `WB.INK/OR/…`、`WB.C.<键>`、`WB.FONT/BODY/NUMF`；确需写死在行尾加 `// style-lint: ok <理由>` |
| `layout` | 每 0.25 s 采样：不出 110 px 安全区、不进字幕带、字号 ≥32、不重叠、字不半截（≥0.5 s 才算） | 调版式或相机 `declip` |
| `determinism` | 随机 30 帧重渲 sha 一致 | 查 Math.random／时间依赖 |
| `av` / `loudness` | 视频流、音频流、源 wav 三者时长差 ≤0.1 s；−16±1 LUFS、真峰 ≤−1.5 | compose/make_audio 的事 |
| `subtitles` | 每条 ≥0.83 s、≤2 行、每行 ≤16 可见字、单调、拼接＝`say` | cuelib 的 `breaks` 表加断句 |
| `redlines` | 红线词与姓名零命中 | 改口播稿要回停点 1 |
| `storyboard` | `check_storyboard.py`（1.3.0）：每拍有画面类型（timeline `look`）且在 `storyboard.vocab` 里；同一种连续 ≤15 s；全片 ≥4 种（口播 <40 s 时 3 种）；`脚本与分镜.md` 镜头表有「画面类型」列；`assets` 里的原件在 `CREDITS.md` 都有行且「许可」列不空。老工程（无 `storyboard` 键）、脚手架（只有片头段）、`require_look` 为 false 且 timeline 一个 `look` 都没有（not required）记 INFO；`require_look` 为 false 但写了部分 `look` 的照常核词表、连续与种类，只是不核缺 look | 按它打印的违规改 timeline 的 `look` 或分镜：连续太长就在中间换一种画面（原件、实物、角色）；种类不够就把数字落到实物上或让角色演出来；原件只在有内容本身的材料时才上，不为凑种类放原件 |
| `film_gate` 的空画面与蓝紫底 | 中段空画面 0、蓝紫底 <0.12 | — |

## 只记录、不拦（`qa.record_only`）

`fast_ratio`（上游引擎的快动帧占比：它只认运镜和大元素砸入，白板笔写读作静止，白板片通常只有 0.00–0.02）、`blue_purple_share`、`push_in_per_min`、`longest_still_s`（film_gate 自报的，读不出笔写）。写进 `qa.json` 的 detail 与 `hints`，供审片者参考。

## 阈值标定（新片第一次）

1. `semantic_threshold`：本片第一支认可草稿（用户点头的 2 分钟带声草稿）跑 `qa.py`，取各事件变化像素数分布的下 10 分位写进 `tools/qa_config.json`，`calibrated: true`。
2. `still_flagged.spots`：审片代理标出的死帧处按 `[节拍, 字]` 登记（字为 null＝该拍末尾）。
3. 其他阈值沿用默认；改了要在 `qa_config.json` 的 `source` 里写依据。

## 看 qa.json

每项 `{"name","status":"PASS|FAIL|INFO","detail"}`；`verdict` 全 PASS 才交付；`hints` 里有口播期间静止段列表、每镜时长、推近次数——给审片者判断「正常阅读停顿」还是「死帧」。
