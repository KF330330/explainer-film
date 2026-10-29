#!/usr/bin/env python3
"""临时 cue 时间表：声音未经用户认可前，按读音音节数估时长造一份 cues，让画面先能排（不合成任何音频）。

- 片头静音（timing.head_silence）后逐 cue 排：时长 d＝max(timing.min_cue_s, 音节数 ÷ timing.cps)，cue 之后按 cuelib.gap_ms 留气口
  （与真配音同规则：150 ms，句末 450 ms，问号 550 ms；末 cue 后不留），片尾再加 timing.tail_silence；
  音节数＝voice_diff.syllables(读法稿)；cps 由一支样片成片的 manifest 标定（口播总音节 ÷ 总有声秒）；
- 写 <产物>/audio/cues-provisional.json，格式同 audio/cues.json，engine="provisional"、voice_fp=null、provisional=true。
真声音合成后由 make_audio.py 写 audio/cues.json，make_timing.py 默认读它；临时表只给 --cues 显式指定时用。

只有片头的时间轴（一拍都没有、每段都有正数 hold_secs）：写 cues: []、duration＝各段 hold_secs 之和，退出 0（不需要 cps）。
用法：provisional_cues.py [--project P] [--out <产物根>]；有拍但 cps 未设、或无拍且有段缺 hold_secs 退出 2。
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402
from voice_diff import syllables  # noqa: E402


def estimate(cfg, cues):
    """只算不写：按上面的规则给 cues（cuelib.load_cues 的结果）排临时时刻，返回与 cues-provisional.json 同格式的字典；cps 没设返回 None。
    须先 cuelib.init（片头片尾静音、气口读的是 cuelib 的项目常量）；storyboard.py 在没有 cues.json 时也用它。"""
    cps, dmin = cfg.get("timing.cps"), float(cfg.get("timing.min_cue_s", 0.6))
    if not cps:
        return None
    t, out = cuelib.HEAD_SILENCE, []
    for i, c in enumerate(cues):
        d = max(dmin, len(syllables(c["tts"])) / float(cps))
        out.append({"id": c["id"], "beat": c["beat"], "start": round(t, 6), "end": round(t + d, 6), "text": c["text"], "tts": c["tts"]})
        t += d + (cuelib.gap_ms(c["tts"]) / 1000 if i < len(cues) - 1 else 0)
    return {"engine": "provisional", "voice_fp": None, "provisional": True, "source": f"音节数÷cps {cps}（每条至少 {dmin}s）＋气口",
            "duration": round(t + cuelib.TAIL_SILENCE, 6), "cues": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    cps = cfg.get("timing.cps")
    cues = cuelib.load_cues()
    ho = None if cues else cuelib.head_only()
    if ho and not ho[1]:                     # 只有片头：空 cue 表，片长＝各段 hold_secs 之和
        res = {"engine": "provisional", "voice_fp": None, "provisional": True, "source": "只有片头：各段 hold_secs 之和",
               "duration": round(sum(s for _, s in ho[0]), 6), "cues": []}
    elif not cps or not cues:
        why = ("project.json 的 timing.cps 没设" if cues else
               f"timeline 里没有节拍，且段 {'、'.join(ho[1])} 没写正数 hold_secs（只有片头的时间轴每段都要写 hold_secs）" if ho else "timeline 里没有节拍")
        print("provisional_cues：" + why, file=sys.stderr)
        return 2
    else:
        res = estimate(cfg, cues)
    out = res["cues"]
    p = (Path(a.out) if a.out else cfg.out_root) / "audio" / "cues-provisional.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"临时 cue 表 {len(out)} 条，片长 {res['duration']:.2f}s → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
