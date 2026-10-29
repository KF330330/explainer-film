# explainer-film（白板版）· 安装与使用说明

## 这是什么

一个 Claude Code 的 skill：把一篇文章、一份报告、一个提纲或者一个主题，做成**白板手绘风格、全程动画、带配音**的讲解视频（1080p mp4，附 srt 字幕）。

- 画面：一整块暖白纸板、一台相机。字按笔顺一笔一画写出来，线按笔速画出来，数字跟着口播落定（落在念到它的那一句或那一小段里），相机在板上推拉横移。
- 配音：用你自己 ElevenLabs 账户里的声音（讲者本人的即时克隆声，或声音库里的声音）。
- 质量：内建机器检查（死帧、动作对位、数字落定、版面、字幕、音画同步等），全过才出成片。

适合拿来做：课程讲解、内部分享、方法与流程说明、数据结论讲解——有一条主线、能边讲边画的内容。
不太适合：要靠真实照片或产品界面撑场的、要强烈情绪氛围的宣传片、通篇是密集表格或代码的内容。

## 前提

- **macOS**（Apple 芯片或 Intel 都行）。要用到系统自带的 Songti SC、PingFang SC、Georgia、Hiragino Sans GB 字体，macOS 默认就有。
- **Claude Code**（终端版）。
- **Homebrew**，用它装 Python 3.11 以上与 ffmpeg：`brew install python@3.11 ffmpeg`。
- **ElevenLabs 账号**：一个 API key（权限要含文字转语音），加一个 voice ID。用讲者本人的即时克隆声，要选支持声音克隆的套餐；用声音库里的声音也要付费套餐（按 ElevenLabs 的说明，免费账号不能经 API 用声音库的声音）。
- 磁盘约 1 GB（Python 环境约 330 MB，Chromium 约 500 MB）；安装时要联网下载 Python 包与 Chromium。

## 四步安装

1. **放到 skills 目录**：解压后把 `explainer-film` 文件夹整个放到 `~/.claude/skills/` 下，结果是 `~/.claude/skills/explainer-film/`：
   ```
   mkdir -p ~/.claude/skills && cp -R explainer-film ~/.claude/skills/
   ```
2. **装环境**：
   ```
   bash ~/.claude/skills/explainer-film/scripts/install.sh
   ```
   它会建 `~/.venvs/explainer-film`、装 Python 依赖（版本已钉死）、装无头浏览器 Chromium、把 ffmpeg 与 ffprobe 链进这个环境，最后跑一遍自检（这一步不查密钥）。缺前提时它只打印一行装法并停下（比如 `brew install python@3.11`、`brew install ffmpeg`），装好再跑一次即可；可以重复运行。
3. **放好 ElevenLabs 的 key 和 voice ID**：
   ```
   mkdir -p ~/.config/elevenlabs && chmod 700 ~/.config/elevenlabs
   ```
   然后用文本编辑器新建两个纯文本文件，各写一行：`~/.config/elevenlabs/api-key` 写 API key，`~/.config/elevenlabs/voice-id` 写 voice ID（在 ElevenLabs 的 Voices 页面点开声音就能复制，20 位字母数字）。最后收紧权限：
   ```
   chmod 600 ~/.config/elevenlabs/api-key ~/.config/elevenlabs/voice-id
   ```
4. **自检**：
   ```
   bash ~/.claude/skills/explainer-film/scripts/selfcheck.sh
   ```
   全部 PASS 就装好了。哪一项 FAIL，它会打印原因和该怎么做（缺 ElevenLabs 配置时会打印第 3 步那两行命令）。

## 怎么用

在 Claude Code 里（先进到你想放工程的目录），对它说「**把这篇做成讲解视频**」，再给内容：贴一段文字、给一个文件路径，或者只给一个主题。中途它会停两次等你：

- **停点 1**：给你看分镜（`脚本与分镜.md`，口播稿和每个镜头画什么）；第一次用这个声音时还会附一段约 30 秒的试听，你听完说「可以」，它就记下这个声音已认可，以后同一个声音不再试听。口播稿从这里起锁定，之后不改字。
- **停点 2**：给你看约 2 分钟的带声草稿，你点头后它才渲全片。

其余的（写画面代码、配音、渲染、审片、机器检查）它自己做完，最后打开成片并给你一段交付说明。不满意可以直接说哪里要改。

## 产物在哪

- **工程目录**：在你让它放的地方，里面是口播稿与分镜（`timeline.json`、`脚本与分镜.md`）、配置（`project.json`）和画面代码（`engine/`）。
- **产物**：默认在 `~/Movies/讲解视频/<工程目录名>/`：
  - `out/<片名>.mp4` 成片、同名 `.srt` 字幕、`qa.json` 机器检查结果、`build.log` 全链日志；
  - `review/` 草稿与审片材料，`audio/` 配音与缓存。

## 耗时与费用

- **耗时**：1 分钟左右的片子约 2 小时，大部分是 Claude 写画面代码与审片；一次全片渲染 7–18 分钟。5 分钟的片子约一个工作日（全片渲染约 40 分钟）。
- **ElevenLabs**：按送去合成的字数计费。一支片的用量≈口播字数＋第一次试听的那几句＋重录的句子；同一句重跑走缓存，不重复计费。中文口播约 230 字/分钟，5 分钟成片连试听与少量重录约 1,500 字，对照自己套餐的月额度估。
- **Claude Code**：按你自己的套餐计用量；画面代码由 Opus 子代理写，是用量的大头。

## 限制

- 只支持 macOS（字体与脚本都按 Mac 写）。
- 只有白板手绘一种画法。
- 配音只走 ElevenLabs，没有本机兜底配音；ElevenLabs 不通时整条链停下，修好再跑（已合成的句子不重复花钱）。
- 口播稿会发到 ElevenLabs，不要放客户数据或真人姓名。
- 以中文口播为主（笔顺、字体、读法规则都按中文写）。

## 卸载

```
rm -rf ~/.claude/skills/explainer-film ~/.venvs/explainer-film
```
ElevenLabs 配置在 `~/.config/elevenlabs/`，声音认可记录在 `~/.config/explainer-film/`，不要了一并删掉。Chromium 在 `~/Library/Caches/ms-playwright/`，其他程序也可能在用，确认没用再删。

## 第三方许可

动画引擎来自开源项目 huashu-art-motion（MIT），字体为 SIL OFL 1.1，笔顺数据为 Arphic Public License，three.js 为 MIT。来源、版本与许可细节见 `vendor/VENDOR.md` 与 `vendor/engine/lib/fonts/LICENSES.md`。
