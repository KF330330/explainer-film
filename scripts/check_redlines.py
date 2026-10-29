#!/usr/bin/env python3
"""红线词扫描。check_redlines.py [--project P] [产物根（缺省 EF_OUT／project.json out_root）]

必扫（缺任一 → 退出 2）：
  1. timeline.json 每个节拍的 say、tts 与事件上屏字 events[].text
  2. project.json redlines.extra_targets 列的文件（相对项目根，缺省 脚本与分镜.md）
有就扫（没有时在汇总里写明没扫到）：
  3. 产物目录 review/scene_text/*.txt（tools/compose.py 写的、每段上板的全部文字）
  4. 产物目录 out/*.srt
词表：redlines.words ＋ redlines.names（缺省 tools/redlines.txt、tools/redlines-names.txt），一行一词（# 开头是注释），逐词按原样做子串匹配（区分大小写）。
命中即打印位置并退出 1；必扫对象缺失退出 2；全部零命中退出 0。
真名表命中时只打印「名单第 N 行」，不把真名写进终端与 build.log。
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import efconfig  # noqa: E402


def load_words(path, masked):
    words = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        w = line.strip()
        if w and not w.startswith("#"):
            words.append((w, f"名单第 {n} 行" if masked else f"「{w}」"))
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    cfg = efconfig.load(a.project)
    PROJ, out = cfg.project_dir, Path(a.out) if a.out else cfg.out_root
    words = load_words(cfg.path("redlines.words", "tools/redlines.txt"), False) + load_words(cfg.path("redlines.names", "tools/redlines-names.txt"), True)
    targets, missing = [], []

    tl = json.loads((PROJ / "timeline.json").read_text(encoding="utf-8"))
    for sc in tl["scenes"]:
        for b in sc.get("beats") or []:
            key = f"{sc['id']}_{b['k']:02d}"
            for field in ("say", "tts"):
                targets.append((f"timeline.json {key}.{field}", b[field]))
            for e in b.get("events") or []:
                if e.get("text"):
                    targets.append((f"timeline.json {key}.events[{e['el']}].text", e["text"]))
    mds = [PROJ / x for x in (cfg.get("redlines.extra_targets") or ["脚本与分镜.md"])]
    missing += [str(m) for m in mds if not m.exists()]
    st = sorted((out / "review" / "scene_text").glob("*.txt"))
    srt = sorted((out / "out").glob("*.srt"))
    for p in [m for m in mds if m.exists()] + st + srt:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            targets.append((f"{p.name}:{n}", line))

    hits = 0
    for where, text in targets:
        for w, label in words:
            if w in text:
                hits += 1
                print(f"命中 {label} @ {where}")
    print(f"红线扫描：词 {len(words)} 个，扫描 {len(targets)} 处（timeline say/tts/上屏字、{'、'.join(m.name for m in mds)}、"
          f"scene_text {len(st)} 个{'（没有，未扫）' if not st else ''}、srt {len(srt)} 个{'（没有，未扫）' if not srt else ''}），命中 {hits} 处")
    if missing:
        print("缺少必扫对象：" + "；".join(missing))
        return 2
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
