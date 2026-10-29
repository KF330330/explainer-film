# project.json 字段表

> 何时读：脚手架建完项目要调参时；脚本报「配置缺键」时。所有脚本只从它读项目信息（`efconfig.py`），项目根由 `--project`／`EF_PROJECT`／从 cwd 向上找三种方式之一确定，绝不按脚本位置推。

| 键 | 含义 | 默认 | 谁填 |
|---|---|---|---|
| `film` | 片名，`^[a-z0-9_]+$`；决定 `engine/<film>/`、`eras_<film>.js`、`?film=` | 脚手架 `--film` | 脚手架 |
| `slug` | 配音文件名（`audio/elevenlabs/<slug>.mp3`、`<slug>.cues.json`，即 `el_cued.py` spec 的 slug） | ＝film | 脚手架 |
| `title` / `version` / `deliverable_name` | 中文标题、版本、成片文件名 | `样片-<title>-<version>` | 脚手架 |
| `source` | `{file, lines}` 内容出处 | — | 主会话 |
| `out_root` | 产物根（仓外） | `~/Movies/讲解视频/<项目目录名>/` | 脚手架 `--out-root` |
| `python` / `ffmpeg_bin_dir` | 解释器、ffmpeg 目录 | `~/.venvs/explainer-film/bin/python`、`~/.venvs/explainer-film/bin`（`install.sh` 建的环境，ffmpeg、ffprobe 软链在它的 bin/ 里） | 脚手架 |
| `vendor` | `{path, commit}` | skill 的 vendor、8a0d7d72 | 脚手架 |
| `canvas` | `{width, height, fps}` | 1920×1080@30 | 主会话（竖屏改这里） |
| `voice.engine` | 只有 elevenlabs | elevenlabs | 脚手架 |
| `voice.style` / `content_type` | 合成基调 | "warm, patient, grounded conversational explanation" / teaching | 主会话 |
| `voice.elevenlabs` | `{tts_cued, voice_id_file, model}`：`tts_cued` 为 null＝用 skill 的 `scripts/el_cued.py`（填路径可换成别的同接口脚本）；`voice_id_file` 是 voice ID 文件；`model` 只记录进认可记录，实际模型是 `el_cued.py` 的 `MODEL` | null、`~/.config/elevenlabs/voice-id`、eleven_v4 | 脚手架 |
| `voice.loudness` / `sample_rate` | `{I, TP, LRA}` / 采样率 | −16／−1.5／11；48000 | 脚手架 |
| `timing` | `{head_silence, tail_silence, gaps_ms{base,sentence,question}, max_cue, breaks[], cps, min_cue_s}` | 3.0／1.2／150-450-550／16／[]／标定值／0.6 | `breaks` 主会话 |
| `theme` | 色板、字体、`speed/lw/settle`、`world`、`rows`、`caption`、`paper` → 生成 `engine/<film>/theme.js` | 白板暖纸值 | 主会话按内容改；改后 `new_project.py --theme` |
| `theme.caption.show` | `false`＝画面不画口播字幕（字幕带留空，版式不变） | `true` | 改后 `new_project.py --theme` 再渲 |
| `compose` | `{font_file, review, srt}` | Hiragino、true、true | 脚手架 |
| `draft` | `{ranges: "auto"｜表达式对, target_s, fps, size}` | auto／120／15／960:540 | 主会话可指定 |
| `style` | 画法 id（`templates/styles/<id>/`；本包只有 `whiteboard`）；**有这个键＝新格式工程**：eras 多加载 `wb/style.js`、跑 `style_lint`、视频绑画法指纹 | whiteboard | 脚手架 |
| `assets` | 图片清单（相对 `engine/<film>/`），写进 eras 的 `EXTRA_ASSETS`，引擎启动时载入；场景用 `WB.image(src, …)` 画，没登记直接报错 | `[]`（画法包自带的图片由脚手架复制并登记） | 主会话加图后跑 `make_timing.py` |
| `theme.extra_colors` | 画法包的额外颜色键名，值在 theme 同层；common.js 用 CSS.supports 核，场景经 `WB.C.<键>` 取（白板没有额外颜色） | 画法包 style.json 的 `extra_colors` | 脚手架 |
| `qa` | `{band_top, pop_elements_re, seed, config, gates{…}, record_only[]}` | 见 qa-rules.md | 主会话改元素名正则 |
| `redlines` | `{words, names, extra_targets[]}` | tools/ 下两表＋分镜 md | 脚手架 |
| `stops` | `{script_review, draft_review}` | true／true | 只有用户明说才改 |
| `voice_diff` | `{sample_scene, sample_secs}` | null（自动）／60 | 脚手架 |
| `skill_version` | 写进 build.log 与 manifest | 脚手架 | 脚手架 |

草稿段界表达式只允许 `KEY.start|end`、数字、`+ −`、`min/max`，例：`["0", "min(B3_18.end+0.6, B3_19.start+0.1)"]`。
