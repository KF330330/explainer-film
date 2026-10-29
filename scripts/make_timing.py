#!/usr/bin/env python3
"""cues.json ＋ timeline.json → engine/<片名>/timing.js 与 engine/eras_<片名>.js（片名、帧率、片头片尾读 project.json）。

TIMING 契约：
  total；seg[场景] = {text, dur, t0, voStart, voEnd, charStart[], charEnd[], match, lines[], captions[{start,end,text}]}
    （seg 内时间为段内局部秒；t0 为全片秒；B0 t0=0、dur＝B1 首 cue start；中间段 dur＝下一段 t0 − 本段 t0；
      末段 dur＝末 cue end − 本段 t0 ＋ 1.2）；
  beats[节拍] = {start, end, text, charStart[], charEnd[], cues{cueId:{start,end}}}（全片秒）。
  另附 cues{cueId:{beat,start,end}}（TMB.land 查表用）、events{节拍:[timeline 事件原样]}、motion、meta。
每字符时间：在所属 cue 的 [start,end] 内按「算一份的字符」（汉字/字母/数字/%/小数点）线性摊，空白与标点沿前一字。
字幕：每节拍 say 按 cuelib.pack_cues（≤16 字）切块；起点＝块内首字开口，终点＝下一块起点（相隔 ≤1.2 s 时）否则本块末字＋0.5 s。
校验（任一不过退出 1，build 中止）：cue 序列与 timeline 逐条同 id 同文本、时间单调不重叠；每个事件 at 在本节拍 say 里恰好出现一次；
count 事件必须有 land_cue 且属于本节拍。
只有片头的时间轴（timeline 一拍都没有、每段都有正数 hold_secs）接受空 cue 表：每段时长取 hold_secs，beats、cues、captions 为空，照常写 timing.js 与 eras；
其余情况（有拍但 cue 表没有 cue、无拍且有段缺 hold_secs、无拍而 cue 表有 cue）→ 退出 2，提示缺什么。

用法：make_timing.py [--project P] [--cues <产物>/audio/cues.json] [--timeline <项目>/timeline.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402
import efconfig  # noqa: E402

CAP_JOIN = 1.2      # 两块字幕间隔不超过它就接上
CAP_TAIL = 0.5      # 否则本块末字后再留 0.5 s
CAP_MIN = 0.83


def fail(msg):
    print("make_timing 校验失败：" + msg, file=sys.stderr)
    sys.exit(1)


def char_times(text, start, end):
    w = [i for i, ch in enumerate(text) if cuelib.weighted(ch)]
    cs, ce = [0.0] * len(text), [0.0] * len(text)
    n = max(1, len(w))
    d = (end - start) / n
    k, last = 0, start
    for i, ch in enumerate(text):
        if cuelib.weighted(ch):
            cs[i], ce[i] = start + k * d, start + (k + 1) * d
            last = ce[i]
            k += 1
        else:
            cs[i] = ce[i] = last
    return cs, ce


def write_outputs(cfg, timing, ids):
    """写 engine/<片名>/timing.js 与 engine/eras_<片名>.js（有拍与只有片头两条路共用）。"""
    F, eng = cfg.film, cuelib.PROJ / "engine"
    js = cuelib.timing_js()
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text("// 由 tools/make_timing.py 生成，勿手改。seg 内时间为段内局部秒，beats/cues 为全片秒（含 3 s 片头）。\n"
                  "window.TIMING = " + json.dumps(timing, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    eras = eng / f"eras_{F}.js"
    libs = ", ".join("'" + x.replace("\\", "\\\\").replace("'", "\\'") + "'" for x in efconfig.scene_libs(cfg))   # 老工程（无 style 键）与加画法包之前逐字节相同；单引号串先转义 \ 与 '（普通路径逐字节不变）
    eras.write_text(
        f"// {cfg.get('title') or F}（?film={F}）。由 scripts/make_timing.py 生成，勿手改；段长来自 {F}/timing.js（口播实测）。\n"
        f"window.PUNCH = 0;\nwindow.FPS_HINT = {cfg.get('canvas.fps', 30)};\n"
        f"window.SCENE_LIBS = [{libs}];\n"
        f"window.SCENE_DIR = '{F}/scenes';\nwindow.EXTRA_ASSETS = {json.dumps(efconfig.extra_assets(cfg), ensure_ascii=False)};\n"
        f"window.ERAS = {json.dumps(ids)}.map(id => ({{ id, get dur() {{ return TIMING.seg[id].dur; }} }}));\n", encoding="utf-8")


def head_only_timing(cfg, tl, cj, cues_file, holds):
    """只有片头的时间轴：每段时长取 hold_secs（t0 依次累加），beats、cues、events、captions 为空，照常写 timing.js 与 eras。"""
    ids, seg, total = [sid for sid, _ in holds], {}, 0.0
    for sid, h in holds:
        seg[sid] = {"text": "", "dur": round(h, 4), "t0": round(total, 4), "voStart": 0, "voEnd": 0,
                    "charStart": [], "charEnd": [], "match": 1.0, "lines": [], "captions": []}
        total += h
    timing = {"total": round(total, 4), "seg": seg, "beats": {}, "cues": {}, "events": {}, "motion": tl.get("motion", {}),
              "meta": {"engine": cj.get("engine"), "voice_fp": cj.get("voice_fp"), "provisional": bool(cj.get("provisional")), "cues_file": str(cues_file)}}
    write_outputs(cfg, timing, ids)
    print(f"timing.js：{len(ids)} 段、只有片头（无节拍、无 cue、无字幕）、片长 {total:.3f}s（各段 hold_secs 之和）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--cues")
    ap.add_argument("--timeline")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    a.cues = a.cues or str(cfg.out_root / "audio" / "cues.json")
    tl = cuelib.load_timeline(a.timeline)
    cj = json.loads(Path(a.cues).read_text(encoding="utf-8")) if Path(a.cues).is_file() else {}
    want = cuelib.load_cues(tl)
    got = cj.get("cues") or []
    ho = None if want else cuelib.head_only(tl)
    if ho and not ho[1] and not got:         # 只有片头：空 cue 表也行（cue 文件不在同样当空表）
        return head_only_timing(cfg, tl, cj, a.cues, ho[0])
    if not want or not got:
        if want:
            why = f"{a.cues} 里没有 cue（timeline 有 {len(want)} 条）——先跑 provisional_cues.py 或 make_audio.py 生成 cue 表"
        elif ho and not ho[1]:
            why = f"timeline 一拍都没有，但 {a.cues} 里有 {len(got)} 条 cue——cue 表与 timeline 对不上，重跑 provisional_cues.py"
        elif ho:
            why = (f"timeline 里没有节拍，且段 {'、'.join(ho[1])} 没写正数 hold_secs——只有片头的时间轴每段都要写 hold_secs；"
                   "要口播就先写节拍，再跑 provisional_cues.py 或 make_audio.py 生成 cue 表")
        else:
            why = "timeline 里没有节拍——先写好 timeline.json，再跑 provisional_cues.py 或 make_audio.py 生成 cue 表"
        print("make_timing：" + why, file=sys.stderr)
        sys.exit(2)
    if [c["id"] for c in got] != [c["id"] for c in want]:
        fail("cues.json 的 cue 序列与 timeline 不一致")
    prev_end = 0.0
    for g, w in zip(got, want):
        if g["text"] != w["text"]:
            fail(f"{g['id']} 文本不一致：{g['text']!r} ≠ {w['text']!r}")
        if not (g["start"] >= prev_end - 1e-6 and g["end"] > g["start"]):
            fail(f"{g['id']} 时间不单调或重叠：{g['start']}–{g['end']}（上一条止于 {prev_end}）")
        prev_end = g["end"]
    cue_t = {g["id"]: g for g in got}

    # ---------- 节拍 ----------
    beats, events, scene_beats = {}, {}, {}
    for sc in tl["scenes"]:
        scene_beats[sc["id"]] = []
        for b in sc.get("beats") or []:
            key = cuelib.beat_key(sc["id"], b)
            cs_all, ce_all, cues = [], [], {}
            for c in b["cues"]:
                g = cue_t[c["id"]]
                cs, ce = char_times(c["text"], g["start"], g["end"])
                cs_all += cs
                ce_all += ce
                cues[c["id"]] = {"start": round(g["start"], 4), "end": round(g["end"], 4)}
            beats[key] = {"start": round(cue_t[b["cues"][0]["id"]]["start"], 4), "end": round(cue_t[b["cues"][-1]["id"]]["end"], 4),
                          "text": b["say"], "charStart": [round(x, 4) for x in cs_all], "charEnd": [round(x, 4) for x in ce_all], "cues": cues}
            scene_beats[sc["id"]].append(key)
            evs = b.get("events") or []
            for e in evs:
                n = b["say"].count(e["at"])
                if n != 1:
                    fail(f"{key} 事件 {e['el']}·{e['do']} 的锚词「{e['at']}」在 say 里出现 {n} 次（须恰好 1 次）")
                if e["do"] == "count":
                    if e.get("land_cue") not in cues:
                        fail(f"{key} count 事件 {e['el']} 的 land_cue={e.get('land_cue')} 不在本节拍")
                elif e.get("land_cue") and e["land_cue"] not in cues:
                    fail(f"{key} 事件 {e['el']} 的 land_cue 不在本节拍")
            tot = sum(float(e.get("dur", 0)) for e in evs)
            bd = beats[key]["end"] - beats[key]["start"]
            if tot > bd + 1e-6:
                print(f"提示：{key} 事件总时长 {tot:.2f}s > 本句音频 {bd:.2f}s", file=sys.stderr)
            events[key] = evs

    # ---------- 段 ----------
    ids = [sc["id"] for sc in tl["scenes"]]
    t0 = {}
    for i, sid in enumerate(ids):
        if scene_beats[sid]:
            t0[sid] = beats[scene_beats[sid][0]]["start"]
        elif i == 0:
            t0[sid] = 0.0
        else:
            fail(f"中间段 {sid} 没有节拍")
    E = got[-1]["end"]
    seg, total = {}, 0.0
    for i, sid in enumerate(ids):
        S = t0[sid]
        dur = (t0[ids[i + 1]] - S) if i + 1 < len(ids) else (E - S + cuelib.TAIL_SILENCE)
        if dur <= 0:
            fail(f"段 {sid} 时长 ≤0")
        bk = scene_beats[sid]
        text = "".join(beats[k]["text"] for k in bk)
        cs = [round(x - S, 4) for k in bk for x in beats[k]["charStart"]]
        ce = [round(x - S, 4) for k in bk for x in beats[k]["charEnd"]]
        seg[sid] = {"text": text, "dur": round(dur, 4), "t0": round(S, 4),
                    "voStart": round(beats[bk[0]]["start"] - S, 4) if bk else 0, "voEnd": round(beats[bk[-1]]["end"] - S, 4) if bk else 0,
                    "charStart": cs, "charEnd": ce, "match": 1.0, "lines": [beats[k]["text"] for k in bk], "captions": []}
        total = S + dur
    sc0 = next((sc for sc in tl["scenes"] if sc["id"] == ids[0]), {})
    if sc0.get("hold_secs") and abs(seg[ids[0]]["dur"] - float(sc0["hold_secs"])) > 0.02:
        print(f"提示：{ids[0]} 段长 {seg[ids[0]]['dur']} ≠ hold_secs {sc0['hold_secs']}", file=sys.stderr)

    # ---------- 字幕 ----------
    caps = []
    for sid in ids:
        for k in scene_beats[sid]:
            b = beats[k]
            pos = 0
            for chunk in cuelib.pack_cues(b["text"]):
                idx = [pos + j for j, ch in enumerate(chunk) if cuelib.weighted(ch)] or [pos]
                caps.append({"scene": sid, "beat": k, "text": chunk, "start": b["charStart"][idx[0]], "speech_end": b["charEnd"][idx[-1]]})
                pos += len(chunk)
    for i, c in enumerate(caps):
        nxt = caps[i + 1]["start"] if i + 1 < len(caps) else None
        end = nxt if (nxt is not None and nxt - c["speech_end"] <= CAP_JOIN) else c["speech_end"] + CAP_TAIL
        if end - c["start"] < CAP_MIN:
            end = c["start"] + CAP_MIN if nxt is None or c["start"] + CAP_MIN <= nxt else end
        c["end"] = min(end, total)
    short = [c for c in caps if c["end"] - c["start"] < CAP_MIN - 1e-6]
    for c in caps:
        S = seg[c["scene"]]["t0"]
        seg[c["scene"]]["captions"].append({"start": round(c["start"] - S, 4), "end": round(c["end"] - S, 4), "text": c["text"]})

    timing = {"total": round(total, 4), "seg": seg, "beats": beats,
              "cues": {g["id"]: {"beat": next(k for k in beats if g["id"] in beats[k]["cues"]), "start": round(g["start"], 4), "end": round(g["end"], 4)} for g in got},
              "events": events, "motion": tl.get("motion", {}),
              "meta": {"engine": cj.get("engine"), "voice_fp": cj.get("voice_fp"), "provisional": bool(cj.get("provisional")), "cues_file": str(a.cues)}}
    write_outputs(cfg, timing, ids)
    print(f"timing.js：{len(ids)} 段、{len(beats)} 节拍、{len(got)} cue、字幕 {len(caps)} 条（短于 {CAP_MIN}s 的 {len(short)} 条）、"
          f"片长 {total:.3f}s（{'临时·' + str(cj.get('engine')) if cj.get('provisional') else cj.get('engine')}）")
    for c in short:
        print(f"  短字幕 {c['beat']}「{c['text']}」{c['end'] - c['start']:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
