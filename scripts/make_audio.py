#!/usr/bin/env python3
"""配音 → 一条带片头片尾静音、响度归一的口播音轨 ＋ cue 精确时间表。

先核声音认可：<产物>/audio/approved_voice.json 必须存在，engine 为 elevenlabs，voice_fp 与本机当前音色指纹相同，
试听文件存在；任何一条不符 → 拒绝批量合成（退出 4）。指纹＝sha256(voice.elevenlabs.voice_id_file 去空白)[:12]。
合成（cue 含子 cue，读法稿由 cuelib.py 从节拍 tts 切出；路径、音色风格、响度、采样率都读 project.json）：
  写 spec 调 voice.elevenlabs.tts_cued（null＝本目录的 el_cued.py）<spec> <audio/elevenlabs>，它逐 cue 合成并按气口拼接，
  给出 <slug>.mp3 与 <slug>.cues.json（样本级精确 start/end）；音色 ID 从 voice_id_file 读出后只放进
  子进程环境变量 ELEVENLABS_TTS_VOICE_ID，不写盘、不打印；密钥由 el_cued.py 自己读 ~/.config/elevenlabs/api-key。
  cuelib.WHOLE_BEATS 里的节拍：子 cue 读法稿拼成一整句作为一条送合成（逐 cue 合成会读重复），合成完由 split_whole
  切回子 cue——以停顿标点结尾的边界取附近静音谷的中点，没有标点的边界按读音音节数比例切；切点写进 manifest 的 whole_beats。
产物：audio/narration.wav（48 kHz 单声道 16 bit；前置 3 s、后置 1.2 s 静音在这里加；loudnorm 两遍 I=-16 TP=-1.5 LRA=11 线性增益）、
      audio/cues.json（{"engine","voice_fp","duration","cues":[{"id","beat","start","end","text","tts"}]}，全片绝对秒，含 3 s 片头）、
      audio/manifest.json（引擎、音色指纹、认可记录、每 cue 时长与读法稿、合成请求信息、响度测量值）。

用法：make_audio.py [--project P] --engine elevenlabs [--out <产物根>] [--force B3_15d,…]
退出码：0 成功；4 声音未认可/指纹不符；2 合成缺 cue；1 其他错误。
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402

SR = 48000   # main() 里换成 voice.sample_rate


def die(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        die(1, f"命令失败（{r.returncode}）：{' '.join(map(str, cmd[:6]))} …")
    return r


def voice_fp(engine):
    if engine != "elevenlabs":
        return None
    vf = cuelib.CFG.path("voice.elevenlabs.voice_id_file")
    if not vf.exists():
        return None
    return hashlib.sha256(vf.read_text(encoding="utf-8").strip().encode()).hexdigest()[:12]


def check_approval(out, engine):
    p = out / "audio" / "approved_voice.json"
    if not p.exists():
        die(4, f"拒绝批量合成：{p} 不存在——用户还没听样段认可声音。")
    ap = json.loads(p.read_text(encoding="utf-8"))
    if ap.get("engine") != engine:
        die(4, f"拒绝批量合成：认可的引擎是 {ap.get('engine')}，这次要用 {engine}；换引擎须重新试听认可。")
    fp = voice_fp(engine)
    if not fp or fp != ap.get("voice_fp"):
        die(4, f"拒绝批量合成：当前音色指纹 {fp} 与认可记录 {ap.get('voice_fp')} 不符；换音色须重新试听认可。")
    if not ap.get("sample") or not Path(ap["sample"]).exists():
        die(4, f"拒绝批量合成：认可记录里的试听文件不存在：{ap.get('sample')}")
    return ap, fp


def decode(src, dst):
    """任意音频 → 48 kHz 单声道 s16le 裸 PCM；返回样本数。"""
    run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(src), "-map", "0:a:0", "-vn", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", "-f", "s16le", str(dst)])
    n = dst.stat().st_size
    if n == 0 or n % 2:
        die(1, f"解码结果不对：{src}")
    return n // 2


PAUSE_END = re.compile(r"[、，,；;：:。！？!?…—]+[" + re.escape(cuelib._CLOSE) + r"]*\s*$")


def split_whole(pcm, start, end, subs):
    """整拍合成的一段口播 [start, end]（秒，相对口播开头）切回子 cue。帧长 10 ms；静音帧＝比本段最响帧低 35 dB 以上；
    静音段＝有声段内部连续的静音帧（中间夹 ≤20 ms 的有声帧仍算同一段），长 ≥50 ms。
    读法稿以停顿标点结尾的边界：按时间先后逐个定，只在可行窗（上一切点＋本段每音节 50 ms，有声末尾−其后各段每音节 50 ms）里挑静音谷、取中点——
    先挑离「按音节比例的期望位置」±0.35 s 内最近的谷，没有就挑窗内最长的谷；窗内一个谷也没有才取窗内能量最低帧（优先期望位置 ±0.5 s）。
    切点因此严格递增、每个子 cue 每音节至少 50 ms；有声段短到放不下时按音节比例切。
    没有标点的边界：在前后两个已定切点（或有声段起止）之间按读音音节数比例切。返回 ([(s, e)…], 切点记录)。"""
    import numpy as np
    from voice_diff import syllables
    hop = SR // 100
    a = np.frombuffer(pcm.read_bytes(), dtype="<i2")[round(start * SR): round(end * SR)].astype(np.float64) / 32768
    nf = len(a) // hop
    db = 20 * np.log10(np.sqrt((a[: nf * hop].reshape(nf, hop) ** 2).mean(1)) + 1e-9)
    thr = float(db.max()) - 35
    vo = np.where(db > thr)[0]
    v0, v1 = int(vo[0]), int(vo[-1]) + 1
    syl = [len(syllables(c["tts"])) for c in subs]
    tot, nb = sum(syl), len(subs) - 1
    runs, r0, last = [], None, None
    for i in range(v0, v1):
        if db[i] <= thr:
            r0 = i if r0 is None else r0
            last = i
        elif r0 is not None and i - last > 2:
            runs.append((r0, last + 1)); r0 = None
    if r0 is not None:
        runs.append((r0, last + 1))
    runs = [r for r in runs if r[1] - r[0] >= 5]
    pk = [k for k in range(nb) if PAUSE_END.search(subs[k]["tts"])]
    anchors, rec, prev = {-1: v0, nb: v1}, {}, v0
    for k in pk:   # 按时间先后定每个停顿边界（只按静音最长挑会挑到别处的长停顿上；候选与回退都限在可行窗内）
        exp = v0 + (v1 - v0) * sum(syl[: k + 1]) / tot
        ka = max(x for x in anchors if x < k)
        lo, hi = prev + 5 * max(1, sum(syl[ka + 1: k + 1])), v1 - 5 * sum(syl[k + 1:])
        fit = [r for r in runs if lo <= (r[0] + r[1]) / 2 <= hi]
        near = [r for r in fit if abs((r[0] + r[1]) / 2 - exp) <= 35]
        r = min(near, key=lambda r: abs((r[0] + r[1]) / 2 - exp)) if near else max(fit, key=lambda r: r[1] - r[0], default=None)
        if r is not None:
            anchors[k] = prev = (r[0] + r[1]) / 2
            rec[k] = {"方法": "停顿谷中点（期望位置 ±0.35 s 内就近）" if near else "停顿谷中点（期望窗内无谷，退回最长谷）",
                      "谷": [round(start + r[0] / 100, 3), round(start + r[1] / 100, 3)], "期望": round(start + exp / 100, 3)}
            continue
        cand = list(range(math.ceil(lo - 0.5), math.floor(hi - 0.5) + 1))   # 帧 i 的切点在 i+0.5，须落在 [lo, hi]
        if cand:
            i = min([j for j in cand if abs(j + 0.5 - exp) <= 50] or cand, key=lambda j: db[j])
            anchors[k] = prev = i + 0.5
            rec[k] = {"方法": "窗内没有静音谷，取窗内能量最低帧", "帧": round(start + i / 100, 3), "dB": round(float(db[i]), 1)}
        else:
            anchors[k] = prev = prev + (v1 - prev) * max(1, sum(syl[ka + 1: k + 1])) / max(1, sum(syl[ka + 1:]))
            rec[k] = {"方法": "有声段放不下每音节 50 ms，按音节比例切", "帧": round(start + prev / 100, 3)}
    for k in range(nb):
        if k in anchors:
            continue
        ka, kb = max(x for x in anchors if x < k), min(x for x in anchors if x > k)
        anchors[k] = anchors[ka] + (anchors[kb] - anchors[ka]) * sum(syl[ka + 1: k + 1]) / sum(syl[ka + 1: kb + 1])
        rec[k] = {"方法": "按读音音节数比例", "区间": [round(start + anchors[ka] / 100, 3), round(start + anchors[kb] / 100, 3)],
                  "音节": [sum(syl[ka + 1: k + 1]), sum(syl[k + 1: kb + 1])]}
    cuts = [start + anchors[k] / 100 for k in range(nb)]
    times = [(start if k == 0 else cuts[k - 1], end if k == nb else cuts[k]) for k in range(nb + 1)]
    info = {"段": [round(start, 3), round(end, 3)], "有声": [round(start + v0 / 100, 3), round(start + v1 / 100, 3)], "静音阈值_dBFS": round(thr, 1),
            "静音段": [[round(start + r[0] / 100, 3), round(start + r[1] / 100, 3)] for r in runs], "音节": syl,
            "切点": [dict({"边界": f"{subs[k]['id']}|{subs[k + 1]['id']}", "秒": round(cuts[k], 3)}, **rec[k]) for k in range(nb)]}
    return times, info


def el_units(cues):
    """送合成的条目：整拍合成的节拍并成一条（id 用节拍号），其余一 cue 一条。"""
    units = []
    for c in cues:
        if c["beat"] in cuelib.WHOLE_BEATS and units and units[-1]["id"] == c["beat"]:
            units[-1]["subs"].append(c); units[-1]["text"] += c["tts"]
        else:
            units.append({"id": c["beat"] if c["beat"] in cuelib.WHOLE_BEATS else c["id"], "text": c["tts"], "subs": [c]})
    return units


def el_spec(slug, units, force=()):
    C = cuelib.CFG
    return {"slug": slug, "provider": "elevenlabs", "silence_gap_ms": cuelib.BASE_GAP_MS, "style": C.get("voice.style"), "content_type": C.get("voice.content_type"),
            "sample_rate": 44100, "bitrate": 192000,
            "cues": [dict({"id": u["id"], "text": u["text"]}, **({"force_regenerate": True} if any(c["id"] in force for c in u["subs"]) else {})) for u in units]}


def run_tts_cued(spec, eld, work):
    """调 tts_cued（project.json voice.elevenlabs.tts_cued；null＝本目录的 el_cued.py；音色 ID 只放进子进程环境变量），失败退出 2。"""
    voice = cuelib.CFG.path("voice.elevenlabs.voice_id_file").read_text(encoding="utf-8").strip()
    sp = work / "spec.json"
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    tool = cuelib.CFG.path("voice.elevenlabs.tts_cued") or Path(__file__).resolve().parent / "el_cued.py"
    r = subprocess.run([sys.executable, str(tool), str(sp), str(eld)],
                       env=dict(os.environ, ELEVENLABS_TTS_VOICE_ID=voice), text=True, capture_output=True)
    (work / "tts_cued.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        die(2, f"tts_cued 失败（rc={r.returncode}），日志 {work / 'tts_cued.log'}：{r.stderr.strip()[-600:]}")


def synth_elevenlabs(out, cues, force, work, fp):
    units, slug = el_units(cues), cuelib.CFG.slug
    spec = el_spec(slug, units, force)
    eld = out / "audio" / "elevenlabs"
    print(f"ElevenLabs 合成 {len(cues)} 条 cue（强制重合成 {len(force)} 条）…", flush=True)
    run_tts_cued(spec, eld, work)
    man = json.loads((eld / f"{slug}.cues.json").read_text(encoding="utf-8"))
    got = {c["id"]: c for c in man["cues"]}
    if [c["id"] for c in man["cues"]] != [u["id"] for u in units]:
        die(2, "tts_cued 输出的条目序列与送去合成的不一致")
    pcm = work / "speech.pcm"
    n = decode(eld / f"{slug}.mp3", pcm)
    times, req, whole = [], {}, {}
    for u in units:
        g = got[u["id"]]
        if u["id"] == u["subs"][0]["id"]:
            times.append((g["start"], g["end"])); req[u["id"]] = g.get("generation")
            continue
        seg, info = split_whole(pcm, g["start"], g["end"], u["subs"])
        times += seg
        whole[u["id"]] = dict({"做法": "整拍一次合成，再切回子 cue", "读法稿": u["text"], "why": cuelib.WHOLE_BEATS[u["id"]].get("why"), "request": g.get("generation")}, **info)
        for c in u["subs"]:
            req[c["id"]] = {"whole_beat": u["id"], "request_id": (g.get("generation") or {}).get("request_id")}
    return pcm, n, times, req, {"tts_cued_manifest": str(eld / f"{slug}.cues.json"), "audio_sha256": man.get("audio_sha256"), "anti_clip": man.get("anti_clip"),
                                "whole_beats": whole}


def main():
    global SR
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--engine", required=True, choices=["elevenlabs"])
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    ap.add_argument("--force", default="", help="逗号分隔的 cue id，强制重合成（读错的句子）")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    SR, L = int(cfg.get("voice.sample_rate", 48000)), cfg.get("voice.loudness") or {}
    out = Path(a.out) if a.out else cfg.out_root
    approved, fp = check_approval(out, a.engine)
    cues = cuelib.load_cues()
    force = {k.strip() for k in a.force.split(",") if k.strip()}
    bad = force - {c["id"] for c in cues}
    if bad:
        die(1, f"--force 里有未知 cue：{sorted(bad)}")
    work = out / "audio" / ".work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    pcm, nspeech, times, req, extra = synth_elevenlabs(out, cues, force, work, fp)

    # 片头 3 s ＋ 口播 ＋ 片尾 1.2 s → 两遍 loudnorm（线性增益，不改时长）
    head, tail = round(cuelib.HEAD_SILENCE * SR), round(cuelib.TAIL_SILENCE * SR)
    full = work / "full.pcm"
    with full.open("wb") as f:
        f.write(bytes(2 * head))
        f.write(pcm.read_bytes())
        f.write(bytes(2 * tail))
    ntot = head + nspeech + tail
    raw = ["-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", str(full)]
    TP = float(L.get("TP", -1.5))
    ln = f"loudnorm=I={L.get('I', -16)}:TP={TP}:LRA={L.get('LRA', 11)}"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin"] + raw + ["-af", ln + ":print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])
    ln2 = (f"{ln}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
           f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=summary")
    wav = out / "audio" / "narration.wav"
    run(["ffmpeg", "-y", "-v", "error", "-nostdin"] + raw + ["-af", ln2 + f",aresample={SR}", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    # 真峰保险：两遍 loudnorm 的真峰估计与最终实测会差 0.0x dB；实测 >TP−0.05 dBTP 就整体恒定衰减到 TP−0.1（不改时长、不动 cue 位置）
    def measure(p):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(p), "-af", ln + ":print_format=json", "-f", "null", "-"], capture_output=True, text=True)
        return json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])
    after = measure(wav)
    trim = 0.0
    if float(after["input_tp"]) > TP - 0.05:
        trim = TP - 0.1 - float(after["input_tp"])
        tmp = work / "trim.wav"
        run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(wav), "-af", f"volume={trim:.4f}dB", "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "1", str(tmp)])
        shutil.move(str(tmp), str(wav))
        after = measure(wav)
    with wave.open(str(wav)) as w:
        nout = w.getnframes()
    if abs(nout - ntot) > SR // 100:
        die(1, f"响度归一后时长变了：{nout} ≠ {ntot} 样本")
    dur = nout / SR
    cj = {"engine": a.engine, "voice_fp": fp, "duration": round(dur, 6),
          "cues": [{"id": c["id"], "beat": c["beat"], "start": round(cuelib.HEAD_SILENCE + s, 6), "end": round(cuelib.HEAD_SILENCE + e, 6),
                    "text": c["text"], "tts": c["tts"]} for c, (s, e) in zip(cues, times)]}
    (out / "audio" / "cues.json").write_text(json.dumps(cj, ensure_ascii=False, indent=1), encoding="utf-8")
    man = {"engine": a.engine, "voice_fp": fp, "approved_voice": approved, "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "narration": str(wav), "duration": round(dur, 6), "sample_rate": SR, "head_silence": cuelib.HEAD_SILENCE, "tail_silence": cuelib.TAIL_SILENCE,
           "gap_rule_ms": {"base": cuelib.BASE_GAP_MS, "sentence": cuelib.SENT_GAP_MS, "question": cuelib.Q_GAP_MS},
           "loudnorm_measured": m, "loudness_after": {"lufs": float(after["input_i"]), "true_peak": float(after["input_tp"]), "trim_db": round(trim, 4)},
           "forced": sorted(force), "tts_overrides": cuelib.OVERRIDES, **extra,
           "cues": {c["id"]: {"beat": c["beat"], "tts": c["tts"], "secs": round(e - s, 6), "request": req.get(c["id"])} for c, (s, e) in zip(cues, times)}}
    (out / "audio" / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print(f"口播音轨 {wav}：{dur:.3f}s（{a.engine}，音色指纹 {fp}），cue {len(cues)} 条；响度归一前 I={m['input_i']} TP={m['input_tp']}，"
          f"归一后 I={after['input_i']} TP={after['input_tp']}（真峰保险衰减 {trim:.2f} dB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
