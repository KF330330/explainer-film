#!/usr/bin/env python3
"""检查点草稿：按段界分段用 scripts/render.sh part --draft（草稿档 draft.size@draft.fps）渲染后拼接，配上同一时间段的口播。
- 口播：engine/<片名>/timing.js 来自真实配音（TIMING.meta.provisional 为假）且 audio/narration.wav 在 → 按同样的时间段切口播拼上，出 review/draft-1.mp4；
  否则（声音还没被用户认可、timing 是按音节数临时造的）→ 只出无声版 review/draft-1-mute.mp4。
- 段界：project.json draft.ranges——"auto"＝[0, 第一个句尾 ≥ draft.target_s 的节拍句尾 + 0.6]；或 [[起, 止], …] 表达式对，
  表达式只许 节拍号.start|end、数字、+ −、min()/max()（如 "min(B3_18.end+0.6, B3_19.start+0.1)"），其余拒绝（退出 2）。
用法：make_draft.py [--project P] [--out <产物根>] [--ranges "a-b,c-d"]（手动指定段界时用）
"""
import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402


def bad(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def expr(src, B):
    """draft.ranges 的小求值器：只认 节拍号.start|end、数字、+ −、min/max。"""
    def ev(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
            return ev(n.left) + ev(n.right) if isinstance(n.op, ast.Add) else ev(n.left) - ev(n.right)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("min", "max") and n.args and not n.keywords:
            return (min if n.func.id == "min" else max)(ev(x) for x in n.args)
        if isinstance(n, ast.Attribute) and n.attr in ("start", "end") and isinstance(n.value, ast.Name) and n.value.id in B:
            return float(B[n.value.id][n.attr])
        bad(f"draft.ranges 表达式「{src}」里有不允许的写法：{ast.unparse(n)}（只许 节拍号.start|end、数字、+ −、min/max）")
    try:
        return ev(ast.parse(str(src).strip(), mode="eval").body)
    except SyntaxError:
        bad(f"draft.ranges 表达式「{src}」写错了")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write((r.stdout + r.stderr)[-3000:])
        raise SystemExit(f"命令失败：{' '.join(map(str, cmd[:6]))} …")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    ap.add_argument("--ranges", default="")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    out = Path(a.out) if a.out else cfg.out_root
    T = cuelib.read_timing()
    B, R = T["beats"], cfg.get("draft.ranges", "auto")
    if a.ranges:
        ranges = [tuple(float(x) for x in r.split("-")) for r in a.ranges.split(",")]
    elif R == "auto":
        k = next((k for k, b in B.items() if b["end"] >= float(cfg.get("draft.target_s", 120))), list(B)[-1])
        ranges = [(0.0, round(min(B[k]["end"] + 0.6, T["total"]), 3))]
    elif isinstance(R, list) and R and all(isinstance(r, list) and len(r) == 2 for r in R):
        ranges = [(round(expr(x, B), 3), round(expr(y, B), 3)) for x, y in R]
    else:
        bad(f"project.json draft.ranges 要么是 \"auto\"，要么是 [[起, 止], …]：{R!r}")
    FPS = int(cfg.get("draft.fps", 15))   # 草稿帧率；段界对齐到帧网格，画面帧数与口播切片长度才严格相等（不靠 -shortest 截）
    ranges = [(round(round(x * FPS) / FPS, 4), round(round(y * FPS) / FPS, 4)) for x, y in ranges]
    pdir = out / "review" / "draft-parts"
    pdir.mkdir(parents=True, exist_ok=True)
    parts = []
    for x, y in ranges:
        p = pdir / f"part-{x:.2f}-{y:.2f}.mp4"
        print(f"渲染 {x:.2f}–{y:.2f}s …", flush=True)
        run(["bash", str(cfg.skill_dir / "scripts/render.sh"), "--project", str(cfg.project_dir), "part", f"{x}", f"{y}", str(p), "--draft"])
        parts.append(p)
    lst = pdir / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    vid = pdir / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vid)])
    wav = out / "audio" / "narration.wav"
    real = not T.get("meta", {}).get("provisional", True) and wav.exists()
    if real:
        filt = "".join(f"[0:a]atrim={x}:{y},asetpts=PTS-STARTPTS[a{i}];" for i, (x, y) in enumerate(ranges))
        filt += "".join(f"[a{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=0:a=1[a]"
        aud = pdir / "audio.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-filter_complex", filt, "-map", "[a]", "-c:a", "pcm_s16le", str(aud)])
        dst = out / "review" / "draft-1.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(aud), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(dst)])
    else:
        dst = out / "review" / "draft-1-mute.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-c", "copy", "-movflags", "+faststart", str(dst)])
    d = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)]).stdout.strip())
    info = {"draft": str(dst), "with_voice": real, "ranges": ranges, "duration": round(d, 3), "timing_meta": T.get("meta")}
    (out / "review" / "draft-1.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"草稿 {dst}：{d:.1f}s，{'带声' if real else '无声（声音未认可，timing 为临时）'}，段 {ranges}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
