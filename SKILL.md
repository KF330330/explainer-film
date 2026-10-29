---
name: explainer-film
description: 一句话把任意内容（文章、报告、提纲、一个主题）做成白板手绘风格、全程动画的配音讲解视频：模型写逐帧画画程序（一整块暖白纸板一台相机，字按笔顺写出、线按笔速画出、数字在念到那一刻落定）、无头浏览器逐帧出图、ElevenLabs 配音（你自己账户里的即时克隆声或声音库里的声音）、ffmpeg 合成 mp4；内建声音试听认可与反 PPT 门禁；中途只停两次（口播稿与试听一起过目、2 分钟带声草稿点头）。使用此 skill 当：(1) 用户说「做个讲解视频」「做成动画讲解」「全程动画」「白板动画」「手绘讲解」「做个讲解片」「把这篇做成讲解视频」「/explainer-film」；(2) 要给分享、汇报、课程配一段带配音的动画短片，即使没提「动画」，只要要的是带配音的讲解视频也用；(3) 重做或补拍某一段讲解动画。
metadata:
  version: 1.3.3
  origin: explainer-film 外发版（白板画法、配音视频、只走 ElevenLabs）
---

# explainer-film · 一句话出白板手绘配音讲解视频

## 你只需看这里

- **触发**：用户给一段内容（文件、链接、粘贴文本或一个主题）说「做成讲解视频」。
- **开工先跑自检**：`bash "$SK/scripts/selfcheck.sh"`（`SK`＝本 skill 所在目录）。全过再往下；有 FAIL 就停下来把它打印的提示告诉用户（缺字体、缺环境就让用户跑 `scripts/install.sh`；缺 ElevenLabs 配置就把它打印的两行命令给用户），不替用户配、不读密钥内容。
- **画法**：只有白板手绘一种（`templates/styles/whiteboard/`）：暖白纸板、墨色笔顺手写、唯一强调红、一台相机在板上推拉横移。场景代理照 `idioms.md` 与 `sample_scenes/` 写。
- **七步**：建项目 → 写口播稿与分镜（**停点 1**：分镜 md 给用户过目；第一次用这个音色时连同 30 秒试听）→ 派 Opus 写场景＋静帧自审 → 配音＋对位 → 2 分钟带声草稿（**停点 2**）→ 全片草稿审片 ≤3 轮 → 一次 `build.sh --clean` 出成片＋机器检查＋交付说明。
- **分镜四条**：每拍写画面类型（timeline `look`＋镜头表「画面类型」列）；同一种连续 ≤15 s、全片 ≥4 种（口播 <40 s 时 3 种）；数字落到东西上（倍数落在硬币摞、房子、人身上，不落在空坐标图上）；原件只上内容本身的材料（口播说到的那件事的真迹，或我们做法的真实产物），谐音、同名、装饰性古画古书不算；没有就写「无原件：原因」，不为凑规矩硬放。`check_storyboard.py` 与 qa 的 `storyboard` 项查。三维画面用 `new_project.py --three`，见 `references/three.md`。
- **产物**：工程目录在当前项目里（timeline、分镜、scenes、project.json）；产物一律放仓外 `~/Movies/讲解视频/<项目>/{audio,review,out}`（`--out-root` 可改）。
- **硬规矩**：vendor 引擎零改动；配音只走 ElevenLabs；批量合成前必有用户试听认可记录；成片必来自一次 `--clean` 全链（唯一例外见下条「来不及时」）；五把尺子全过才交付；口播稿锁定后不改字。
- **来不及时**（用户明说「来不及」才走）：
  - 能省的：审片代理减到 1 轮，或由主会话自己看帧条；停点 2 可以和看全片合在一起；成片可以分段渲染再用 ffmpeg 拼接——同一份 timing.js 下并行起几个 `render.sh part <a> <b> <产物根>/review/part-<a>-<b>.mp4`（相邻两段共用同一个段界，末段的 `b`＝`engine/<片名>/timing.js` 里的 `TIMING.total`），列表文件每行 `file '<段的绝对路径>'`，`ffmpeg -f concat -safe 0 -i <列表> -i <第一段> -map 0:v -map_metadata 1 -c copy -movflags +faststart+use_metadata_tags <产物根>/out/video_only.mp4`（帧数与整片渲相同，抄上第一段的版本标签），再 `compose.py`。
  - 不能省的：只用认可过的音色；要有试听认可；红线零命中；口播只改用户点名的句子。
  - 拼出来的成片至少跑一次 `qa.py --video <产物根>/out/<交付名>.mp4`，交付说明写明「非 --clean 全链」，并把这一点列为残余。
- **预期耗时**（实测一支 8 句 178 字、成片 50.9 s 的片子）：建项目 5 s；口播与分镜约 10 分钟；场景代码由 Opus 子代理写约 30 分钟，审片一轮加修约 30 分钟；配音约 1.5 分钟；一次 `--clean` 全链 7–18 分钟（1,527 帧）；独立验收约 5 分钟——合计约 2 小时。5 分钟成片按比例约 1 个工作日（全片渲染约 40 分钟）。ElevenLabs 按字符计费：一支片的用量≈口播字数＋试听字数＋重录的句子（缓存命中不计费），对照自己套餐的月额度估。

## 0. 前提自检

`bash "$SK/scripts/selfcheck.sh"`：1 四个字体（Songti SC、PingFang SC、Georgia 浏览器实测，Hiragino Sans GB 审片字体文件，仅 macOS）；2 `~/.venvs/explainer-film/bin/python`＋playwright/numpy/opencv/Pillow 能导入、`~/.venvs/explainer-film/bin/ffmpeg` 能跑；2b `~/.config/elevenlabs/` 归本人、`api-key`、`voice-id` 两个文件在且权限 600（只看属性，不读内容）；3 vendor 清单 sha 抽核；4 参考片出帧；4b 白板画法包齐全。环境由 `scripts/install.sh` 一次装好（不带参数；建 `~/.venvs/explainer-film`、装依赖与 Chromium、软链 ffmpeg/ffprobe，最后跑 `selfcheck.sh --no-voice`）。缺字体或缺 ElevenLabs 配置＝停下来告诉用户，不替他配、不读密钥内容。

## 1. 七步流程（每步一行命令＋产物＋失败怎么办）

`SK`＝本 skill 所在目录（装在 `~/.claude/skills/explainer-film` 时就是它），`PY=~/.venvs/explainer-film/bin/python`；`SK` 的路径可能含空格，命令里一律写成带引号的 `"$SK/…"`。所有脚本带 `--project <项目根>`（或在项目目录内运行）。

### ① 建项目
`$PY "$SK/scripts/new_project.py" --dest <项目根> --film <片名> --title "<标题>" [--three] [--version v1] [--out-root <产物根>]`
→ 画法缺省就是白板（`whiteboard`）：`project.json` 写 `style`、主题取白板默认、`engine/<film>/wb/style.js` 复制进来；分镜有 `look:"三维"` 的片子加 `--three`（另带三维可选件，已有工程用 `--add-three`，见 `references/three.md`）。复制 13 个引擎根文件＋软链 8 个大目录、生成最小可渲染项目（B0 片头）、`project.json`、`timeline.json` 骨架、`脚本与分镜.md`、`tools/{qa_config,tts_overrides,redlines,redlines-names}`、`.gitignore`；自检渲参考片与空片各一次，失败只删本次新建目录并退出 2（看它打印的原因：多半是字体或 vendor 软链目标）。项目放哪由当前仓库的放置规则决定（没有规则就放用户指定处）；`--dest` 已存在且非空会拒绝。

### ② 口播稿与分镜（停点 1）
1. 读内容 → 写 `timeline.json`（一句一拍、3–7 秒；关键数字拆子 cue；`say` 显示稿／`tts` 读法稿；事件 el/do/at/dur 先按分镜写；每拍写 `look` 画面类型）与 `脚本与分镜.md`（画风锁三行＋板上版式＋镜头表：时间段｜画面类型｜画面里的物｜它在做什么｜镜头｜屏上字 ≤8 字｜做法＋「三、原件与素材」表；用到原件同时登记 `CREDITS.md` 与 `project.json` 的 `assets`）。契约见 `references/timeline-schema.md`（`look` 的写法与词表在键规则表）；镜头表模板见 `templates/脚本与分镜.md`（`vendor/docs/镜头表模板.md` 的 6 列加「画面类型」列）。
2. `$PY "$SK/scripts/check_redlines.py"` 零命中（红线表在 `tools/`，主会话按内容填）；`$PY "$SK/scripts/check_storyboard.py"` 零违规（画面类型轮换、镜头表「画面类型」列、原件出处；没配音前按音节数临时估时）。
3. `$PY "$SK/scripts/approve_voice.py" check`：退出 0＝全局已有当前音色的认可记录，已复制进本工程，这一片不再试听，第 4 步也不跑 `record`；退出 3＝没认可过 → `approve_voice.py sample`（≤8 句、≤40 秒试听，会花这几句的字符额度）。
4. **停点 1**：`open` 分镜 md（第 3 步跑了 `sample` 时连同试听一起 open）。用户点头＝口播稿认可（跑了 `sample` 时也等于声音认可）。只有跑了 `sample` 的才接着 `approve_voice.py record --quote "<用户原话>"`；`record` 要用本片这次的试听文件，check 已通过的不要跑。用户改稿就改 timeline 与分镜再来一次。口播稿锁定后不再改字。

### ③ 场景代码（派 Opus 子代理）
1. `$PY "$SK/scripts/provisional_cues.py"` → `$PY "$SK/scripts/make_timing.py" --cues <产物根>/audio/cues-provisional.json`（声音没合成前先按字速造时间轴，场景能先写）。
2. 用 `references/scene-brief.md` 填任务书（「本片画法」填 `whiteboard`：要它先读 `templates/styles/whiteboard/idioms.md`、`style.json` 的 signature 与 `sample_scenes/`），`Agent(subagent_type="general-purpose", model="opus")` 写 `engine/<film>/scenes/*.js`（它只见任务书与 references）。
3. 回来后 `bash "$SK/scripts/render.sh" stills <每段首拍+0.8, 各数字落定, 末帧> <scratch 目录>`，用 Read 看图自审：曲线可辨、字不半截、宋体与苹方生效、白板签名特征看得见、无溢出、画面类型按分镜切换（与 timeline `look` 一致）。上板字改了就 `$PY "$SK/scripts/make_strokes.py"`（重抽笔顺）。

### ④ 配音与对位
`$PY "$SK/scripts/make_audio.py" --engine elevenlabs`（核认可记录，不符退出 4；读错的句子 `--force <cue,…>` 重合成）→ `$PY "$SK/scripts/make_timing.py"`（真实切点回填 timing.js／eras）。规则见 `references/voice.md`。

### ⑤ 带声草稿（停点 2）
`$PY "$SK/scripts/make_draft.py"`（按 `project.json.draft.ranges`，默认前约 2 分钟＋含数字与循环的段）→ `open` `<产物根>/review/draft-1.mp4`，用户点头后才渲全片；不点头 → 改场景再出草稿。

### ⑥ 全片草稿与审片（≤3 轮）
`bash "$SK/scripts/render.sh" draft` → `$PY "$SK/scripts/compose.py" --video <产物根>/review/draft.mp4 --review-dir <产物根>/review --name 草稿-审片`（`--name` 另起名，草稿合成写到 `out/草稿-审片.mp4`，不覆盖交付名文件）出接触表、画面轮换表 `rotation.jpg` 与帧条 → 按 `references/review-and-delivery.md` 派独立审片代理（只看图，≤10 条带时间码）→ 修（派回场景代理或自己改）→ 再 draft；第 3 轮仍不过就停下来问用户。阈值首次标定见 `references/qa-rules.md`。

### ⑦ 成片、检查、交付
`bash "$SK/scripts/build.sh" --clean --engine elevenlabs`（配音→时间轴→渲染 1080p30→合成→qa，日志 `out/build.log`）→ `out/qa.json` 的 `verdict` 必须 PASS（五把尺子＋版面＋音画＋字幕＋红线＋分镜；fast_ratio 只记录）→ 独立验收（`references/review-and-delivery.md` 第 1–10 项）→ `open` 成片 mp4 → 对话里写交付说明（模板同上）。

## 2. 硬规矩

1. `vendor/engine`、`vendor/gates` 零改动（manifest sha 核）；我方文件只在 `engine/eras_<film>.js`、`engine/<film>/`、`tools/`、`timeline.json`、`脚本与分镜.md`。
2. 配音只走 ElevenLabs：spec 必须显式 `provider: "elevenlabs"`（`el_cued.py` 不认别的，退出 2）；换音色必须重新试听认可。
3. 批量合成前必须存在 `<产物根>/audio/approved_voice.json`（由 `approve_voice.py check` 或 `record` 从全局记录复制过来），且指纹匹配；记录必带用户原话。
4. 交付成片必须来自一次 `build.sh --clean` 全链，`out/qa.json` 全 PASS；交付说明写明配音引擎、音色指纹、门禁数值、残余、引用同意状态。唯一的例外是「你只需看这里」的「来不及时」快速路径（分段渲染再拼接），要用户明说「来不及」才能走。
5. 口播只来自用户给的内容，锁定后不改字；上屏字 ≤8 字/镜；红线表零命中；合成文本会外发到 ElevenLabs，不能含客户数据或真人姓名。
6. 停点只有两处（`project.json.stops`），用户明说才减。
7. 产物不进仓、不进同步目录；`engine/<film>/timing.js` 是生成物不进仓。

## 3. 产物与目录

| 位置 | 内容 |
|---|---|
| `<项目根>/` | `project.json`、`timeline.json`、`脚本与分镜.md`、`CREDITS.md`（原件出处）、`存根-产物位置.md`、`tools/{qa_config.json,tts_overrides.json,redlines.txt,redlines-names.txt}` |
| `<项目根>/engine/` | 复制的 13 个根文件＋8 个软链（.gitignore）＋`eras_<film>.js`＋`<film>/{theme.js,tmb.js,wb/common.js,wb/style.js（白板画法包）,wb/parts.js（通用件，经 `libs` 加载）,wb/three.js（可选，三维件，`--three` 才有）,wb/strokes.js,timing.js,scenes/*.js}` |
| `<产物根>/audio/` | `approved_voice.json`、`narration.wav`、`cues.json`、`manifest.json`、`elevenlabs/`（逐 cue 合成结果与请求缓存） |
| `<产物根>/review/` | 静帧、`draft-N.mp4`、`contact.png`、`rotation.jpg`、`strips/`、`scene-end/`、`fast-*.png`、`qa-draftN/`、试听 |
| `<产物根>/out/` | `<deliverable_name>.mp4`、`.srt`、`video_only.mp4`、`build.log`、`qa.json`、`gate.json` |

## 4. 常见坑

- 字体缺：引擎启动时探测，缺即拒绝启动（只在 macOS 装了 Songti SC／PingFang SC 的机器上渲）。
- `__bootErrors`：场景文件语法错或没 `SCENES[id]=WB.scene`；`events[].at` 在该拍 `say` 里不是恰好一次 → `make_timing.py` 退出非 0。
- 写字时长超过那句口播：build 只顺延 ≤0.35 s，超了改 `rate` 或精简上屏字。
- 相机没停稳就落笔 → `cam_pen` FAIL：起笔改到运镜末＋0.5 s。
- 数字终值提前出现：cnt 模板里终值只在 `p ≥ 1` 显示。
- ElevenLabs 缓存全中不花钱；要重录用 `--force`；偶发开头重复只重录那一条，不要把句子拆碎。配音失败时看 `<产物根>/audio/.work/tts_cued.log`：401 密钥无效、402 额度不足、404 音色不对、429 限流。
- 渲染慢：full 1080p30 约 0.2 s/帧，5 分钟片约 20–40 分钟；先 draft（15 fps、960×540）看节奏。
- 上板汉字没笔顺（之字形揭开）：`make_strokes.py` 报未命中清单，换字或接受。

## 5. 文件索引

- `references/timeline-schema.md`（写口播稿前）、`scene-writing.md` 与 `scene-brief.md`（派场景代理前）、`voice.md`（配音前：自己的 key 与音色、试听认可、费用）、`qa-rules.md`（看 qa.json 时）、`review-and-delivery.md`（审片与交付）、`parts.md`（通用件 `templates/parts.js` 的签名与用法，含换页三式 `WB.panTo`／`WB.review`（第十四节），派场景代理前）、`three.md`（三维可选件 `templates/three.js`：开法、接口、硬事实，有 `look:"三维"` 的片子写场景前）、`project-config.md`（调参）、`vendor.md`（只在升级引擎）。
- `scripts/`：`install.sh`（装环境，不带参数）、`selfcheck.sh [--project P] [--no-voice]`、`efconfig.py`（读 project.json）、`new_project.py`（脚手架；`--relink` 重建软链、`--theme` 重写主题、`--three` 建工程时带三维可选件、`--add-three` 给已有新格式工程补上三维（事务写法，失败整体还原）、`--write-manifest` 重算 vendor 清单）、`approve_voice.py check|sample|record --quote`、`provisional_cues.py`、`make_audio.py --engine elevenlabs [--force cue,…]`、`el_cued.py`（ElevenLabs 逐 cue 合成，`make_audio.py`、`approve_voice.py` 调它）、`make_timing.py --cues`、`make_strokes.py`、`render.sh stills|draft|part|full`、`make_draft.py`、`compose.py`（出审片材料含 `rotation.jpg`）、`qa.py --video`、`check_storyboard.py [--cues] [--json]`（分镜画面类型检查；库 `storyboard.py`）、`build.sh --clean --engine elevenlabs`、`check_redlines.py`、`voice_diff.py`、`cuelib.py`。全部带 `--project P`（或 `EF_PROJECT`，或在项目目录内）。
- `templates/styles/whiteboard/`：白板画法包 `{style.json,style.js,idioms.md,sample_scenes/,preview.jpg}`。
- `templates/`：`project.json`、`theme.js`、`common.js`、`tmb.js`、`timing_min.js`、`scene_min.js`（脚手架最小片头；写真实场景的范例见 `styles/whiteboard/sample_scenes/B0.js`）、`qa_config.json`、`tts_overrides.json`、`redlines*.txt`、`gitignore`、`脚本与分镜.md`（7 列镜头表＋原件与素材表）、`CREDITS.md`（原件出处表）、`parts.js`（通用件）、`three.js`（三维可选件）、`存根-产物位置.md`。
- `vendor/`：引擎、门禁、上游文档、笔顺数据包、`VENDOR.md`、`vendor_manifest.json`。
- `README.md`（安装与使用说明）、`CHANGELOG.md`、`requirements.txt`。

## 6. 升级引擎

见 `references/vendor.md`。
