#!/bin/bash
# explainer-film 安装（只支持 macOS）：建 ~/.venvs/explainer-film（与 templates/project.json 的 python、ffmpeg_bin_dir 一致），装 requirements.txt，
# 装 Playwright 的 Chromium，把 ffmpeg、ffprobe 软链进 venv 的 bin/，最后跑 selfcheck.sh --no-voice；随后只查 ~/.config/elevenlabs/{api-key,voice-id}
# 在不在（不读内容），缺了打印怎么配，不算安装失败。不带参数、不提供改目录的参数；可重复运行；全程不写 ~/.config。
# 用法：bash install.sh
# 退出：0 环境装好、selfcheck.sh --no-voice 全过（与 ElevenLabs 配置在不在无关）；2 缺前提（不是 Mac、找不到 ≥3.11 的 Python、没有 ffmpeg／ffprobe），
#       打印一行装法，这时还没建 venv；1 装依赖、装 Chromium 或自检失败。
set -uo pipefail
VENV="$HOME/.venvs/explainer-film"
HERE="${BASH_SOURCE[0]%/*}"; [ "$HERE" = "${BASH_SOURCE[0]}" ] && HERE=.
SK="$(cd "$HERE/.." && pwd)"
[ $# -eq 0 ] || { echo "install.sh 不带参数（环境固定装到 ${VENV}）" >&2; exit 2; }

# 0 前提：macOS、Python ≥3.11（钉死的 numpy 2.4.4 要求）、ffmpeg 与 ffprobe。找的时候跳过本 venv 自己的 bin/（重复运行时它可能在 PATH 里）
OS="$( (/usr/bin/uname || uname) 2>/dev/null )"
[ "$OS" = Darwin ] || { echo "只支持 macOS（这台是 ${OS:-未知系统}）" >&2; exit 2; }
IFS=: read -r -a _parts <<< "$PATH"; NP=""
for p in ${_parts[@]+"${_parts[@]}"}; do [ "$p" = "$VENV/bin" ] || NP="${NP:+$NP:}$p"; done
PATH="$NP"
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  p="$(command -v "$c" 2>/dev/null)" || continue
  read -r major minor < <("$p" -c 'import sys; print(sys.version_info[0], sys.version_info[1])' 2>/dev/null) || continue
  case "$major$minor" in *[!0-9]*|"") continue ;; esac
  if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }; then PY="$p"; break; fi
done
[ -n "$PY" ] || { echo "缺 Python 3.11 或更新版本：brew install python@3.11" >&2; exit 2; }
FF="$(command -v ffmpeg 2>/dev/null)"; FP="$(command -v ffprobe 2>/dev/null)"
[ -n "$FF" ] && [ -n "$FP" ] || { echo "缺 ffmpeg／ffprobe：brew install ffmpeg" >&2; exit 2; }
echo "前提：macOS；Python $("$PY" -c 'import platform; print(platform.python_version())')（${PY}）；ffmpeg ${FF}；ffprobe $FP"

# 1 venv：已有且能跑 ≥3.11 就沿用（只补装依赖）；没有就建；有但坏了或版本太低就 --clear 重建
VPY="$VENV/bin/python"
if [ -x "$VPY" ] && "$VPY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "== 1/5 沿用已有环境 $VENV"
else
  mkdir -p "$HOME/.venvs" || exit 1
  if [ -e "$VENV" ]; then echo "== 1/5 重建环境 ${VENV}（原有的跑不起来或 Python 低于 3.11）"; "$PY" -m venv --clear "$VENV" || exit 1
  else echo "== 1/5 建环境 $VENV"; "$PY" -m venv "$VENV" || exit 1; fi
fi
echo "== 2/5 装依赖（requirements.txt）"
"$VPY" -m pip install --disable-pip-version-check -r "$SK/requirements.txt" || { echo "装依赖失败（看上面 pip 的报错；多半是网络）" >&2; exit 1; }
echo "== 3/5 装 Chromium（playwright install chromium；已装过会很快）"
"$VPY" -m playwright install chromium || { echo "装 Chromium 失败（看上面的报错；多半是网络）" >&2; exit 1; }
echo "== 4/5 软链 ffmpeg、ffprobe 进 $VENV/bin/"
ln -sfn "$FF" "$VENV/bin/ffmpeg" && ln -sfn "$FP" "$VENV/bin/ffprobe" || exit 1
echo "== 5/5 自检（selfcheck.sh --no-voice）"
bash "$SK/scripts/selfcheck.sh" --no-voice || { echo "自检不过：按上面 FAIL 那项的提示处理后再跑一次 install.sh" >&2; exit 1; }

echo
echo "环境装好了：${VENV}（新建工程的 project.json 默认就用它）"
if [ -f "$HOME/.config/elevenlabs/api-key" ] && [ -f "$HOME/.config/elevenlabs/voice-id" ]; then
  echo "ElevenLabs 的 api-key、voice-id 文件都在：再跑一次 bash $SK/scripts/selfcheck.sh 全查（含权限）"
else
  echo "下一步：放好密钥和音色。第一行建目录；再把你的 API key、voice ID 各存成一行纯文本，文件名分别是 ~/.config/elevenlabs/api-key 与 voice-id；第二行收紧权限："
  echo "  mkdir -p ~/.config/elevenlabs && chmod 700 ~/.config/elevenlabs"
  echo "  chmod 600 ~/.config/elevenlabs/api-key ~/.config/elevenlabs/voice-id"
  echo "放好后跑 bash $SK/scripts/selfcheck.sh 全查。"
fi
exit 0
