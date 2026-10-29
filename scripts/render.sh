#!/bin/bash
# 渲染封装：在 <项目>/engine/ 下调抄来的 render.py --film <片名>（render.py 一字不改）。项目：--project P ＞ EF_PROJECT ＞ cwd 向上找。
#   render.sh [--project P] draft [out.mp4]               草稿档（draft.fps、draft.size，crf23）→ <产物>/review/draft.mp4
#   render.sh [--project P] full  [out.mp4]               canvas.fps 1920×1080 crf18 → <产物>/out/video_only.mp4
#   render.sh [--project P] stills t1,t2,… [目录]         只出这些时刻的 PNG（t001.00.png …）→ 默认 <产物>/review/stills/
#   render.sh [--project P] part a b [out.mp4] [--draft]  只渲 [a,b) 秒（--draft 用草稿档），默认 <产物>/review/part-a-b.mp4
#   任一模式加 --noambient：页面的 WB.ambientT 恒为 0（装饰性持续动作——线 boil、粒子、呼吸——全部冻住），qa.py 的 still_video_source
#     "noambient_draft" 用它出无装饰草稿；render.py 不收页面参数，这里临时写一个包装 eras（engine/eras_<片名>__noamb_<pid>_<随机>.js，设 window.WB_NOAMBIENT
#     再接原 eras 全文）、用 --film <片名>__noamb_<pid>_<随机> 渲。该文件已存在就拒绝（退出 2、不碰它）；退出时只删本次自己新建的那个。
#     EF_NOAMB_ID 可指定 <pid>_<随机> 这一段（^[a-z0-9_]+$，测试用）。
# 色彩：render.py 把 PNG 经 image2pipe 交给 libx264 转 yuv420p 时，ffmpeg 默认按 BT.601 矩阵换算且不写色彩标签；
# 这里渲完后再过一遍 ffmpeg：按 BT.601→BT.709 换算矩阵、写 bt709 标签（tv 范围）。为抵消二次编码，render.py 先按 crf−6 出中间件。
# 版本标签：draft/full/part 出的 mp4 带元数据 explainer_film_timing_sha256（engine/<片名>/timing.js 全文）与 explainer_film_scenes_sha256
# （engine/<片名>/scenes/*.js 按文件名排序后内容拼接），供核对「画面与当前时间轴、场景同版」；
# 另写画法指纹 explainer_film_look_sha256（engine/<片名>/theme.js、wb/common.js、wb/style.js 存在的按此顺序拼接），有 style 键的工程据此核「画面与当前画法同版」。
# 环境：EF_OUT 覆盖产物根目录；python、ffmpeg 目录、片名、帧率都读 project.json（efconfig.py）。
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
[ "${1:-}" = "--project" ] && { export EF_PROJECT="$2"; shift 2; }
EFC() { python3 "$SK/scripts/efconfig.py" "$@"; }
PROJ="$(EFC get project_dir)"; export EF_PROJECT="$PROJ"
ENGINE="$PROJ/engine"; OUT="$(EFC get out_root)"; PY="$(EFC path python)"; FILM="$(EFC get film)"
FPS="$(EFC get canvas.fps)"; DFPS="$(EFC get draft.fps)"; DSIZE="$(EFC get draft.size)"
NOAMB=0; ARGS=(); for x in "$@"; do [ "$x" = --noambient ] && NOAMB=1 || ARGS+=("$x"); done; set -- ${ARGS[@]+"${ARGS[@]}"}
RFILM="$FILM"
if [ "$NOAMB" = 1 ]; then   # 包装 eras：先设 WB_NOAMBIENT 再接原 eras 全文；只删本次自己新建的那个
  NID="${EF_NOAMB_ID:-$$_$RANDOM$RANDOM}"
  [[ "$NID" =~ ^[a-z0-9_]+$ ]] || { echo "EF_NOAMB_ID 须为 ^[a-z0-9_]+$：$NID" >&2; exit 2; }
  RFILM="${FILM}__noamb_${NID}"; WRAP="$ENGINE/eras_${RFILM}.js"; MADE=0
  [ -f "$ENGINE/eras_$FILM.js" ] || { echo "缺 $ENGINE/eras_$FILM.js" >&2; exit 2; }
  trap 'if [ "$MADE" = 1 ]; then rm -f "$WRAP"; fi' EXIT
  { [ ! -e "$WRAP" ] && ( set -C; : > "$WRAP" ) 2>/dev/null; } || { echo "包装文件 $WRAP 已存在（或建不了），拒绝覆盖，未改动它" >&2; exit 2; }
  MADE=1   # noclobber 独占新建成功：这个文件是本次建的
  { echo "window.WB_NOAMBIENT = true;   // render.sh --noambient 临时生成，渲完即删"; cat "$ENGINE/eras_$FILM.js"; } > "$WRAP"
fi
export PATH="$(EFC path ffmpeg_bin_dir):$PATH"
abs() { case "$1" in /*) printf '%s\n' "$1" ;; *) printf '%s/%s\n' "$PWD" "$1" ;; esac; }   # 输出路径一律先转绝对路径：下面要 cd engine

fp() {   # 三行：timing.js 的 sha256、scenes/*.js 排序拼接的 sha256、画法指纹（theme.js＋wb/common.js＋wb/style.js 存在的按序拼接）；文件不在就输出空行
  python3 -c 'import hashlib, sys; from pathlib import Path
d = Path(sys.argv[1]); t = [d / "timing.js"] if (d / "timing.js").is_file() else []
look = [p for p in (d / "theme.js", d / "wb" / "common.js", d / "wb" / "style.js") if p.is_file()]
for ps in (t, sorted((d / "scenes").glob("*.js")), look):
    h = hashlib.sha256(b"".join(p.read_bytes() for p in ps)); print(h.hexdigest() if ps else "")' "$ENGINE/$FILM"
}
fix709() {   # $1 输入（render.py 原样输出）$2 输出 $3 crf $4 输出尺寸 宽:高（空＝原尺寸，草稿档在这一遍里一起缩小）$5 timing 指纹 $6 scenes 指纹 $7 画法指纹
  local wh="${4:-}"
  ffmpeg -y -v error -i "$1" -vf "scale=${wh:+$wh:flags=lanczos:}in_color_matrix=bt601:out_color_matrix=bt709:in_range=tv:out_range=tv,format=yuv420p" \
    -c:v libx264 -preset medium -crf "$3" -pix_fmt yuv420p -x264-params colorprim=bt709:transfer=bt709:colormatrix=bt709 \
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv -movflags +faststart+use_metadata_tags \
    -metadata explainer_film_timing_sha256="$5" -metadata explainer_film_scenes_sha256="$6" -metadata explainer_film_look_sha256="$7" -an "$2"
}
render() {   # $1 输出 mp4；$2 crf；$3 输出尺寸（空＝原尺寸 1920×1080；草稿 960:540）；其余透传给 render.py
  local out crf="$2" wh="$3"; out="$(abs "$1")"; shift 3
  local tmp="${out%.mp4}.raw.mp4" tsha ssha lsha
  mkdir -p "$(dirname "$out")"
  { read -r tsha; read -r ssha; read -r lsha; } < <(fp)   # 渲染前取指纹：标签对应的就是这次渲染读到的时间轴、场景与画法
  ( cd "$ENGINE" && "$PY" render.py --film "$RFILM" --out "$tmp" --crf "$((crf - 6))" "$@" )
  fix709 "$tmp" "$out" "$crf" "$wh" "$tsha" "$ssha" "$lsha"
  rm -f "$tmp"
  echo "→ $out"
}

mode="${1:-}"; shift || true
case "$mode" in
  draft)  render "${1:-$OUT/review/draft.mp4}" 23 "$DSIZE" --fps "$DFPS" ;;
  full)   render "${1:-$OUT/out/video_only.mp4}" 18 "" --fps "$FPS" ;;
  stills) [ -n "${1:-}" ] || { echo "用法：render.sh stills t1,t2,… [目录]"; exit 2; }
          dir="$(abs "${2:-$OUT/review/stills}")"; mkdir -p "$dir"
          ( cd "$ENGINE" && "$PY" render.py --film "$RFILM" --stills "$1" --out "$dir" ) ;;
  part)   a="${1:?起点秒}"; b="${2:?终点秒}"; shift 2
          out="$OUT/review/part-$a-$b.mp4"; draft=0
          for x in "$@"; do case "$x" in --draft) draft=1 ;; *.mp4) out="$(abs "$x")" ;; esac; done
          if [ "$draft" = 1 ]; then render "$out" 23 "$DSIZE" --fps "$DFPS" --from "$a" --to "$b"
          else render "$out" 18 "" --fps "$FPS" --from "$a" --to "$b"; fi ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
