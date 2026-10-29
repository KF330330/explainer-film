#!/bin/bash
# 全链：配音 → 时间轴 → （笔顺）→ 渲染 → 合成 → 机器检查，日志 <产物>/out/build.log。交付成片必须来自一次 --clean 全链。
#   build.sh [--project P] --clean --engine elevenlabs     （项目：--project ＞ EF_PROJECT ＞ cwd 向上找 project.json）
#   --clean    先删掉上一轮的派生产物（out/、audio/narration.wav、cues.json、manifest.json、engine/<片名>/timing.js），
#              不删 audio/approved_voice.json（用户的声音认可记录）和配音引擎自己的请求缓存
#   --engine   配音引擎，只认 elevenlabs；make_audio.py 会核 approved_voice.json，引擎或音色指纹不符就拒绝（整条链停）
#   环境变量 HANZI_WRITER_DATA=<hanzi-writer-data 包目录> 时重抽笔顺（engine/<片名>/wb/strokes.js），没设就沿用项目里的；EF_OUT 覆盖产物根目录。
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
CLEAN=0; ENGINE=""
while [ $# -gt 0 ]; do case "$1" in --clean) CLEAN=1 ;; --engine) ENGINE="$2"; shift ;; --project) export EF_PROJECT="$2"; shift ;; *) echo "未知参数 $1"; exit 2 ;; esac; shift; done
[ -n "$ENGINE" ] || { sed -n '2,8p' "$0"; exit 2; }
[ "$ENGINE" = elevenlabs ] || { echo "--engine 只认 elevenlabs（收到 ${ENGINE}）"; exit 2; }
EFC() { python3 "$SK/scripts/efconfig.py" "$@"; }
PROJ="$(EFC get project_dir)"; export EF_PROJECT="$PROJ"
OUT="$(EFC get out_root)"; PY="$(EFC path python)"; FILM="$(EFC get film)"; NAME="$(EFC get deliverable_name)"
NAME="${NAME:-样片-$(EFC get title)-$(EFC get version)}"; S="$SK/scripts"; P=(--project "$PROJ")
export PATH="$(EFC path ffmpeg_bin_dir):$PATH" PYTHONDONTWRITEBYTECODE=1
if [ "$CLEAN" = 1 ]; then
  rm -rf "$OUT/out" "$OUT/audio/narration.wav" "$OUT/audio/cues.json" "$OUT/audio/manifest.json" "$OUT/audio/.work" "$PROJ/engine/$FILM/timing.js"
fi
mkdir -p "$OUT/out"
{
  echo "== build $(date '+%F %T')  clean=$CLEAN  engine=$ENGINE  out=$OUT  skill_version=$(EFC get skill_version)  vendor=$(EFC get vendor.commit)"
  echo "== 1/6 配音"; "$PY" "$S/make_audio.py" "${P[@]}" --engine "$ENGINE" --out "$OUT"
  echo "== 2/6 时间轴"; "$PY" "$S/make_timing.py" "${P[@]}" --cues "$OUT/audio/cues.json"
  if [ -n "${HANZI_WRITER_DATA:-}" ]; then echo "== 3/6 笔顺"; "$PY" "$S/make_strokes.py" "${P[@]}" --data-dir "$HANZI_WRITER_DATA"
  else echo "== 3/6 笔顺：未设 HANZI_WRITER_DATA，沿用项目里的 engine/$FILM/wb/strokes.js"; fi
  echo "== 4/6 渲染（$(EFC get canvas.fps) fps）"; t0=$(date +%s); bash "$S/render.sh" "${P[@]}" full "$OUT/out/video_only.mp4"; echo "   渲染用时 $(( $(date +%s) - t0 )) s"
  echo "== 5/6 合成"; "$PY" "$S/compose.py" "${P[@]}" --out "$OUT"
  echo "== 6/6 机器检查"; "$PY" "$S/qa.py" "${P[@]}" --video "$OUT/out/$NAME.mp4" --out "$OUT"
  echo "== build 完成 $(date '+%F %T')"
} 2>&1 | tee "$OUT/out/build.log"
