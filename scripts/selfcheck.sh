#!/bin/bash
# explainer-film 前提自检（只写临时目录）：1 字体（主题 required_fonts 浏览器实测＋审片字体文件，缺即停）；2 Python 依赖与 ffmpeg；
# 2b ElevenLabs 配置（~/.config/elevenlabs/ 归本人、组与其他人不可写；api-key、voice-id 是本人的非空普通文件、权限 600；只看属性不读内容；
#    缺了打印两行配置命令；--no-voice 只跳过这一项，安装时还没放密钥用它）；
# 3 vendor 零改动（manifest 抽核 20 个 sha256，--full-manifest 全核）；4 参考片 wbx 出帧 1,5 非纯色；
# 4b 白板画法包 whiteboard 文件齐全（style.json 合法、style.js、idioms.md、sample_scenes/*.js、preview.jpg）；
# 带 --project 再加：5 八个软链目标在；6 本片出帧 0,2（无页面错误、非纯色）；7 efconfig get out_root；
#   project.json 有 style 键（新格式工程）再加：8 engine/<片名>/wb/style.js 在、画法包 style.json 的 required_fonts 浏览器实测都在。
# 用法：selfcheck.sh [--project P] [--tmp DIR] [--full-manifest] [--no-voice]；退出 0 全过、2 有一项不过（逐项打印 PASS/FAIL 与耗时）
set -uo pipefail
SK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="" TMPD="" FULL=0 STYLE="" NOVOICE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --tmp) TMPD="$2"; shift 2 ;;
    --full-manifest) FULL=1; shift ;;
    --no-voice) NOVOICE=1; shift ;;
    *) echo "selfcheck: 不认识的参数 $1" >&2; exit 2 ;;
  esac
done
export PYTHONDONTWRITEBYTECODE=1
EFC() { python3 "$SK/scripts/efconfig.py" --project "$PROJECT" "$@"; }
if [ -n "$PROJECT" ]; then
  PROJECT="$(cd "$PROJECT" && pwd)" || exit 2
  PY="$(EFC path python)" || exit 2; FFDIR="$(EFC path ffmpeg_bin_dir)" || exit 2
  FILM="$(EFC get film)" || exit 2; FONTFILE="$(EFC get compose.font_file)" || exit 2
  FONTS="$(EFC get theme.required_fonts)" || exit 2; ENG="$PROJECT/engine"
  STYLE="$(EFC get style 2>/dev/null || true)"
else
  { read -r PY; read -r FFDIR; read -r FONTFILE; read -r FONTS; } < <(python3 - "$SK/templates/project.json" <<'EOF'
import json, os, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(os.path.expanduser(d["python"]), os.path.expanduser(d["ffmpeg_bin_dir"]), d["compose"]["font_file"],
      json.dumps(d["theme"]["required_fonts"], ensure_ascii=False, separators=(",", ":")), sep="\n")
EOF
)
  ENG="$SK/vendor/engine"
fi
OWN_TMP=0; if [ -z "$TMPD" ]; then TMPD="$(mktemp -d -t ef-selfcheck)"; OWN_TMP=1; fi
mkdir -p "$TMPD" || exit 2
export PATH="$FFDIR:$PATH"
FAILS=0
now() { python3 -c 'import time; print(int(time.time() * 1000))'; }   # 毫秒整数（bash 3.2 只会整数运算）
secs() { printf '%d.%02d' $(( $1 / 1000 )) $(( ($1 % 1000) / 10 )); }
step() {   # step 名称 命令…：输出进 $TMPD/step-N.log，打印 PASS/FAIL 与耗时，失败时打印日志末尾
  local name="$1"; shift; local t0 t1 log="$TMPD/step-$((++N)).log"; t0=$(now)
  local rc=0; "$@" >"$log" 2>&1 || rc=$?; t1=$(now); local el; el="$(secs $((t1 - t0)))"
  if [ $rc -eq 0 ]; then echo "PASS  ${name}  ${el}s"; else echo "FAIL  ${name}  ${el}s"; tail -15 "$log" | sed 's/^/      /'; FAILS=$((FAILS + 1)); fi
}
N=0
nonflat() { "$PY" -c 'import sys, numpy as np; from PIL import Image
for p in sys.argv[1:]:
    a = np.asarray(Image.open(p).convert("RGB"), dtype=float); s = float(a.std()); print(p, "std", round(s, 2))
    assert s > 2.0, p + " 近乎纯色"' "$@"; }
fonts() {
  [ -f "$FONTFILE" ] || { echo "审片字体文件不在：${FONTFILE}"; return 1; }
  browser_fonts "$FONTS"
}
browser_fonts() {   # $1 字体名 JSON 数组：浏览器里逐个实测（与 monospace 回退宽度不同才算在）
  "$PY" - "$1" <<'EOF'
import json, sys
from playwright.sync_api import sync_playwright
names = json.loads(sys.argv[1])
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    miss = pg.evaluate("""async (names) => { const q = n => /^[A-Za-z][A-Za-z0-9-]*$/.test(n) ? n : `"${n}"`, g = document.createElement('canvas').getContext('2d'), out = [];
      for (const n of names) { await document.fonts.load(`64px ${q(n)}`, '测0'); g.font = `64px ${q(n)}, monospace`; const a = g.measureText('AIxyz0123①≠测试').width;
        g.font = '64px monospace'; if (Math.abs(a - g.measureText('AIxyz0123①≠测试').width) < 0.5) out.push(n); } return out; }""", names)
    b.close()
print("画面字体", names, "缺：", miss or "无")
sys.exit(1 if miss else 0)
EOF
}
tools() { [ -x "$PY" ] || { echo "Python 不在：${PY}"; return 1; }; "$PY" -c 'import playwright, numpy, cv2, PIL; print("python ok")' && "$FFDIR/ffmpeg" -hide_banner -version | head -1; }
manifest() {
  python3 - "$SK/vendor" "$FULL" <<'EOF'
import hashlib, json, random, sys
from pathlib import Path
root, full = Path(sys.argv[1]), sys.argv[2] == "1"
m = json.loads((root / "vendor_manifest.json").read_text(encoding="utf-8"))
keys = sorted(m["files"]); pick = keys if full else random.sample(keys, min(20, len(keys)))
bad = [k for k in pick if not (root / k).is_file() or hashlib.sha256((root / k).read_bytes()).hexdigest() != m["files"][k]]
print(f"vendor 核 {len(pick)}/{len(keys)} 个文件，不符 {len(bad)}：{bad}")
sys.exit(1 if bad else 0)
EOF
}
packs() {   # 白板画法包文件齐全：templates/styles/whiteboard/ 有 style.json（字段合法）、style.js、idioms.md、sample_scenes/*.js、preview.jpg
  python3 -B - "$SK" <<'EOF'
import sys
from pathlib import Path
sk = Path(sys.argv[1]); sys.path.insert(0, str(sk / "scripts"))
import new_project
s = "whiteboard"; d = sk / "templates" / "styles" / s; bad = []
if not d.is_dir():
    bad.append(f"缺画法包目录 templates/styles/{s}/")
else:
    bad += [f"{s}/{n}" for n in ("style.json", "style.js", "idioms.md", "preview.jpg") if not (d / n).is_file()]
    bad += [] if list((d / "sample_scenes").glob("*.js")) else [f"{s}/sample_scenes/*.js"]
    try:
        (d / "style.json").is_file() and new_project.load_style(s)
    except new_project.Fail as e:
        bad.append(str(e))
print(f"画法包 {s}：缺或不合法：{bad or '无'}")
sys.exit(1 if bad else 0)
EOF
}
voice_help() {
  echo "怎么配 ElevenLabs：第一行建目录；再把你的 API key、voice ID 各存成一行纯文本，文件名分别是 ~/.config/elevenlabs/api-key 与 voice-id；第二行收紧权限："
  echo "  mkdir -p ~/.config/elevenlabs && chmod 700 ~/.config/elevenlabs"
  echo "  chmod 600 ~/.config/elevenlabs/api-key ~/.config/elevenlabs/voice-id"
}
voice() {   # ElevenLabs 配置：只看目录与文件的属性（类型、属主、权限、大小），不读内容
  python3 - "$HOME/.config/elevenlabs" <<'EOF' && return 0
import os, stat, sys
d, bad = sys.argv[1], []
try:
    st = os.lstat(d)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
        bad.append(f"{d}/ 要是本人的目录、组与其他人不可写（chmod 700）")
except FileNotFoundError:
    bad.append(f"缺目录 {d}/")
for n in ("api-key", "voice-id"):
    p = os.path.join(d, n)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        bad.append(f"缺 {p}")
        continue
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
        bad.append(f"{p} 要是本人的普通文件（不能是软链）")
    elif st.st_mode & 0o077:
        bad.append(f"{p} 权限要 600（现在 {stat.S_IMODE(st.st_mode):o}）")
    elif st.st_size == 0:
        bad.append(f"{p} 是空文件")
print("ElevenLabs 配置：" + ("；".join(bad) if bad else "目录与 api-key、voice-id 都在、权限对（未读内容）"))
sys.exit(1 if bad else 0)
EOF
  voice_help; return 1
}
ref() { (cd "$ENG" && "$PY" render.py --film wbx --stills 1,5 --out "$TMPD/wbx") && nonflat "$TMPD/wbx/t001.00.png" "$TMPD/wbx/t005.00.png"; }
links() { local d bad=0; for d in lib scenes demos spacex spacex_wb transitions clips examples; do [ -e "$ENG/$d" ] || { echo "缺 engine/${d}（软链目标不在？跑 new_project.py --relink）"; bad=1; }; done; return $bad; }
film() { (cd "$ENG" && "$PY" render.py --film "$FILM" --stills 0,2 --out "$TMPD/film") && nonflat "$TMPD/film/t000.00.png" "$TMPD/film/t002.00.png"; }
outroot() { local o; o="$(EFC get out_root)" && [ -n "$o" ] && echo "out_root=${o}"; }
style() {   # 新格式工程：wb/style.js 在；画法包 style.json 的 required_fonts 浏览器实测
  local sj="$SK/templates/styles/$STYLE/style.json" rf
  [ -f "$ENG/$FILM/wb/style.js" ] || { echo "缺 engine/${FILM}/wb/style.js（new_project.py --dest <项目> --theme 会按 style 键重拷）"; return 1; }
  [ -f "$sj" ] || { echo "画法包不在：${sj}"; return 1; }
  rf="$(python3 -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8"))["required_fonts"], ensure_ascii=False))' "$sj")" || return 1
  browser_fonts "$rf"
}

step "1 字体（画面三种＋审片字体文件）" fonts
[ $FAILS -eq 0 ] || { echo "字体不全：本 skill 只在装了这些字体的 macOS 上能用，先装字体再来"; exit 2; }
step "2 工具（Python 依赖、ffmpeg）" tools
if [ "$NOVOICE" = 1 ]; then echo "SKIP  2b ElevenLabs 配置（--no-voice）"; else step "2b ElevenLabs 配置（~/.config/elevenlabs/）" voice; fi
step "3 vendor 零改动（sha256 抽核）" manifest
step "4 参考片 wbx 出帧 1,5" ref
step "4b 白板画法包文件齐全" packs
if [ -n "$PROJECT" ]; then
  step "5 引擎软链" links
  step "6 本片 ${FILM} 出帧 0,2" film
  step "7 efconfig get out_root" outroot
  [ -n "$STYLE" ] && step "8 画法包 ${STYLE}（wb/style.js、required_fonts）" style
fi
if [ $FAILS -eq 0 ]; then echo "自检全过（临时目录 ${TMPD}）"; [ $OWN_TMP -eq 1 ] && rm -rf "$TMPD"; exit 0; fi
echo "自检不过 ${FAILS} 项（日志与出帧留在 ${TMPD}）"; exit 2
