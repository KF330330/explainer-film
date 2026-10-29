#!/usr/bin/env python3
"""声音认可的全局记录 ~/.config/explainer-film/approved_voice.json（目录 700、文件 600）：同一音色认可一次，以后各项目不再问。
键＝<engine>:<voice_fp>（engine 只有 elevenlabs）；指纹与 make_audio.py 同一算法（voice_id_file 内容去空白 sha256[:12]）。
  check  [--engine E]   全局有当前音色 → 复制成项目 <产物>/audio/approved_voice.json（多 copied_from_global、project 两键），退出 0；没有 → 退出 3。
  sample [--engine E]   取 timeline 前 ≤8 句（按 cps 估总长 ≤40 s），用该引擎显式合成 <产物>/review/试听-<engine>-<指纹>.mp3 并 open，退出 0。
  record [--engine E] --quote "<用户原话>" [--sample 文件]   写全局与项目两份记录，试听文件复制到 samples/；没有 --quote 拒写。
--engine 缺省 project.json voice.engine；环境变量 EF_VOICE_REGISTRY 可把全局记录换到别处（测试用）。退出码：0 成功；3 未认可；2 用法或合成错误。
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402
import make_audio  # noqa: E402
from voice_diff import syllables  # noqa: E402

REG = Path(os.environ.get("EF_VOICE_REGISTRY") or "~/.config/explainer-film/approved_voice.json").expanduser()


def die(code, msg):
    print("approve_voice: " + msg, file=sys.stderr)
    sys.exit(code)


def load_reg():
    return json.loads(REG.read_text(encoding="utf-8")) if REG.exists() else {"schema": 1, "default": None, "voices": {}}


def private_dir(d):
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def to_project(rec, out):
    p = out / "audio" / "approved_voice.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    proj = dict(rec, copied_from_global=str(REG), project=str(cuelib.PROJ))
    p.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def cmd_check(a, cfg, eng, fp, out):
    rec = load_reg()["voices"].get(f"{eng}:{fp}") if fp else None
    if not rec or not Path(rec.get("sample") or "").is_file():
        print(f"未认可：全局记录 {REG} 里没有 {eng}:{fp}{'（取不到当前音色指纹）' if not fp else ''}"
              f"{'（记录在但试听文件丢了）' if rec else ''}——先 sample 试听，用户点头后 record --quote")
        return 3
    print(f"已认可 {eng}:{fp}（{rec.get('approved_by')}）→ {to_project(rec, out)}")
    return 0


def cmd_sample(a, cfg, eng, fp, out):
    cps, beats = float(cfg.get("timing.cps") or 3.82), {}
    for c in cuelib.load_cues():
        beats.setdefault(c["beat"], []).append(c)
    pick, est = [], 0.0
    for cs in beats.values():   # 按整句取（整拍合成的节拍不拆开）
        d = sum(len(syllables(c["tts"])) / cps + cuelib.gap_ms(c["tts"]) / 1000 for c in cs)
        if len({c["beat"] for c in pick}) >= 8 or (pick and est + d > 40):
            break
        pick, est = pick + cs, est + d
    if not pick:
        die(2, "timeline 里没有节拍")
    dst, work = out / "review" / f"试听-{eng}-{fp}.mp3", out / "review" / f".sample-{os.getpid()}"
    work.mkdir(parents=True)
    try:
        make_audio.run_tts_cued(make_audio.el_spec("sample", make_audio.el_units(pick)), work, work)
        shutil.move(str(work / "sample.mp3"), str(dst))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"试听 {dst}：{len({c['beat'] for c in pick})} 句，约 {est:.0f} 秒（{eng}，音色指纹 {fp}）")
    subprocess.run(["open", str(dst)])
    return 0


def cmd_record(a, cfg, eng, fp, out):
    if not (a.quote or "").strip():
        die(2, "record 要 --quote「用户原话」；没有原话不写认可记录")
    src = Path(a.sample).expanduser() if a.sample else out / "review" / f"试听-{eng}-{fp}.mp3"
    if not src.is_file():
        die(2, f"试听文件不存在：{src}")
    smp = private_dir(private_dir(REG.parent) / "samples") / f"{eng}-{fp}{src.suffix}"
    shutil.copy2(src, smp)
    os.chmod(smp, 0o600)
    key, reg, V = f"{eng}:{fp}", load_reg(), cfg.get(f"voice.{eng}") or {}
    rec = {"engine": eng, "model": V.get("model"), "voice_fp": fp, "voice_id_file": V.get("voice_id_file"), "style": cfg.get("voice.style"),
           "sample": str(smp), "approved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "approved_by": f"用户原话：「{a.quote.strip()}」", "first_project": reg["voices"].get(key, {}).get("first_project") or str(cuelib.PROJ)}
    reg["voices"][key], reg["default"] = rec, reg.get("default") or key
    tmp = REG.with_name(f".{REG.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, REG)
    print(f"已记录 {key} → {REG}；项目 {to_project(rec, out)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="explainer-film 声音认可：check / sample / record")
    ap.add_argument("cmd", choices=["check", "sample", "record"])
    ap.add_argument("--project")
    ap.add_argument("--engine", choices=["elevenlabs"])
    ap.add_argument("--quote", help="record：用户认可时的原话")
    ap.add_argument("--sample", help="record：试听文件（缺省 <产物>/review/试听-<engine>-<指纹>.mp3）")
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    eng = a.engine or cfg.get("voice.engine") or "elevenlabs"
    fp = make_audio.voice_fp(eng)
    if a.cmd != "check" and not fp:
        die(2, f"取不到当前 {eng} 音色指纹（voice-id 文件不存在）")
    return {"check": cmd_check, "sample": cmd_sample, "record": cmd_record}[a.cmd](a, cfg, eng, fp, Path(a.out) if a.out else cfg.out_root)


if __name__ == "__main__":
    sys.exit(main())
