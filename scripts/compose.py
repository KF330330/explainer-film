#!/usr/bin/env python3
"""合成成片与审片材料。

1. 画面 out/video_only.mp4 ＋ 口播 audio/narration.wav → out/<交付名>.mp4（交付名＝project.json deliverable_name；aac 192k 48 kHz，faststart；画面 copy 不重编码）。
   口播已含 3 s 片头与 1.2 s 片尾静音（make_audio 加的），这里不再加；视频与音频时长差 >0.1 s 退出 1。
   源画面的 sha256 写进成片元数据 explainer_film_video_sha256 与 compose_summary.json 的 video_only_sha256（演示包据此核「成片与当前画面同版」）。
   草稿审片（--video <产物根>/review/draft.mp4）用 --name 另起名（如 --name 草稿-审片），别覆盖交付名文件。
2. 字幕 out/<交付名>.srt（compose.srt 为假时不出）：取 engine/<片名>/timing.js 的 captions（全片秒＝段 t0＋段内秒），文本是 say 原文切块，拼接＝全部 say。
3. 审片材料（--no-review 或 compose.review 为假时跳过；--review-dir 改目录）：
   review/contact.png      接触表（fps=1/3）；
   review/scene-end/<段>.png  每段末帧；
   review/strips/<段>[-k].png 每 0.5 s 一帧、左上角烧时间码与当前字幕的连续帧条（每张最多 48 帧，按段分图）；
   review/fast-<n>.png     全片帧差最大的三处（相隔 ≥3 s），各取前后 12 帧（原帧率）拼条；
   review/scene_text/<段>.txt 该段上板的全部文字（给 check_redlines.py 扫）。
   review/rotation.jpg     画面轮换表（1.3.0）：每 2 s 一帧（共 ⌈片长/2⌉ 格）、每格 480 宽、5 列，左上角烧「时刻  画面类型」
                           （类型按 timeline 的 look，storyboard.look_at；老工程或没写 look 的时刻标 —），审片看「标签与画面是否一致」。
用法：compose.py [--project P] [--out <产物根>] [--video …] [--audio …] [--name <交付名>] [--no-review] [--review-dir …]
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402
import storyboard  # noqa: E402

FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"   # main() 里换成 compose.font_file
BAND_FRAC = 880 / 1080                                  # 字幕带上沿占画高比例：qa.band_top ÷ canvas.height


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit(f"命令失败：{' '.join(map(str, cmd[:6]))} …")
    return r


def probe_dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def captions(T):
    out = []
    for sid, seg in T["seg"].items():
        for c in seg["captions"]:
            out.append({"scene": sid, "start": seg["t0"] + c["start"], "end": seg["t0"] + c["end"], "text": c["text"]})
    return sorted(out, key=lambda c: c["start"])


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(T, path):
    caps = captions(T)
    say_all = "".join(b["say"] for sc in cuelib.load_timeline()["scenes"] for b in (sc.get("beats") or []))
    if "".join(c["text"] for c in caps) != say_all:
        raise SystemExit("字幕拼接 ≠ 全部 say")
    last = -1.0
    lines = []
    for i, c in enumerate(caps, 1):
        if c["start"] < last - 1e-6 or c["end"] <= c["start"]:
            raise SystemExit(f"字幕时间不单调：{c}")
        last = c["end"]
        lines.append(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(caps)


def cap_at(caps, t):
    for c in caps:
        if c["start"] <= t < c["end"]:
            return c["text"].strip()
    return ""


def frames_at(video, times):
    """按时间取帧（顺序读，一次过）。返回 {t: BGR ndarray}。"""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    want = sorted(set(round(t * fps) for t in times))
    out, idx, k = {}, 0, 0
    while k < len(want):
        ok, f = cap.read()
        if not ok:
            break
        if idx == want[k]:
            out[want[k]] = f
            k += 1
        idx += 1
    cap.release()
    return {t: out.get(round(t * fps)) for t in times}, fps


def label(img_bgr, text, w=480):
    im = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).resize((w, round(w * img_bgr.shape[0] / img_bgr.shape[1])))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 17)
    tw = d.textlength(text, font=f)
    d.rectangle([0, 0, tw + 10, 24], fill=(255, 255, 255))
    d.text((5, 3), text, fill=(192, 57, 27), font=f)
    return im


def grid(ims, cols, path):
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w + (cols - 1) * 4, rows * h + (rows - 1) * 4), "white")
    for i, im in enumerate(ims):
        S.paste(im, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
    S.save(path)


def rotation(video, rdir, total, looks):
    """画面轮换表：0、2、4…秒各一帧（片尾那格取 total−0.1 s，OpenCV 顺序读常读不到最后一帧），左上角烧「时刻  画面类型」。"""
    ts = [2.0 * k for k in range(max(1, math.ceil(total / 2 - 1e-9)))]
    rd = {t: round(min(t, max(0.0, total - 0.1)), 3) for t in ts}
    fr, _ = frames_at(video, sorted(set(rd.values())))
    ims = []
    for t in ts:
        f = fr[rd[t]]
        if f is None:   # 取不到帧也占一格，格数恒为 ⌈片长/2⌉
            f = np.full((540, 960, 3), 200, np.uint8)
        ims.append(label(f, f"{rd[t]:5.1f}s  {storyboard.look_at(looks, rd[t]) or '—'}"))
    grid(ims, 5, rdir / "rotation.jpg")
    return len(ims)


def review(video, T, rdir, total, looks=None):
    rdir.mkdir(parents=True, exist_ok=True)
    caps = captions(T)
    n_rot = rotation(video, rdir, total, looks)
    # 接触表
    rows = max(1, math.ceil(math.ceil(total / 3) / 8))   # 每 3 秒一格、每行 8 格，行数按片长算（固定 13 行时 5 分 12 秒以后的画面进不了表）
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", f"fps=1/3,scale=320:-1,tile=8x{rows}:padding=4:color=white", "-frames:v", "1", "-update", "1", str(rdir / "contact.png")])
    # 每段末帧 ＋ 帧条
    (rdir / "scene-end").mkdir(exist_ok=True)
    (rdir / "strips").mkdir(exist_ok=True)
    for old in (rdir / "strips").glob("*.png"):
        old.unlink()
    for sid, seg in T["seg"].items():
        t0, t1 = seg["t0"], min(seg["t0"] + seg["dur"], total)
        ts = [round(t0 + k * 0.5, 3) for k in range(int((t1 - t0) / 0.5) + 1) if t0 + k * 0.5 < t1 - 0.02]
        tend = max(t0, t1 - 0.1)   # 段末前 0.1 s（OpenCV 顺序读常读不到最后一帧）
        fr, fps = frames_at(video, ts + [tend])
        end = fr[tend]
        if end is not None:
            cv2.imwrite(str(rdir / "scene-end" / f"{sid}.png"), end)
        ims = [label(fr[t], f"{t:7.2f}s  {cap_at(caps, t)}") for t in ts if fr[t] is not None]
        for k in range(0, len(ims), 48):
            grid(ims[k:k + 48], 6, rdir / "strips" / (f"{sid}.png" if len(ims) <= 48 else f"{sid}-{k // 48 + 1}.png"))
    # 帧差最大的三处
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    prev, diffs = None, []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (320, round(320 * f.shape[0] / f.shape[1]))), cv2.COLOR_BGR2GRAY).astype(np.int16)
        g = g[: int(g.shape[0] * BAND_FRAC)]
        diffs.append(0.0 if prev is None else float(np.abs(g - prev).mean()))
        prev = g
    cap.release()
    order = np.argsort(diffs)[::-1]
    picks = []
    for i in order:
        if all(abs(i - j) > 3 * fps for j in picks):
            picks.append(int(i))
        if len(picks) == 3:
            break
    for n, i in enumerate(sorted(picks), 1):
        ts = [max(0, (i + d) / fps) for d in range(-12, 13)]
        fr, _ = frames_at(video, ts)
        grid([label(fr[t], f"{t:7.3f}s  帧差 {diffs[min(len(diffs) - 1, round(t * fps))]:.1f}", w=384) for t in ts if fr[t] is not None], 5, rdir / f"fast-{n}.png")
    return {"fastest": [{"t": round(i / fps, 3), "diff": round(diffs[i], 2)} for i in sorted(picks)], "rotation_cells": n_rot}


def scene_text(rdir):
    """起页面读每段上板的字（WB.S 里 text/pop 笔画按章节分），写 scene_text/<段>.txt。"""
    import functools
    import http.server
    import socketserver
    import threading
    from playwright.sync_api import sync_playwright

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x):
            pass

    class S(socketserver.ThreadingTCPServer):
        request_queue_size = 128
        daemon_threads = True

    srv = S(("127.0.0.1", 0), functools.partial(Q, directory=str(cuelib.PROJ / "engine")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html?render=1&film={cuelib.CFG.film}")
        pg.wait_for_function("window.__ready === true || !!window.__bootFailed", timeout=120000)
        data = pg.evaluate("(() => { const m = {}; for (const s of WB.S) { const t = s.kind === 'text' || s.kind === 'pop' ? s.str : (s.textAt ? s.textAt(1e9) : null); const v = t && typeof t === 'object' ? t.text : t; if (v) (m[s.ch] = m[s.ch] || []).push(v); } return m; })()")
        b.close()
    srv.shutdown()
    d = rdir / "scene_text"
    d.mkdir(parents=True, exist_ok=True)
    for sid, arr in data.items():
        (d / f"{sid}.txt").write_text("\n".join(arr) + "\n", encoding="utf-8")
    return sum(len(v) for v in data.values())


def main():
    global FONT, BAND_FRAC
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    ap.add_argument("--video", default="")
    ap.add_argument("--audio", default="")
    ap.add_argument("--name", help="缺省 project.json deliverable_name")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--review-dir", default="")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    FONT, BAND_FRAC = str(cfg.path("compose.font_file", FONT)), cfg.get("qa.band_top", 880) / cfg.get("canvas.height", 1080)
    a.name = a.name or cfg.get("deliverable_name") or f"样片-{cfg.get('title')}-{cfg.get('version')}"
    a.no_review = a.no_review or not cfg.get("compose.review", True)
    out = Path(a.out) if a.out else cfg.out_root
    video = Path(a.video or out / "out" / "video_only.mp4")
    audio = Path(a.audio or out / "audio" / "narration.wav")
    T = cuelib.read_timing()
    mp4 = out / "out" / f"{a.name}.mp4"
    mp4.parent.mkdir(parents=True, exist_ok=True)
    vd, ad = probe_dur(video), probe_dur(audio)
    if abs(vd - ad) > 0.1:
        raise SystemExit(f"画面 {vd:.3f}s 与口播 {ad:.3f}s 差 >0.1s")
    h = hashlib.sha256()
    with video.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    vsha = h.hexdigest()
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart+use_metadata_tags",
         "-metadata", f"explainer_film_video_sha256={vsha}", str(mp4)])   # 不用 -shortest：流复制下它按包截断会丢末帧
    n = write_srt(T, out / "out" / f"{a.name}.srt") if cfg.get("compose.srt", True) else 0
    info = {"mp4": str(mp4), "duration": probe_dur(mp4), "video": vd, "audio": ad, "srt_cues": n, "video_only_sha256": vsha}
    if not a.no_review:
        rdir = Path(a.review_dir or out / "review")
        try:
            looks = storyboard.load_looks(cfg, out / "audio" / "cues.json")
        except storyboard.StoryboardInputError as e:   # 画面类型读不出不挡合成：轮换表全标 —
            print(f"提示：rotation.jpg 的画面类型读不出（{e}），全标 —", file=sys.stderr)
            looks = None
        info.update(review(mp4, T, rdir, vd, looks))
        info["scene_text_items"] = scene_text(rdir)
    (out / "out" / "compose_summary.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"成片 {mp4}：{info['duration']:.3f}s，字幕 {n} 条" + ("" if a.no_review else f"；审片材料 → {a.review_dir or out / 'review'}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
