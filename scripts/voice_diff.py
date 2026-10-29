#!/usr/bin/env python3
"""配音读音核对。

子命令：
  check   外部转写工具（环境变量 EF_TRANSCRIBE_CMD）前台转写每节拍 mp3 → out/voice_check/<engine>/<节拍>.txt，与 tts 读法稿比对，
          写 out/voice_check/<engine>/diff.json；不一致 > max_mismatch 或有节拍无音频 → 退出码 3。
  sample  生成「某段前 1 分钟」样段 wav（段＝project.json voice_diff.sample_scene，null＝首个时长 ≥ sample_secs 的段）：
          本引擎已有全片音频就直接拼，否则只合成这些节拍再拼，并顺带转写比对。
  decide  记录最终引擎与原因到 out/voice_check/decision.json。
  report  汇总 decision.json 与各引擎 diff.json，写 out/voice_check/diff.md。

比对规则（转写与读法稿两边同一套）：NFKC（全角转半角）→ 英文转小写 → 去掉数字间的千分位逗号 →
阿拉伯数字（含小数、百分号）按 NUM_TABLE 转汉字读法 → 「两」并作「二」、「百分之一百」并作「百分之百」→
只留汉字与英文字母（去标点与空白）→ pypinyin.lazy_pinyin(style=NORMAL) 转成去声调音节序列 →
在音节序列上算 difflib.SequenceMatcher(autojunk=False).ratio()。
按拼音比对的原因：离线转写同音字选字不稳（它/他、批/劈），配音本身读音无误。
相似度 < min_similarity（timeline voice 段，默认 0.85）或转写为空＝不一致。
转写工具：check、sample 要用。环境变量 EF_TRANSCRIBE_CMD 给转写命令（可带前置参数，按 shell 规则拆分），调用约定
  <命令> --foreground --output-dir <目录> -- <音频文件…>，每个音频在 <目录> 里写同名 .txt；没设就退出 2，请人工逐句听。
"""
import argparse
import datetime
import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

PROJ = None   # main() 里由 efconfig 定
TRANSCRIBE_ENV = "EF_TRANSCRIBE_CMD"   # 转写命令（见模块说明）；check、sample 要用，没设就退出 2
ENGINE_ZH = {"elevenlabs": "ElevenLabs"}
SAMPLE_SCENE = None   # project.json voice_diff.sample_scene；None＝首个时长 ≥ SAMPLE_SECS 的段
SAMPLE_SECS = 60.0

# ---------------- 归一规则（同一张表用于两边） ----------------
DIGITS = "零一二三四五六七八九"


def _section(n):
    """0 < n < 10000 的读法（不含开头「一十」→「十」的处理）。"""
    out, zero = "", False
    for val, unit in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        d = n // val % 10
        if d == 0:
            if out:
                zero = True
            continue
        if zero:
            out += "零"
            zero = False
        out += DIGITS[d] + unit
    return out


def int_reading(n):
    if n == 0:
        return "零"
    parts = []
    yi, rest = divmod(n, 100000000)
    wan, low = divmod(rest, 10000)
    if yi:
        parts.append(int_reading(yi) + "亿")
    if wan:
        if yi and wan < 1000:
            parts.append("零")
        parts.append(_section(wan) + "万")
    if low:
        if (yi or wan) and low < 1000:
            parts.append("零")
        parts.append(_section(low))
    s = "".join(parts)
    if s.startswith("一十"):
        s = s[1:]
    return s


def num_reading(m):
    """NUM_TABLE：整数按位读，小数点读「点」后逐位读，百分号读作前置「百分之」。"""
    intpart, frac, pct = m.group(1), m.group(2), m.group(3)
    s = int_reading(int(intpart))
    if frac:
        s += "点" + "".join(DIGITS[int(c)] for c in frac[1:])
    return ("百分之" + s) if pct else s


NUM_RE = re.compile(r"(\d+)(\.\d+)?(%?)")


def norm(text):
    s = unicodedata.normalize("NFKC", text or "").lower()
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    s = NUM_RE.sub(num_reading, s)
    s = s.replace("两", "二").replace("百分之一百", "百分之百")
    return re.sub(r"[^一-鿿a-z]", "", s)


def syllables(text):
    """归一后转去声调拼音音节序列；英文串原样作为一个音节。"""
    from pypinyin import Style, lazy_pinyin
    return lazy_pinyin(norm(text), style=Style.NORMAL)


def similarity(a, b):
    return difflib.SequenceMatcher(None, syllables(a), syllables(b), autojunk=False).ratio()


# ---------------- 公共 ----------------
def load_timeline(path):
    tl = json.loads(Path(path).read_text(encoding="utf-8"))
    beats = [{"key": f"{sc['id']}_{b['k']:02d}", "scene": sc["id"], "tts": b["tts"], "say": b["say"]}
             for sc in tl["scenes"] for b in sc["beats"]]
    return tl, beats


def audio_files(audio_dir):
    mpath = Path(audio_dir) / "manifest.json"
    if not mpath.exists():
        return None, {}
    m = json.loads(mpath.read_text(encoding="utf-8"))
    files = {k: Path(audio_dir) / v["file"] for k, v in m.get("beats", {}).items()
             if (Path(audio_dir) / v["file"]).exists()}
    return m.get("engine"), files


def transcribe(files, tx_dir):
    """files: {key: mp3}；EF_TRANSCRIBE_CMD 一次前台转写全部，结果改名为 <key>.txt。返回 {key: 文本}。"""
    tx_dir.mkdir(parents=True, exist_ok=True)
    raw = tx_dir / ".raw"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir()
    if files:
        cmd = shlex.split(os.environ[TRANSCRIBE_ENV]) + ["--foreground", "--output-dir", str(raw), "--"] + [str(p) for p in files.values()]
        r = subprocess.run(cmd, capture_output=True, text=True)
        (tx_dir / "transcribe.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    out = {}
    for key, mp3 in files.items():
        p = raw / (mp3.stem + ".txt")
        txt = p.read_text(encoding="utf-8").strip() if p.exists() else ""
        (tx_dir / f"{key}.txt").write_text(txt + "\n", encoding="utf-8")
        out[key] = txt
    shutil.rmtree(raw, ignore_errors=True)
    return out


def concat_wav(mp3s, wav):
    wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for p in mp3s:
        cmd += ["-i", str(p)]
    n = len(mp3s)
    flt = "".join(f"[{i}:a]aresample=24000,aformat=channel_layouts=mono[a{i}];" for i in range(n))
    flt += "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    cmd += ["-filter_complex", flt, "-map", "[out]", "-c:a", "pcm_s16le", str(wav)]
    subprocess.run(cmd, check=True)


def vc_dir(out):
    return Path(out) / "out" / "voice_check"


# ---------------- 子命令 ----------------
def cmd_check(a):
    tl, beats = load_timeline(a.timeline)
    v = tl.get("voice", {})
    min_sim, max_mis = float(v.get("min_similarity", 0.85)), int(v.get("max_mismatch", 3))
    audio_dir = Path(a.audio_dir or Path(a.out) / "audio")
    tx_dir = Path(a.tx_dir or vc_dir(a.out) / a.engine)
    eng, files = audio_files(audio_dir)
    if eng is not None and eng != a.engine:
        print(f"音频目录引擎是 {eng}，不是 {a.engine}")
        return 1
    if a.beats:
        want = set(k.strip() for k in a.beats.split(","))
        beats = [b for b in beats if b["key"] in want]
    have = {b["key"]: files[b["key"]] for b in beats if b["key"] in files}
    txs = transcribe(have, tx_dir)
    rows, mis = [], 0
    for b in beats:
        tx = txs.get(b["key"], "")
        no_audio = b["key"] not in have
        sim = similarity(b["tts"], tx) if tx else 0.0
        ok = (not no_audio) and bool(tx) and sim >= min_sim
        mis += 0 if ok else 1
        rows.append({"key": b["key"], "tts": b["tts"], "tx": tx, "sim": round(sim, 4), "ok": ok,
                     "no_audio": no_audio, "norm_tts": norm(b["tts"]), "norm_tx": norm(tx),
                     "py_tts": " ".join(syllables(b["tts"])), "py_tx": " ".join(syllables(tx))})
    res = {"engine": a.engine, "label": a.label, "generated": now(), "min_similarity": min_sim,
           "max_mismatch": max_mis, "total": len(rows), "mismatch": mis,
           "no_audio": [r["key"] for r in rows if r["no_audio"]], "rows": rows}
    (tx_dir / "diff.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        if not r["ok"]:
            print(f"  不一致 {r['key']} sim={r['sim']:.3f}\n    读法：{r['tts']}\n    转写：{r['tx']}")
    print(f"MISMATCH={mis} TOTAL={len(rows)} NO_AUDIO={len(res['no_audio'])} ENGINE={a.engine} LABEL={a.label}")
    return 0 if (mis <= max_mis and not res["no_audio"]) else 3


def synth_beats(a, keys, sdir):
    """合成这些节拍、每拍一个文件，写 {"engine", "beats": {节拍: {"file"}}} 清单给 audio_files／cmd_check 读；返回 (退出码, 日志)。
    只支持 elevenlabs：每拍一次 tts_cued（make_audio 的 el_units/el_spec，整拍合成的节拍并成一条，同文本命中缓存）。"""
    import cuelib
    import make_audio
    if a.engine != "elevenlabs":
        return 2, f"样段按需合成只支持 elevenlabs，不支持 {a.engine}\n"
    cuelib.init(str(PROJ))
    by, log, files = {}, [], {}
    for c in cuelib.load_cues(cuelib.load_timeline(a.timeline)):
        by.setdefault(c["beat"], []).append(c)
    shutil.rmtree(sdir, ignore_errors=True)
    sdir.mkdir(parents=True)
    try:
        for k in keys:
            make_audio.run_tts_cued(make_audio.el_spec(k, make_audio.el_units(by[k])), sdir, sdir)
            log.append((sdir / "tts_cued.log").read_text(encoding="utf-8"))
            files[k] = f"{k}.mp3"
    except SystemExit as e:   # run_tts_cued 失败时 die(2)
        lp = sdir / "tts_cued.log"
        return (e.code if isinstance(e.code, int) and e.code else 2), "".join(log) + (lp.read_text(encoding="utf-8") if lp.exists() else str(e.code))
    (sdir / "manifest.json").write_text(json.dumps({"engine": a.engine, "beats": {k: {"file": f} for k, f in files.items()}}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0, "".join(log)


def cmd_sample(a):
    tl, beats = load_timeline(a.timeline)
    vc = vc_dir(a.out)
    vc.mkdir(parents=True, exist_ok=True)
    sb = vc / "sample_beats.json"
    main_audio = Path(a.out) / "audio"
    main_eng, main_files = audio_files(main_audio)
    if sb.exists():
        keys = json.loads(sb.read_text(encoding="utf-8"))["beats"]
    else:
        dpath = main_audio / "durations.json"
        durs = json.loads(dpath.read_text(encoding="utf-8")) if dpath.exists() else {}
        keys, acc = [], 0.0
        scene = SAMPLE_SCENE or next((sc for sc in dict.fromkeys(b["scene"] for b in beats)
                                      if sum(durs.get(b["key"], 4.0) for b in beats if b["scene"] == sc) >= SAMPLE_SECS), beats[0]["scene"])
        for b in beats:
            if b["scene"] != scene:
                continue
            keys.append(b["key"])
            acc += durs.get(b["key"], 4.0)
            if acc >= SAMPLE_SECS:
                break
        sb.write_text(json.dumps({"scene": scene, "beats": keys, "basis": main_eng}, ensure_ascii=False,
                                 indent=1), encoding="utf-8")
    wav = vc / f"样段-{a.engine}-{keys[0].split('_')[0] if keys else ''}前{SAMPLE_SECS:.0f}秒.wav"
    status = {"engine": a.engine, "beats": keys, "wav": None, "error": None}
    if a.unavailable:
        status["error"] = a.unavailable
        (vc / f"sample-{a.engine}.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"SAMPLE_SKIP {a.engine}: {a.unavailable}")
        return 3
    if main_eng == a.engine and all(k in main_files for k in keys):
        src = [main_files[k] for k in keys]
        status["source"] = "全片音频"
    else:
        sdir = vc / a.engine / "audio"
        rc, log = synth_beats(a, keys, sdir)
        (vc / a.engine).mkdir(parents=True, exist_ok=True)
        (vc / a.engine / "sample_tts.log").write_text(log, encoding="utf-8")
        eng, files = audio_files(sdir)
        if rc != 0 or not all(k in files for k in keys):
            status["error"] = f"样段合成失败（退出码 {rc}，日志 {a.engine}/sample_tts.log）"
            (vc / f"sample-{a.engine}.json").write_text(json.dumps(status, ensure_ascii=False, indent=1),
                                                        encoding="utf-8")
            print(f"SAMPLE_FAIL {a.engine}: {status['error']}")
            return 3
        src = [files[k] for k in keys]
        status["source"] = "单独合成"
        # 顺带转写比对样段节拍（结果标为「样段」，不计入判定）
        sub = argparse.Namespace(timeline=a.timeline, out=a.out, engine=a.engine, audio_dir=str(sdir),
                                 tx_dir=str(vc / a.engine / "sample"), beats=",".join(keys), label="样段")
        cmd_check(sub)
    concat_wav(src, wav)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                       capture_output=True, text=True)
    status["wav"] = wav.name
    status["secs"] = round(float(r.stdout.strip() or 0), 2)
    (vc / f"sample-{a.engine}.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"SAMPLE_OK {a.engine} {wav} {status['secs']}s")
    return 0


def cmd_decide(a):
    vc = vc_dir(a.out)
    vc.mkdir(parents=True, exist_ok=True)
    d = {"final_engine": a.final, "reason": a.reason, "generated": now()}
    (vc / "decision.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"DECISION final={a.final} reason={a.reason}")
    return 0


def md_cell(s):
    return (s or "（空）").replace("|", "｜").replace("\n", " ")


def cmd_report(a):
    vc = vc_dir(a.out)
    lines = ["# 配音读音核对（转写 vs 读法稿）", "", f"生成时刻：{now()}", "",
             "判定规则：转写与读法稿两边同一套归一——全角转半角、英文转小写、阿拉伯数字（含小数与百分号）按同一张表转汉字读法、"
             "「两」并作「二」、「百分之一百」并作「百分之百」、去标点与空白；再转成去声调拼音音节序列（pypinyin，style=NORMAL），"
             "在音节序列上算 difflib 相似度，低于阈值或转写为空＝不一致。按拼音比对的原因：离线转写同音字选字不稳（它/他、批/劈），"
             "配音本身读音无误。"
             "不一致超过上限、或任一节拍无音频，就逐句听、读错的句子重合成。规则代码见 skill 的 `scripts/voice_diff.py` 的 `norm()`。", ""]
    dpath = vc / "decision.json"
    if dpath.exists():
        d = json.loads(dpath.read_text(encoding="utf-8"))
        lines += ["## 结论", "", f"- 最终配音引擎：{ENGINE_ZH.get(d['final_engine'], d['final_engine'])}",
                  f"- 原因：{d['reason']}"]
        am = Path(a.out) / "audio" / "manifest.json"
        if am.exists():
            m = json.loads(am.read_text(encoding="utf-8"))
            if m.get("voice"):
                lines.append(f"- 音色：{m.get('voice_name')} `{m['voice']}`，资源 ID {m.get('resource_id') or '脚本默认'}；{m.get('voice_note', '')}")
    results = []
    for p in sorted(vc.glob("*/diff.json")) + sorted(vc.glob("*/sample/diff.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        results.append(r)
        lines.append(f"- {ENGINE_ZH.get(r['engine'], r['engine'])}（{r['label']}）：{r['total']} 句里不一致 "
                     f"{r['mismatch']} 句（阈值 {r['min_similarity']}，上限 {r['max_mismatch']} 句）")
    smoke = vc / "smoke.txt"
    if smoke.exists():
        lines += ["", "## 冒烟记录", "", "```", smoke.read_text(encoding="utf-8").strip(), "```"]
    for r in results:
        lines += ["", f"## {ENGINE_ZH.get(r['engine'], r['engine'])} · {r['label']}逐节拍", "",
                  "| 节拍 | 读法稿 | 转写 | 读法稿拼音 | 转写拼音 | 相似度 | 判定 |", "|---|---|---|---|---|---|---|"]
        for row in r["rows"]:
            verdict = "一致" if row["ok"] else ("无音频" if row["no_audio"] else "**不一致**")
            lines.append(f"| {row['key']} | {md_cell(row['tts'])} | {md_cell(row['tx'])} | {md_cell(row.get('py_tts', ''))} "
                         f"| {md_cell(row.get('py_tx', ''))} | {row['sim']:.3f} | {verdict} |")
    (vc / "diff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT {vc / 'diff.md'}")
    return 0


def now():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def main():
    global PROJ, SAMPLE_SCENE, SAMPLE_SECS
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--timeline")
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--engine", required=True)
    c.add_argument("--audio-dir")
    c.add_argument("--tx-dir")
    c.add_argument("--beats", default="")
    c.add_argument("--label", default="全片")
    s = sub.add_parser("sample")
    s.add_argument("--engine", required=True)
    s.add_argument("--unavailable", default="", help="该引擎不可用的原因；给出则不合成，只记录")
    d = sub.add_parser("decide")
    d.add_argument("--final", required=True)
    d.add_argument("--reason", required=True)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd in ("check", "sample") and not os.environ.get(TRANSCRIBE_ENV, "").strip():
        print(f"voice_diff: 未配置转写工具（环境变量 {TRANSCRIBE_ENV}），请人工逐句听", file=sys.stderr)
        return 2
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import efconfig
    cfg = efconfig.load(a.project)
    PROJ, SAMPLE_SCENE, SAMPLE_SECS = cfg.project_dir, cfg.get("voice_diff.sample_scene"), float(cfg.get("voice_diff.sample_secs") or 60)
    a.timeline, a.out = a.timeline or str(PROJ / "timeline.json"), a.out or str(cfg.out_root)
    return {"check": cmd_check, "sample": cmd_sample, "decide": cmd_decide, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
