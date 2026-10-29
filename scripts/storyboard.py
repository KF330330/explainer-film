#!/usr/bin/env python3
"""分镜的画面类型（timeline 每拍的 look）：读出画面段、按时刻查类型、统计并判违规（1.3.0）。check_storyboard.py、qa.py、compose.py 共用。

look 写法（词表＝project.json storyboard.vocab）：
  拍级 "look": "图表"（整拍一种），或 [{"type": "图表"}, {"type": "原件", "at": "按每年"}]——首项从拍首起，后项从 at 词开口时刻起；
  at 在该拍 say 里须恰好出现一次，开口时刻＝make_timing.char_times 按 cue 摊到该词首字的起点（与 events 的 at 同一解析）。
  beats: [] 的片头段写场景级 "look"（从 0 秒起，时长＝hold_secs，实际到下一段起点）；有拍的场景写拍级，场景级 look 不用。
画面段：第 i 段从自己起点到下一段起点，最后一段到片尾（末 cue end＋timing.tail_silence，同 make_timing）；第一段一律从 0 秒起（盖住片头静音）。
  相邻同类合并后算「同一种连续」。
时刻：cues_path 指向的 cues.json 在就用它；不在（或没给）用 provisional_cues.estimate 的临时时刻（只算不写）。拍起止取该拍 cue 首末。
脚手架：timeline 里全是 kind=="title" 的片头段（new_project 刚建、还没写分镜）＝scaffold，只核词表与 look 写法，不核缺 look、种类数与连续时长。
未要求：storyboard.require_look 为 false 且 timeline 里一个 look 都没有＝not_required，不产生任何违规；
  require_look 为 false 但写了部分 look 的，照常按已有 look 核词表、连续与种类（只是不核缺 look）。

库：
  load_looks(cfg, cues_path=None) -> {"present", "scaffold", "not_required", "segments": [{"beat","type","t0","t1"}], "vocab", "rules", "beats", "problems",
                                      "notes", "total", "speech_s", "time_source"}（cfg＝efconfig.Cfg；project.json 无 storyboard 键 → present False）
  look_at(looks, t) -> 画面类型 | None
  stats(looks, total=None) -> {"kinds", "n_kinds", "longest_run": {"type","t0","t1","s"}|None, "share": {类型: 秒占比}, "violations": [str], "hints": [str]}
输入错（读不了 timeline／cues、cue 序列与 timeline 不符、storyboard 段不合法、中间段没有拍）抛 StoryboardInputError。
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402
import efconfig  # noqa: E402

DEFAULT_RULES = {"require_look": True, "min_kinds": 4, "min_kinds_under_40s": 3, "max_same_run_s": 15}
UNDER_S = 40.0                    # 口播总长短于它时种类数下限用 min_kinds_under_40s
NUM_ONLY = {"图表", "字卡"}        # count 事件所在拍只有这两类时提示「数字没落到东西上」


class StoryboardInputError(Exception):
    pass


def _rules(sb):
    if not isinstance(sb, dict):
        raise StoryboardInputError("project.json 的 storyboard 不是对象")
    vocab = sb.get("vocab")
    if not (isinstance(vocab, list) and vocab and all(isinstance(v, str) and v.strip() for v in vocab)):
        raise StoryboardInputError(f"project.json 的 storyboard.vocab 须为非空字符串列表：{vocab!r}")
    r = dict(DEFAULT_RULES)
    for k in DEFAULT_RULES:
        if k in sb:
            v = sb[k]
            ok = isinstance(v, bool) if k == "require_look" else (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)
            if not ok:
                raise StoryboardInputError(f"project.json 的 storyboard.{k} 不合法：{v!r}")
            r[k] = v
    return r, list(vocab)


def _cue_times(cfg, cues_path, want):
    """返回 ({cue id: (start, end)}, 来源说明)；cue 序列须与 timeline 逐条同 id。"""
    p = Path(cues_path) if cues_path else cfg.out_root / "audio" / "cues.json"
    if p.is_file():
        try:
            got = json.loads(p.read_text(encoding="utf-8")).get("cues") or []
        except (OSError, ValueError, AttributeError) as e:
            raise StoryboardInputError(f"{p} 读不了：{e}")
        src = f"cues.json（{p}）"
    else:
        import provisional_cues
        res = provisional_cues.estimate(cfg, want)
        if res is None:
            raise StoryboardInputError(f"{p} 不在，且 project.json 的 timing.cps 没设，算不了临时时刻")
        got, src = res["cues"], f"临时估时（{p} 不在；provisional_cues 按音节数排）"
    if [c.get("id") for c in got] != [c["id"] for c in want]:
        raise StoryboardInputError(f"{src} 的 cue 序列与 timeline 不一致（先重跑 make_audio.py 或 provisional_cues.py）")
    try:
        return {c["id"]: (float(c["start"]), float(c["end"])) for c in got}, src
    except (KeyError, TypeError, ValueError) as e:
        raise StoryboardInputError(f"{src} 的 cue 缺 start/end：{e}")


def _items(look):
    """look → [(type, at)]；写法不对返回 None。"""
    if isinstance(look, str):
        return [(look, None)]
    if isinstance(look, list) and look and all(isinstance(x, dict) and isinstance(x.get("type"), str) for x in look):
        return [(x["type"], x.get("at")) for x in look]
    return None


def load_looks(cfg, cues_path=None):
    cfg = cfg if isinstance(cfg, efconfig.Cfg) else efconfig.load(cfg)
    empty = {"present": False, "scaffold": False, "not_required": False, "segments": [], "vocab": [], "rules": {}, "beats": [], "problems": [], "notes": [],
             "total": None, "speech_s": None, "time_source": None}
    if "storyboard" not in cfg.data:
        return empty
    rules, vocab = _rules(cfg.data["storyboard"])
    if cuelib.PROJ != cfg.project_dir:
        cuelib.init(cfg.project_dir)
    try:
        tl = cuelib.load_timeline()
        scenes = tl["scenes"]
        want = cuelib.load_cues(tl)
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise StoryboardInputError(f"timeline.json 读不了或子 cue 与 say 对不上：{e}")
    if not want:
        raise StoryboardInputError("timeline 里没有节拍（没有一条 cue）")
    times, src = _cue_times(cfg, cues_path, want)
    from make_timing import char_times
    scaffold = all(sc.get("kind") == "title" for sc in scenes)
    written = any("look" in sc for sc in scenes if not sc.get("beats")) or any("look" in b for sc in scenes for b in sc.get("beats") or [])
    starts, beats, problems, notes = [], [], [], []   # problems：(类别 missing|vocab|format, 说明)

    def add(t, typ, owner):
        if typ not in vocab:
            problems.append(("vocab", f"{owner} 的画面类型「{typ}」不在词表（{'、'.join(vocab)}）"))
        starts.append((t, typ, owner))

    for i, sc in enumerate(scenes):
        bs = sc.get("beats") or []
        if not bs:
            if i > 0:
                raise StoryboardInputError(f"中间段 {sc.get('id')} 没有节拍（只有第一段可以是无拍的片头段）")
            its = _items(sc.get("look")) if "look" in sc else []
            if its is None or len(its or []) > 1:
                problems.append(("format", f"{sc.get('id')}（无拍的片头段）的场景级 look 须为一个类型字符串：{sc.get('look')!r}"))
            elif its:
                add(0.0, its[0][0], sc.get("id"))
            elif rules["require_look"]:
                problems.append(("missing", f"{sc.get('id')}（无拍的片头段）缺场景级 look"))
            continue
        if "look" in sc:
            notes.append(f"{sc.get('id')} 有拍，场景级 look 不用（按拍级 look 切）")
        for b in bs:
            key = cuelib.beat_key(sc["id"], b)
            ids = [c["id"] for c in b["cues"]]
            b0, b1 = times[ids[0]][0], times[ids[-1]][1]
            cs = []
            for c in b["cues"]:
                cs += char_times(c["text"], *times[c["id"]])[0]
            row = {"beat": key, "t0": round(b0, 3), "t1": round(b1, 3), "types": [], "count": any(e.get("do") == "count" for e in b.get("events") or [])}
            beats.append(row)
            if "look" not in b:
                rules["require_look"] and problems.append(("missing", f"{key} 缺 look"))
                continue
            its = _items(b["look"])
            if its is None:
                problems.append(("format", f"{key} 的 look 写法不对（字符串，或 [{{\"type\":…}}, {{\"type\":…, \"at\":…}}]）：{b['look']!r}"))
                continue
            last = b0
            for j, (typ, at) in enumerate(its):
                if j == 0:
                    t = b0
                else:
                    n = b["say"].count(at) if isinstance(at, str) and at else 0
                    if n != 1:
                        problems.append(("format", f"{key} look 第 {j + 1} 项的 at「{at}」在 say 里出现 {n} 次（须恰好 1 次）"))
                        continue
                    t = cs[b["say"].index(at)]
                    if t <= last + 1e-6:
                        problems.append(("format", f"{key} look 第 {j + 1} 项「{at}」的开口时刻 {t:.2f}s 不晚于前一项起点 {last:.2f}s"))
                        continue
                add(t, typ, key)
                row["types"].append(typ)
                last = t
    first, end = times[want[0]["id"]][0], times[want[-1]["id"]][1]
    total = end + cuelib.TAIL_SILENCE
    segs = []
    for k, (t, typ, owner) in enumerate(starts):
        t0 = 0.0 if k == 0 else t
        t1 = starts[k + 1][0] if k + 1 < len(starts) else total
        segs.append({"beat": owner, "type": typ, "t0": round(t0, 3), "t1": round(t1, 3)})
    return {"present": True, "scaffold": scaffold, "not_required": not rules["require_look"] and not written, "segments": segs, "vocab": vocab,
            "rules": rules, "beats": beats, "problems": problems,
            "notes": notes, "total": round(total, 3), "speech_s": round(end - first, 3), "time_source": src}


def look_at(looks, t):
    segs = (looks or {}).get("segments") or []
    for s in segs:
        if s["t0"] <= t < s["t1"]:
            return s["type"]
    if segs and segs[-1]["t1"] <= t <= segs[-1]["t1"] + 0.1:   # 片尾那一帧（视频比时间轴长出不到 0.1 s）
        return segs[-1]["type"]
    return None


def runs(segs):
    out = []
    for s in segs:
        if out and out[-1]["type"] == s["type"]:
            out[-1]["t1"] = s["t1"]
        else:
            out.append({"type": s["type"], "t0": s["t0"], "t1": s["t1"]})
    for r in out:
        r["s"] = round(r["t1"] - r["t0"], 3)
    return out


def stats(looks, total=None):
    res = {"kinds": [], "n_kinds": 0, "longest_run": None, "share": {}, "violations": [], "hints": []}
    if not looks or not looks.get("present"):
        return res
    total = float(total if total is not None else looks["total"])
    segs = [dict(s) for s in looks["segments"]]
    if segs:
        segs[-1]["t1"] = total
    rs = runs(segs)
    kinds = []
    for s in segs:
        s["type"] in kinds or kinds.append(s["type"])
        res["share"][s["type"]] = res["share"].get(s["type"], 0.0) + (s["t1"] - s["t0"])
    res["share"] = {k: round(v / total, 3) if total > 0 else 0.0 for k, v in res["share"].items()}
    res.update(kinds=kinds, n_kinds=len(kinds), longest_run=max(rs, key=lambda r: r["s"]) if rs else None)
    rules, scaffold = looks["rules"], looks["scaffold"]
    if looks.get("not_required"):   # require_look=false 且一个 look 都没有：未要求，不判任何违规
        return res
    res["violations"] = [msg for cat, msg in looks["problems"] if not scaffold or cat != "missing"]
    if not scaffold:
        for r in rs:
            if r["s"] > rules["max_same_run_s"] + 1e-6:
                res["violations"].append(f"「{r['type']}」从 {r['t0']:.1f}s 连续到 {r['t1']:.1f}s，共 {r['s']:.1f}s，超过 {rules['max_same_run_s']}s")
        short = looks["speech_s"] < UNDER_S
        need = rules["min_kinds_under_40s"] if short else rules["min_kinds"]
        if len(kinds) < need:
            res["violations"].append(f"画面类型只有 {len(kinds)} 种（{'、'.join(kinds) or '无'}），口播 {looks['speech_s']:.1f}s"
                                     f"{'＜' if short else '≥'}{UNDER_S:.0f}s 要求至少 {need} 种")
        for b in looks["beats"]:
            ty = {s["type"] for s in segs if s["t0"] < b["t1"] and s["t1"] > b["t0"]}
            if b["count"] and ty and ty <= NUM_ONLY:
                res["hints"].append(f"{b['beat']} 有 count 事件，画面只有{'／'.join(sorted(ty))}：数字没落到东西上，确认是否有东西可落（实物、角色、三维）")
    return res
