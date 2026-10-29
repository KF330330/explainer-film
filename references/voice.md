# 配音：ElevenLabs、声音认可、读法稿、费用

> 何时读：第 ② 步（口播稿定稿时同时做声音认可）与第 ④ 步（批量合成）之前；第一次配 ElevenLabs 时。

## 用你自己的 ElevenLabs 账号与音色

- **要两样东西**：
  - **API key**：在 ElevenLabs 网站的个人设置里建（API Keys），权限要含文字转语音（Text to Speech）。
  - **voice ID**：20 位字母数字，在 Voices 页面点开一个声音就能复制。声音两种来源都行：
    - **即时克隆**（Instant Voice Cloning）：在 Voices 里上传或现录一段讲者本人清晰的人声，得到你账户里的一个克隆声。讲解片用讲者本人的声音最自然。
    - **声音库**（Voice Library）里的现成声音：先加到你自己的 Voices 里，再复制它的 voice ID。
- **放在哪**：`~/.config/elevenlabs/api-key`（一行 key）、`~/.config/elevenlabs/voice-id`（一行 voice ID），目录 700、文件 600。`selfcheck.sh` 缺配置时会打印两行命令照做：
  ```
  mkdir -p ~/.config/elevenlabs && chmod 700 ~/.config/elevenlabs
  chmod 600 ~/.config/elevenlabs/api-key ~/.config/elevenlabs/voice-id
  ```
  第一行建目录；然后用文本编辑器把 key、voice ID 各存成一行（文件名 `api-key`、`voice-id`）；第二行收紧权限。`selfcheck.sh` 第 2b 项只看这两个文件在不在、权限对不对，不读内容。
- **合成链**：`make_audio.py --engine elevenlabs` → `scripts/el_cued.py`（`project.json` 的 `voice.elevenlabs.tts_cued` 为 null 时用它）。逐句送 ElevenLabs 合成（模型 `eleven_v4`，`project.json` 的 `voice.style` 作为风格标签放在每句前面），各句解码成样本后按气口拼成一条，cue 起止按样本数精确算。
  - voice ID 从 `voice.elevenlabs.voice_id_file` 读出后只放进子进程环境变量 `ELEVENLABS_TTS_VOICE_ID`，不写盘、不打印；`cues.json`、缓存记录里只有它的 sha256 前 12 位（音色指纹）。密钥由 `el_cued.py` 自己读（也认环境变量 `ELEVENLABS_API_KEY`）。
  - spec 里 `provider` 必须是 `"elevenlabs"`，否则 `el_cued.py` 退出 2。
  - 气口：句间 150 ms；读法稿以句末标点结尾抬到 450 ms，问号 550 ms（`project.json` 的 `timing.gaps_ms` 与它同值）。
- **只走 ElevenLabs，没有兜底引擎**：缺 key、密钥无效（401）、额度不足（402）、音色不对（404）、限流（429）或网络不通时，`make_audio.py` 退出 2、整条链停，错误在 `<产物根>/audio/.work/tts_cued.log`。修好再跑：已经合成过的句子在缓存里，不重复花钱。
- **合成文本会发到 ElevenLabs 云端**：口播稿里不能有客户数据或真人姓名（红线表管这个）。

## 声音认可（批量合成的门禁）

- 全局记录 `~/.config/explainer-film/approved_voice.json`（目录 700、文件 600）：`voices["elevenlabs:<voice_fp>"]`，指纹＝voice-id 文件内容（去空白）的 sha256 前 12 位；每条带 `sample`（试听文件的副本）、`approved_at`、`approved_by`（用户原话）。环境变量 `EF_VOICE_REGISTRY` 可把它换到别处（试用、测试时用）。
- 第一次用一个音色（或换了 voice-id）的路子：
  1. `approve_voice.py check`：全局记录里没有当前音色 → 退出 3。
  2. `approve_voice.py sample`：取 timeline 前 ≤8 句、总长 ≤40 s 合成 `<产物根>/review/试听-elevenlabs-<指纹>.mp3` 并 `open`；**与分镜 md 一起在停点 1 给用户**。
  3. 用户听完点头 → `approve_voice.py record --quote "<用户原话>"`：写全局与项目两份记录；没有原话拒写。
  4. 再 `approve_voice.py check` → 退出 0，复制成项目 `audio/approved_voice.json`。以后别的项目用同一个音色，第 1 步就直接过，不再试听。
- `make_audio.py` 启动先核项目 `audio/approved_voice.json` 的引擎与指纹，不符退出 4；换音色＝指纹变＝重走 sample。

## 费用怎么估

- ElevenLabs 按送去合成的文字计费。每句送去的是「风格标签＋读法稿」；每次真请求的回包里如果带了实际计费字数，就记在 `<产物根>/audio/elevenlabs/cache/*.json` 的 `generation.character_cost_header`，可据此核实际用量。
- 一支片的用量≈读法稿总字数（正式配音一次）＋试听那几句（第一次用这个音色时）＋重录的句子。缓存命中不发请求、不计费：同一句、同一音色、同一风格标签再合成就走缓存；`--force` 的句子必重发。`<slug>.cues.json` 里的 `requests_sent`、`cache_hits` 是这一次实际发了几条、命中几条。
- 试听不进缓存：`approve_voice.py sample` 在临时目录里合成、用完即删，正式配音（`make_audio.py`）会把这几句再合成一遍、再计一次费。口播 ≤8 句、≤40 s 的短片，试听就是全片，第一次用一个音色时一支短片约计费两遍全片字数。
- 粗算：中文口播约 3.8 字/秒，1 分钟成片约 230 字；5 分钟成片约 1,200 字，加上试听与少量重录约 1,500 字。对照自己套餐的月额度估。

## 读法稿（tts）

- 数字写读法（92.2% → 百分之九十二点二；7 轮 → 七轮）；英文人名、机构名保留英文；禁加拼音、IPA、SSML，也不要写方括号（方括号会被当成语气标签，`el_cued.py` 直接拒绝）。英文里的连字符（GPT-6、always-on）送合成前自动换成空格，字幕不变。
- 听出读错的字才在 `tts` 里换同音字（`say` 不动），或写进 `tools/tts_overrides.json`：`{"B2_02": {"tts": "…"}}`（只许改标点、空格）；整拍连读更自然的句子用 `whole_beats`（整句合成后按静音谷切回子 cue，切法记在 manifest）。
- 重合成某几句：`make_audio.py --engine elevenlabs --force B3_15d,B5_02`（走 `force_regenerate`）；缓存全中时不调接口、不花钱。
- 产物：`audio/narration.wav`（48 kHz 单声道，两遍 loudnorm −16 LUFS／−1.5 dBTP，前置 3 s、后置 1.2 s 静音）、`audio/cues.json`（每 cue 全片绝对秒）、`audio/manifest.json`（引擎、指纹、每句时长、请求 ID）、`audio/elevenlabs/`（`<slug>.mp3`、`<slug>.cues.json`、`cache/`）。

## 验收口径

逐句听，或用手边的语音转写工具逐句转写后比对：拼音去声调、数字转读法后比（`scripts/voice_diff.py` 的 `norm()`、`syllables()` 就是这套归一）；音节编辑距离 ≤2 记为转写格式／多音字差异（列出），>2 为真读错，两次重合成仍错则切片给用户听，由用户定。`voice_diff.py` 的 `check`、`sample` 子命令要用环境变量 `EF_TRANSCRIBE_CMD` 指定一个转写命令（调用约定 `<命令> --foreground --output-dir <目录> -- <音频文件…>`，每个音频在目录里写同名 `.txt`）；本包不带转写工具，没设这个变量时它们退出 2，就人工逐句听。
