#!/usr/bin/env python3
"""分镜检查（1.3.0，第 ② 步写完 timeline 与分镜后跑；qa.py 的 storyboard 项也调它）：每拍的画面类型（timeline look）是否按规矩轮换。
违规（退出 1）：require_look 下有拍缺 look；类型不在词表；同一种连续 > max_same_run_s；种类数 < min_kinds（口播总长 <40 s 时用 min_kinds_under_40s）；
  look 写法不对（数组后项的 at 不在 say 里恰好一次等）；脚本与分镜.md 的镜头表表头没有「画面类型」列；project.json 的 assets 非空而 CREDITS.md
  缺任一文件名的行、或该行「许可」列为空。
只记录（打印不拦）：各类占比；count 事件所在拍只有 图表／字卡 时提示「数字没落到东西上」。
老工程（project.json 无 storyboard 键）打印 STORYBOARD: skipped 退出 0；脚手架（timeline 只有片头段）打印 STORYBOARD: scaffold，只核词表与 look 写法、退出 0；
storyboard.require_look 为 false 且 timeline 一个 look 都没有打印 STORYBOARD: not required，不核任何一项、退出 0
（require_look 为 false 但写了部分 look 的照常核词表、连续、种类、镜头表与原件，只是不核缺 look）。qa.py 对这三种都记 INFO。
时刻与画面段的算法见 storyboard.py。输入错（timeline／cues 读不了或对不上、storyboard 段不合法）退出 2。
用法：check_storyboard.py [--project P] [--cues <产物根>/audio/cues.json] [--json <路径>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import efconfig  # noqa: E402
import storyboard  # noqa: E402

EMPTY = {"", "—", "-", "–", "－"}


def md_tables(text):
    """markdown 表格：[(表头单元格, [行单元格…])]；表头行的下一行须是 |---| 分隔行。"""
    lines, out, i = text.splitlines(), [], 0
    cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]  # noqa: E731
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            head, rows, i = cells(lines[i]), [], i + 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append((head, rows))
        else:
            i += 1
    return out


def check_files(cfg):
    """分镜表头与 CREDITS.md：返回违规说明列表。"""
    bad, d = [], cfg.project_dir
    sb = d / "脚本与分镜.md"
    if not sb.is_file():
        bad.append("缺 脚本与分镜.md（镜头表要有「画面类型」列）")
    elif not any("画面类型" in head for head, _ in md_tables(sb.read_text(encoding="utf-8"))):
        bad.append("脚本与分镜.md 的镜头表表头没有「画面类型」列（模板：| 时间段 | 画面类型 | 画面里的物 | 它在做什么 | 镜头 | 屏上字 | 做法 |）")
    assets = [a for a in (cfg.get("assets") or []) if isinstance(a, str)]
    if not assets:
        return bad
    cr = d / "CREDITS.md"
    if not cr.is_file():
        return bad + [f"project.json 登记了 {len(assets)} 个原件（assets），但没有 CREDITS.md"]
    rows = []
    for head, rs in md_tables(cr.read_text(encoding="utf-8")):
        if "文件" in head and "许可" in head:
            fi, li = head.index("文件"), head.index("许可")
            rows += [(r[fi].strip("` "), r[li]) for r in rs if len(r) > max(fi, li)]
    for a in assets:
        hit = [lic for f, lic in rows if f and Path(f).name == Path(a).name]
        if not hit:
            bad.append(f"CREDITS.md 没有原件「{a}」的行（表头要有「文件」「许可」列）")
        elif all(lic.strip() in EMPTY for lic in hit):
            bad.append(f"CREDITS.md 里原件「{a}」那行的「许可」列是空的")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="分镜画面类型检查（timeline look＋镜头表＋原件出处）")
    ap.add_argument("--project")
    ap.add_argument("--cues", help="cues.json 路径（缺省 <产物根>/audio/cues.json；不在就按音节数临时估时）")
    ap.add_argument("--json", help="结果另存为 JSON")
    a = ap.parse_args(argv)
    cfg = efconfig.load(a.project)
    res = {"status": None, "time_source": None, "total": None, "speech_s": None, "segments": [], "stats": None, "violations": [], "hints": [], "notes": []}

    def done(code, line):
        print(line)
        if a.json:
            Path(a.json).parent.mkdir(parents=True, exist_ok=True)
            Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return code

    if "storyboard" not in cfg.data:
        res["status"] = "skipped"
        return done(0, "STORYBOARD: skipped（project.json 无 storyboard 键）")
    try:
        looks = storyboard.load_looks(cfg, a.cues)
    except storyboard.StoryboardInputError as e:
        res["status"] = "input_error"
        res["violations"] = [str(e)]
        return done(2, f"STORYBOARD: 输入错：{e}")
    st = storyboard.stats(looks)
    viol = st["violations"] + ([] if looks["scaffold"] or looks["not_required"] else check_files(cfg))
    res.update(time_source=looks["time_source"], total=looks["total"], speech_s=looks["speech_s"], segments=looks["segments"],
               stats={k: st[k] for k in ("kinds", "n_kinds", "longest_run", "share")}, violations=viol, hints=st["hints"], notes=looks["notes"])
    print(f"时刻来源：{looks['time_source']}；片长 {looks['total']:.2f}s，口播 {looks['speech_s']:.2f}s")
    print("| 拍 | 起止 | 画面类型 |\n|---|---|---|")
    for s in looks["segments"]:
        print(f"| {s['beat']} | {s['t0']:.2f}–{s['t1']:.2f}s | {s['type']} |")
    lr = st["longest_run"]
    print(f"统计：{st['n_kinds']} 种（{'、'.join(st['kinds']) or '无'}）；最长连续 "
          + (f"「{lr['type']}」{lr['s']:.1f}s（{lr['t0']:.1f}–{lr['t1']:.1f}s）" if lr else "无")
          + "；占比 " + "、".join(f"{k} {v:.0%}" for k, v in st["share"].items()))
    for n in looks["notes"]:
        print("备注：" + n)
    for h in st["hints"]:
        print("提示：" + h)
    for v in viol:
        print("违规：" + v)
    if viol:
        res["status"] = "FAIL"
        return done(1, f"STORYBOARD: FAIL（{len(viol)} 条违规）")
    if looks["not_required"]:
        res["status"] = "not_required"
        return done(0, "STORYBOARD: not required（require_look=false 且 timeline 无 look）")
    if looks["scaffold"]:
        res["status"] = "scaffold"
        return done(0, "STORYBOARD: scaffold（只有片头拍，待写分镜）")
    res["status"] = "PASS"
    return done(0, f"STORYBOARD: PASS（{st['n_kinds']} 种，最长连续 {lr['s']:.1f}s）")


if __name__ == "__main__":
    sys.exit(main())
