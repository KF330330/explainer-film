# timeline.json 契约（口播稿＋事件）

> 何时读：写口播稿、拆 cue、登记事件之前。它是全链唯一的内容来源：配音按它合成，字幕按它切，场景按它对位，QA 按它查「说到的东西有没有动」。

## 顶层

```json
{"title": "片名", "version": "v1", "fps": 30, "width": 1920, "height": 1080,
 "source": {"file": "内容出处（相对项目根或绝对路径）", "lines": [起, 止]},
 "world": {"w": 4800, "h": 2800, "caption_band": 200, "rows": {"A": 80, "B": 1250, "C": 2300}},
 "motion": {"enter": 0.35, "exit": 0.18, "zeta": 0.8, "lag": 0.08, "write_cps": 15, "title_cps": 7.5,
            "num_hold": 0.5, "creep": 0, "count_dur": [0.9, 1.3], "land_offset_default": -0.15},
 "voice": {"engines": ["elevenlabs"], "approval_file": "audio/approved_voice.json"},
 "scenes": [ …见下… ]}
```

- `world`：一块板的世界坐标（1920×1080 是相机取景）；`rows` 是三行版式的 y 起点，场景文件 `B0.js` 里的 `WB.L` 按它排各块。
- `motion`：动效契约数字，执行者照抄：入场 0.35 s / 退场 0.18 s；写字 15 字/秒、标题 7.5；数字落定后停 ≥0.5 s；`creep 0`＝停留时相机不动；`count_dur` 数字滚动时长区间；`land_offset_default`＝落定时刻相对数字子 cue 末尾的偏移（−0.15 s，ElevenLabs 片段末尾有一点尾静音）。

## 场景与节拍

```json
{"id": "B3", "kind": "curve", "hold_secs": null,
 "beats": [
   {"k": 15, "n": 23,
    "say": "7 轮、4 天，从 92.2% 到 100%；",
    "tts": "七轮、四天，从百分之九十二点二到百分之百；",
    "cues": [{"id": "B3_15a", "text": "7 轮、"}, {"id": "B3_15b", "text": "4 天，"},
             {"id": "B3_15c", "text": "从 92.2%"}, {"id": "B3_15d", "text": " 到 100%；"}],
    "events": [
      {"el": "card1.l3",  "do": "write", "at": "7 轮",  "dur": 0.6, "text": "7 轮 4 天"},
      {"el": "card1.pct", "do": "write", "at": "92.2%", "dur": 0.4, "text": "92.2% →"},
      {"el": "card1.pct2","do": "count", "at": "100%",  "dur": 1.0, "from": 92.2, "to": 100,
       "land_cue": "B3_15d", "fmt": "{:.1f}%"}],
    "look": [{"type": "图表"}, {"type": "实物", "at": "92.2%"}],
    "consent_required": false}]}
```

| 键 | 规则 |
|---|---|
| `id` | 场景名 `^[A-Z][0-9]+$` 之类的短名；片头场景 `kind: "title"`、`hold_secs: 3`、`beats: []`（3 秒无口播）。 |
| `k` | 节拍序号（本场景内从 1 起）；节拍键＝`<场景>_<两位 k>`，如 `B3_15`。`n` 是全片序号，可选。 |
| `say` | **显示稿**：字幕与 QA 用，原文原样（含阿拉伯数字、空格、标点）。全片 `say` 顺序拼接＝口播稿全文，一字不差。 |
| `tts` | **读法稿**：送合成用。数字写成读法（92.2% → 百分之九十二点二），英文名保留英文；`norm(tts)` 与 `norm(say)` 去标点后须相等（`voice_diff.norm`）。只有听出读错的字才换同音字，`say` 不动。 |
| `cues` | 子 cue：**含关键数字的节拍按标点拆，保证每个数字落在它所在子 cue 的末尾**；`cues[].text` 顺序拼接＝`say`（含空格）。没有数字的节拍可以只有一个 cue（id＝节拍键）。数字后面紧跟量词和名词、按标点拆落不到子 cue 末尾时（「定一个二十五分钟的闹钟，」），不要在词中间硬拆（每个子 cue 单独送合成，词中间一断读起来就顿）：要么让 `count` 的 `land_cue` 落在含这个数的短句末尾（「做满四个番茄，」——第四个番茄与 ×4 在这句念完时一起落定），要么不用 `count`，改用 `pop` 在念到这个数时把它砸到东西上（`WB.qb(拍, '二十五')`）。 |
| `events[].el` | 具名元素，点号分层（`card1.l3`）；场景代码给对应笔画打同名 `el`，QA 用 `elementBoxes()` 取它的框。 |
| `events[].do` | `write / draw / grow / pop / pin / count / underline / circle / strike / slide / camera` 之一。场景里每一处 `WB.ev(拍, el, do, …)` 都必须在该拍的 `events` 里有同 `el`、同 `do` 的一条，**运镜也一样**（`WB.ev(拍, 'cam', 'camera', t, dur)` 要在 timeline 里登记 `{"el": "cam", "do": "camera", "at": …, "dur": …}`），否则 `TMB.ev` 报 console.error、渲染非零退出。 |
| `events[].at` | **本节拍 `say` 原文里的子串**，须恰好出现一次（`make_timing.py` 校验，否则退出非 0）；场景里用 `WB.qb(节拍, at)` 取念到它的时刻。 |
| `events[].dur` | 动作实际时长；QA 在 `[start, start+dur]` 的 25%/75% 两处取帧比变化。每句事件总时长 ≤ 该句音频时长。 |
| `count` | 另有 `from/to/fmt/land_cue[/land_offset]`：落定时刻＝`land_cue` 的真实 end＋offset；`land_cue` 必须属于本节拍。 |
| `consent_required` | 引用他人观点的节拍标 true，交付说明必须写明本人同意状态。 |
| `look` | 画面类型（1.3.0；`project.json` 有 `storyboard` 键的工程必写，`check_storyboard.py` 与 qa 的 `storyboard` 项查）。字符串＝整拍一种，如 `"look": "图表"`；数组＝拍内换类型，如 `[{"type":"图表"},{"type":"原件","at":"按每年"}]`：首项从拍首起，后项从 `at` 词开口时刻起（`at` 在该拍 `say` 里恰好一次，解析同 events 的 `at`）。`beats: []` 的片头段在场景级写 `look`（时长＝`hold_secs`）。类型只用词表 `storyboard.vocab`：`场景`（有地点有人物的小场景）、`角色`（人物在演动作）、`图表`（坐标图、柱、流程框、表格）、`原件`（内容本身的材料：口播说到的那件事的真迹或我们做法的真实产物，必带出处；谐音、同名、装饰性古画古书不算）、`实物`（实物比喻：硬币摞、房子、卡片堆）、`地图`、`三维`、`字卡`（大字、结论卡）。画面段从自己起点到下一段起点（最后一段到片尾），相邻同类合并后算「同一种连续」：≤15 s（`max_same_run_s`）；全片 ≥4 种（`min_kinds`；口播 <40 s 时 `min_kinds_under_40s` 3 种）。 |

## 写口播稿的规矩

- 口播只来自用户给的内容：用户给的是讲稿就原样用；给的是文章／提纲就改写成口语讲稿，**在停点 1 给用户过目并锁定**，之后不再改字。
- 一句一拍，3–7 秒一拍（约 15–35 字）；关键数字单独成子 cue。
- 上屏文字另写（镜头表「屏上字」列，每镜 ≤8 字），不是把口播搬上屏。
- 红线：`tools/redlines.txt`（词）＋`tools/redlines-names.txt`（真人姓名）在 `say/tts/脚本与分镜.md` 里零命中（`check_redlines.py`）。

## 派生物

`make_timing.py` 由 `audio/cues.json`＋本文件生成 `engine/<film>/timing.js`（`window.TIMING`：`seg{场景}`、`beats{节拍}`、`cues{子cue}`，全片绝对秒，含片头静音）与 `engine/eras_<film>.js`。契约细节见 `vendor/docs/接口速查.md` §4。
