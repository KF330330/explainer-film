# CHANGELOG

## 1.3.3 外发版

由 explainer-film 1.3.3 完整版精简而来：只留白板画法和配音视频，引擎（`vendor/engine`、`vendor/gates`）与出片链不变，三维可选件保留。`project.json` 的 `skill_version` 仍是 1.3.3。

**相对完整版删掉的**

- 另外五种画法包（只留 `templates/styles/whiteboard/`）及画法总览图、画法样片生成与总览拼图脚本、画法选择文档。
- 现场演示版：现场模式、提词页、演示包、帧率预检、停点表生成，以及对应的模板、文档与 `project.json` 的 `live` 键。
- 本机兜底配音引擎及其合成脚本、`project.json` 的对应配置键；`make_audio.py`、`approve_voice.py`、`build.sh` 的 `--engine` 只认 `elevenlabs`。
- 背景音乐混音脚本与文档。
- 样片范例索引文档、单元测试与回归脚本、内部样片的出处与开发记录。
- `new_project.py` 里只用于内部回归的导入旧工程选项。

**改了的**

- 配音不再依赖外部配音工具：新增 `scripts/el_cued.py`，只用标准库加 ffmpeg/ffprobe 直连 ElevenLabs，逐句合成、按样本数精确拼接、带请求缓存；`project.json` 的 `voice.elevenlabs.tts_cued` 为 null 时用它。
- 新增 `scripts/install.sh` 与 `requirements.txt`：环境固定装到 `~/.venvs/explainer-film`（ffmpeg、ffprobe 软链进它的 `bin/`），新工程模板的 `python`、`ffmpeg_bin_dir` 默认指向它。
- `selfcheck.sh` 新增第 2b 项查 ElevenLabs 配置（只看文件属性，不读内容；缺了打印两行配置命令）与 `--no-voice`（只跳过这一项，安装时用）；第 4b 项只查白板画法包。`new_project.py` 建工程时的自检带 `--no-voice`。
- 文档改成给第一次用的人：新增 `README.md`（安装与使用），`SKILL.md` 与 `references/` 去掉已删功能与内部记录，`references/voice.md` 重写为自带 key 与音色、试听认可、费用估算。
