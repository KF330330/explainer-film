#!/usr/bin/env python3
"""成片／草稿的机器检查。输出 <qa-dir>/qa.json（每项 {"name","status":"PASS|FAIL|INFO","detail"}）与 gate.json（film_gate 原始结果）。
口径读 project.json：qa.gates 五把尺子（still_in_speech_s→pen_idle 阈值、mentioned_el_must_move→semantic、number_land→count_land、
camera_settle→cam_pen、sample_change_min→still_flagged 的变化占比；设成 null/false 的项只记录 INFO 不拦）；qa.record_only 里的指标只写不拦；
qa.band_top、qa.pop_elements_re、qa.seed、qa.config（标定文件）；gates 脚本在 vendor.path/gates。
硬门禁（任一 FAIL 退出 1，不交付）：
  film_gate      gates/film_gate.py：中段空画面 0、蓝紫底 <0.12（屏蔽底部 200px 字幕带）；fast_ratio 只记录不拦（硬门禁用
                 pen_idle/semantic/count_land/cam_pen/still_flagged 这几把尺子，快动帧占比量不到白板笔写）；
  jumps          gates/qa.py 报的跳变（它已把平滑推拉横移认作镜头事件）逐条对相机运动、砸入／弹出、数字落定、带 jump 字段的笔画（画法包专用件）时刻
                 标注为有意，标不上的 FAIL；
  style_lint     （只在 project.json 有 style 键时跑）engine/<片名>/scenes/*.js 的字符串里不得出现 #rgb/#rrggbb/#rrggbbaa、rgb(/rgba(/hsl( 颜色字面量
                 与字体名字面量（颜色字体一律经 WB 令牌：WB.INK/OR/…、WB.C.<键>、WB.FONT/BODY/NUMF）；行尾 `// style-lint: ok <理由>` 豁免该行；
  semantic       语义动作：timeline 每个事件取实际区间 [start, start+dur]（start＝页面 eventTimes() 登记的实际起点，dur＝timeline），
                 在 25% 与 75% 两处各出一帧，两帧都用 start 时刻的相机（WB.lockcam，剔除运镜）、遮掉字幕带，数该元素
                 elementBoxes() 框内变了（任一通道差 >12）的像素数 > 阈值；相机事件比较两时刻相机位置；每个节拍至少一个事件 PASS。
                 阈值读 tools/qa_config.json（用本片第一支认可草稿的事件差值分布取下 10 分位标定，calibrated=true）；--threshold 可临时覆盖（此时记未标定）；
                 期望节拍取 timeline.json 里有 events 的节拍（落在 --range 内的），页面 eventTimes() 没登记的节拍直接记 FAIL；
  determinism    随机 N 个 t（种子固定）用 render.py --stills 出两遍，sha256 逐张一致；
  layout         每 0.25 s 采样 visibleItems()（运镜中也采）：画面里的字被画框切成半截、或离上边 <60 px，连续 ≥0.5 s 即问题
                 （按元素归并：同一条笔画——WB.items 的 sid，即它在 WB.S 的下标——的采样连起来计时；同一串字写在两处是两条笔画，分别计）；
                 相机停住时，画面里任何一行字的包围盒都不得与字幕带（y>880）相交；
                 这个镜头里（上次运镜停稳后）最近 6 s 内写完的字：不出左右 110px、字高（em×0.85）≥32px、互不重叠；
  pen_idle       口播期间（首 cue 起 → 末 cue 止）每 0.05 s 查页面 penAt()：连续 ≥1.5 s 画面里没有一笔在动、相机也没在动即 FAIL（字幕变不算；
                 相机在动的帧算画面在变——落镜要停 0.5 s，1 s 远行＋0.5 s 停稳本身就有 1.5 s 不能落笔）；
  still_video    成片实测：12 fps、640 宽灰度、遮字幕带，相邻帧差 >12 的像素数 < K 记静止，口播期间连续 ≥ max_s 即 FAIL（tools/qa_config.json still_video.max_s，缺省 1.5 s）
                 （K 用片尾静持段的编码噪声标定；旧提示项「帧差均值 <0.4」看不见笔画，不再用）；qa_config.json 的 still_video_source 缺省 "video"（量成片）；
                 设 "noambient_draft" 时先 render.sh draft --noambient 出无装饰动作草稿（<qa-dir>/still-noambient-draft.mp4），still_video 与 still_flagged
                 量这条草稿（K 仍按其片尾静持段标定）——画法有线 boil 等装饰性持续动作时用，免得装饰动作把死帧盖住；
  still_flagged  审片人标过的死帧处（tools/qa_config.json 的 still_flagged.spots，按 [节拍, 字] 锚点登记，不按秒数）：处内任一 window_s（1.2 s）窗，
                 逐帧对变化像素累计须 ≥ 整幅（遮字幕带）的 min_pct%（0.4）；qa.json 逐处输出实测最小窗值与位置；
  cam_pen        相机运动期间不起笔：画面里的笔画（引线除外）起笔不得落在运镜或糊影区间 [m0, m1+SETTLE) 里（SETTLE＝WB.SETTLE，0.5 s；
                 糊影区间＝逐 1/30 s 算画框角点位移 ≥24 px 的时段，与渲染时的运动模糊同口径）；标了 camOk 的笔画（慢推中允许起笔）改量起笔 t0 起 0.3 s 内
                 相机够不够慢：逐 1/30 s 差分，缩放变化率 |Δz/z| ≤ 0.05/秒 且画面平移速度（相机中心世界位移×z）≤ 40 px/秒（1920×1080 屏幕像素），超过且在画面里即 FAIL；
                 detail 的 cam_ok 记 camOk 笔画条数与各自实测速度；
  count_land     每个 count 事件页面实际落定时刻 ＝ cues.json 里 land_cue 的 end ＋ land_offset，误差 ≤0.1 s；
  av / loudness  视频与口播时长差 ≤0.1 s；口播 −16±1 LUFS、真峰 ≤−1.5 dBTP（无口播时 INFO 跳过）；
  subtitles      每条 ≥0.83 s、每行 ≤16 字、≤2 行、时间单调、拼接＝全部 say；
  redlines       tools/check_redlines.py 退出 0；
  storyboard     scripts/check_storyboard.py（--cues <产物根>/audio/cues.json）退出 0：每拍有画面类型（timeline look）且在词表里、同一种连续
                 ≤ storyboard.max_same_run_s（15 s）、全片种类 ≥ min_kinds（4；口播 <40 s 用 min_kinds_under_40s 3）、镜头表有「画面类型」列、
                 assets 里的原件在 CREDITS.md 都有行且「许可」列不空；project.json 无 storyboard 键（老工程）、脚手架（只有片头段）、require_look=false 且 timeline 无 look（not required）记 INFO。
提示项（INFO，只给审片者看）：相机停留时长、推近次数/分钟。
用法：qa.py [--project P] --video <mp4> [--out <产物根>] [--qa-dir <目录>] [--beats B1_01,…] [--range a-b,…] [--threshold 0.8] [--det-n 30]
      [--skip gates_qa,determinism,…]（没有单独的草稿开关：查分段拼接的草稿时用 --range 给出各段的全片秒，与草稿的段界一致）
"""
import argparse
import base64
import functools
import hashlib
import http.server
import io
import json
import os
import random
import re
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cuelib  # noqa: E402

PY = sys.executable
BAND = 880            # 字幕带上沿（1080p）；main() 里换成 qa.band_top
G, RO = {}, set()     # qa.gates、qa.record_only


def gated(it, on):
    """qa.gates 关掉的尺子只记录（INFO）不拦。"""
    return it if on else dict(it, status="INFO")


def gates_dir():
    return (cuelib.CFG.path("vendor.path") or cuelib.CFG.skill_dir / "vendor") / "gates"


def item(name, ok, detail, info=False):
    return {"name": name, "status": "INFO" if info else ("PASS" if ok else "FAIL"), "detail": detail}


class Page:
    """起整片页面（1920×1080），给 QA 渲帧、读 eventTimes/elementBoxes/visibleItems/cameraAt。"""
    def __enter__(self):
        from playwright.sync_api import sync_playwright

        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *x):
                pass

        class S(socketserver.ThreadingTCPServer):
            request_queue_size = 128
            daemon_threads = True

        self.srv = S(("127.0.0.1", 0), functools.partial(Q, directory=str(cuelib.PROJ / "engine")))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch()
        self.pg = self.b.new_page(viewport={"width": 1920, "height": 1080})
        self.errors = []
        self.pg.on("pageerror", lambda e: self.errors.append(str(e)))
        self.pg.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.pg.goto(f"http://127.0.0.1:{self.srv.server_address[1]}/index.html?render=1&film={cuelib.CFG.film}")
        self.pg.wait_for_function("window.__ready === true || !!window.__bootFailed", timeout=120000)
        bf = self.pg.evaluate("window.__bootFailed || null")
        if bf:
            raise SystemExit("页面起不来：" + bf)
        return self

    def ev(self, js, arg=None):
        return self.pg.evaluate(js, arg)

    def frame(self, t, lock=None):
        b64 = self.pg.evaluate("async ([t, lock]) => { WB.lockcam = lock; await window.prepare(t); window.renderFrame(t); const d = window.__canvas.toDataURL('image/png').split(',')[1]; WB.lockcam = null; return d; }", [t, lock])
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")).astype(np.int16)

    def __exit__(self, *x):
        self.b.close()
        self.pw.stop()
        self.srv.shutdown()


def in_ranges(t, ranges):
    return not ranges or any(a <= t <= b for a, b in ranges)


def check_film_gate(video, qdir):
    r = subprocess.run([PY, str(gates_dir() / "film_gate.py"), str(video), "--json", "--sub-band", "0.186", "--no-template"], capture_output=True, text=True)
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        return item("film_gate", False, f"film_gate 读不了：{r.stderr[-400:]}"), None
    (qdir / "gate.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    fr, bl, bp = res.get("fast_ratio"), res.get("blank_run_s") or 0, res.get("blue_purple_share") or 0
    ok = fr is not None and bl == 0 and ("blue_purple_share" in RO or bp < 0.12) and ("fast_ratio" in RO or fr >= 0.06)
    pol = "只记录（硬门禁用 pen_idle/semantic/count_land/cam_pen/still_flagged）" if "fast_ratio" in RO else "≥0.06（不在 qa.record_only）"
    return item("film_gate", ok, {"fast_ratio": fr, "fast_ratio_policy": pol, "blank_run_s": bl, "blue_purple_share": bp, "gate_light": res.get("gate_light"),
                                  "longest_still_s": res.get("longest_still_s"), "event_rate": res.get("event_rate"),
                                  "max_event_gap_s": res.get("max_event_gap_s"), "push_in_per_min": res.get("push_in_per_min")}), res


def check_jumps(pg, qdir, ranges):
    gq = qdir / "gates-qa"
    env = dict(os.environ, PYTHONPATH=str(cuelib.PROJ / "engine"), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY, str(gates_dir() / "qa.py"), "--project", str(cuelib.PROJ / "engine"), "--film", cuelib.CFG.film, "--fps", "4", "--out", str(gq)],
                       capture_output=True, text=True, env=env)
    p = gq / "qa.json"
    if not p.exists():
        return item("jumps", False, f"gates/qa.py 没出结果：{(r.stdout + r.stderr)[-500:]}"), None
    rep = json.loads(p.read_text(encoding="utf-8"))
    segs = {s["id"]: s for s in pg.ev("ERAS.map(e => ({id: e.id, t0: e.t0}))")}
    marks = pg.ev("""(re) => { const out = []; for (let i = 0; i < WB.K.length - 1; i++) { const a = WB.K[i], b = WB.K[i + 1];
        if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) > 2 || Math.abs(a.z - b.z) > 1e-3) out.push([a.t, b.t, 'camera']); }
        for (const s of WB.S) { if (s.kind === 'pop') out.push([s.t0, s.t1, 'stamp']); if (s.kind === 'custom' && s.textAt) out.push([s.t0, s.t1, 'count']);
          if (s.kind === 'custom' && s.el && new RegExp(re).test(s.el)) out.push([s.t0, s.t1 + 0.3, 'pop']); if (s.kind === 'fill') out.push([s.t0, s.t1, 'fill']);
          if (s.jump) out.push([s.t0, s.t1, String(s.jump)]); }   // 画法包专用件自报的有意跳变（如砸入 jump: 'stamp'）
        return out; }""", cuelib.CFG.get("qa.pop_elements_re"))
    bad, ok = [], []
    for s in rep.get("segments", []):
        t0 = segs.get(s["id"], {}).get("t0", 0)
        for lt in s.get("spikes_at_lt", []):
            t = t0 + lt
            if not in_ranges(t, ranges):
                continue
            hit = next((m[2] for m in marks if m[0] - 0.3 <= t <= m[1] + 0.3), None)
            (ok if hit else bad).append({"t": round(t, 2), "label": hit})
    det = all(s.get("deterministic", False) for s in rep.get("segments", []))
    ms = [s.get("ms_mean") for s in rep.get("segments", [])]
    return item("jumps", not bad, {"labelled": ok, "unlabelled": bad, "gates_qa_deterministic": det, "ms_mean_by_seg": ms,
                                   "page_errors": rep.get("page_errors", [])}), rep


def check_semantic(pg, beats, threshold, ranges, T, calibrated):
    evs = [e for e in pg.ev("eventTimes()") if (not beats or e["beat"] in beats) and in_ranges(e["start"], ranges)]
    # 期望节拍：timeline 里有 events 的节拍（句首落在查验时段内、且在 --beats 内）——页面没登记动作的节拍不会被漏掉
    tl = cuelib.load_timeline()
    expect = sorted(cuelib.beat_key(sc["id"], b) for sc in tl["scenes"] for b in (sc.get("beats") or []) if b.get("events")
                    and (not beats or cuelib.beat_key(sc["id"], b) in beats) and in_ranges(T["beats"][cuelib.beat_key(sc["id"], b)]["start"], ranges))
    rows, by_beat = [], {k: [] for k in expect}
    for e in evs:
        s, d = e["start"], max(0.2, float(e["dur"]))
        ta, tb = s + 0.25 * d, s + 0.75 * d
        if e["do"] == "camera":
            ca, cb = pg.ev("(t) => window.cameraAt(t)", ta), pg.ev("(t) => window.cameraAt(t)", tb)
            v = abs(ca["x"] - cb["x"]) * ca["z"] + abs(ca["y"] - cb["y"]) * ca["z"] + abs(np.log(cb["z"] / ca["z"])) * 1000
            ok = v > 5
        else:
            box = pg.ev("([t, el]) => { WB.lockcam = t; const b = window.elementBoxes(t)[el]; WB.lockcam = null; return b || null; }", [s, e["el"]])
            if not box or not all(np.isfinite(v) for v in box):
                rows.append({**e, "diff": None, "pass": False, "why": "元素没有框"})
                continue
            x0, y0, x1, y1 = [int(round(v)) for v in box]
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(1920, x1), min(BAND, y1)
            if x1 - x0 < 4 or y1 - y0 < 4:
                rows.append({**e, "diff": None, "pass": False, "why": "元素在画外或全在字幕带里"})
                continue
            fa, fb = pg.frame(ta, s), pg.frame(tb, s)
            dd = np.abs(fa[y0:y1, x0:x1] - fb[y0:y1, x0:x1]).max(axis=2)
            v = int((dd > 12).sum())                     # 框内变了的像素数（不随框大小稀释：大框里的一笔淡色虚线也算得出来）
            ok = v > threshold
        rows.append({**e, "diff": round(float(v), 3), "mean": round(float(dd.mean()), 3) if e["do"] != "camera" else None, "pass": bool(ok)})
        by_beat.setdefault(e["beat"], []).append(ok)
    for r in rows:
        by_beat.setdefault(r["beat"], [])
    unregistered = sorted(b for b in expect if not any(e["beat"] == b for e in pg.ev("eventTimes()")))
    fail_beats = sorted(b for b, oks in by_beat.items() if not any(oks))
    diffs = sorted(r["diff"] for r in rows if r.get("diff") is not None and r["do"] != "camera")
    q10 = float(np.quantile(diffs, 0.1)) if diffs else None
    detail = {"threshold": threshold, "calibrated": calibrated, "events": len(rows), "events_pass": sum(r["pass"] for r in rows),
              "beats_expected": len(expect), "beats": len(by_beat), "beats_fail": fail_beats, "beats_unregistered": unregistered, "diff_q10": q10, "diff_min": diffs[0] if diffs else None,
              "events_fail": [{k: r.get(k) for k in ("beat", "el", "do", "start", "dur", "diff", "why")} for r in rows if not r["pass"]], "rows": rows}
    return item("semantic", not fail_beats, detail)


def check_determinism(n, total, ranges, qdir):
    rng = random.Random(cuelib.CFG.get("qa.seed", 20261022))
    pool = [(a, b) for a, b in (ranges or [(0, total)])]
    ts = sorted(round(rng.uniform(*rng.choice(pool)), 2) for _ in range(n))
    dirs = [qdir / "det-a", qdir / "det-b"]
    rcs = []
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)               # 先清空：渲染失败时不能拿上一次的旧 PNG 判 PASS
        r = subprocess.run(["bash", str(cuelib.CFG.skill_dir / "scripts/render.sh"), "--project", str(cuelib.PROJ), "stills", ",".join(map(str, ts)), str(d)], capture_output=True, text=True)
        rcs.append(r.returncode)
    h = [{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*.png"))} for d in dirs]
    want = len(set(ts))
    ok = all(rc == 0 for rc in rcs) and len(h[0]) == want and len(h[1]) == want and h[0] == h[1]
    return item("determinism", ok, {"n": len(h[0]), "expected": want, "render_exit": rcs, "times": ts, "mismatch": [k for k in h[0] if h[0].get(k) != h[1].get(k)]})


# ---------- style_lint：场景里不写死颜色与字体（只在有 style 键的新格式工程跑） ----------
LINT_FONTS = ("Songti", "PingFang", "Georgia", "Hiragino", "Menlo", "Monaco", "Helvetica", "Arial", "Times", "Courier", "Kaiti", "Heiti", "STSong", "STKaiti",
              "STHeiti", "SimSun", "SimHei", "YaHei", "Noto", "Source Han", "Avenir", "Futura", "Baskerville", "Palatino", "Verdana", "Optima", "Didot", "Lucida",
              "monospace", "sans-serif", "serif", "cursive", "fantasy", "system-ui", "-apple-system", "BlinkMacSystemFont")
LINT_RES = (re.compile(r"(?<![\w&#])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_])"),     # #rgb #rgba #rrggbb #rrggbbaa
            re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\s*\("),                                     # rgb( rgba( hsl( …
            re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in LINT_FONTS) + r")(?![\w-])"),           # 字体名
            re.compile(r"\d(?:\.\d+)?px\s+[A-Za-z\"']"))                                                     # '64px Georgia' 一类字体简写
LINT_OK = re.compile(r"^//\s*style-lint:\s*ok\s+\S")


def js_strings(src):
    """粗分词（不跑 JS）：跳过注释，返回字符串字面量（含模板串静态部分）[(起始行号, 内容)] 与各行行尾 // 注释 {行号: 注释}。
    正则字面量按前一个有效字符判（( , = : [ ! & | ? { } ; + - * % < > ~ ^ 之后的 / 当正则）。"""
    out, comments, stack, i, n, line, prev = [], {}, [], 0, len(src), 1, ""

    def scan(j, end):   # 从 j 读到 end（引号或模板串的 ` / ${）为止，返回 (内容, 停下的位置)
        nonlocal line
        buf = []
        while j < n and not end(j):
            if src[j] == "\\":
                buf.append(src[j:j + 2]); line += src[j:j + 2].count("\n"); j += 2; continue
            line += src[j] == "\n"
            buf.append(src[j]); j += 1
        return "".join(buf), j
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            line += c == "\n"; i += 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); j = n if j < 0 else j
            comments[line] = src[i:j]; i = j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            line += src.count("\n", i, j); i = j; continue
        if c in "'\"":
            l0 = line
            text, j = scan(i + 1, lambda k, q=c: src[k] == q or src[k] == "\n")
            out.append((l0, text)); i, prev = (j + 1 if j < n and src[j] == c else j), c; continue
        if c == "`" or (c == "}" and stack and stack[-1] == 0):
            if c == "}":
                stack.pop()
            l0 = line
            text, j = scan(i + 1, lambda k: src[k] == "`" or src.startswith("${", k))
            out.append((l0, text))
            if src.startswith("${", j):
                stack.append(0); i, prev = j + 2, "{"
            else:
                i, prev = j + 1, "`"
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^}" or re.search(r"(?<![\w$.])(?:return|typeof|case|do|else|in|of|void|yield|await|delete|new)\s*$", src[max(0, i - 12):i])):
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == "/" and not cls:
                    break
                cls = True if src[j] == "[" else False if src[j] == "]" else cls
                j += 1
            i = j + 1
            while i < n and src[i].isalpha():
                i += 1
            prev = "/"; continue
        if stack and c in "{}":
            stack[-1] += 1 if c == "{" else -1
        prev, i = c, i + 1
    return out, comments


def check_style_lint(cfg):
    files = sorted((cuelib.PROJ / "engine" / cfg.film / "scenes").glob("*.js"))
    probs, exempt = [], []
    for f in files:
        src = f.read_text(encoding="utf-8")
        lines, (strs, comments) = src.split("\n"), js_strings(src)
        ok = {ln for ln, c in comments.items() if LINT_OK.match(c)}
        for ln, text in strs:
            hits = [m.group(0) for r in LINT_RES for m in r.finditer(text)]
            if not hits:
                continue
            rec = {"file": f.name, "line": ln, "hits": hits[:4], "code": lines[ln - 1].strip()[:140]}
            (exempt if any(k in ok for k in range(ln, ln + text.count("\n") + 1)) else probs).append(rec)
    return item("style_lint", bool(files) and not probs, {"style": cfg.get("style"), "files": [f.name for f in files], "problems": probs, "exempted": exempt})


def check_layout(pg, total, ranges):
    js = """(ts) => { const out = [];
      const M = WB.moves();
      for (const t of ts) { const ca = window.cameraAt(t), cb = window.cameraAt(t - 1 / 30), shot0 = Math.max(0, ...M.filter(m => m[1] <= t).map(m => m[1]));
        const still = !(Math.abs(ca.x - cb.x) * ca.z + Math.abs(ca.y - cb.y) * ca.z > 1 || Math.abs(ca.z - cb.z) > 1e-4);
        const it = WB.items(t).filter(i => i.onScreen).map(i => { const w = i.x1 - i.x0, h = i.y1 - i.y0;
          return { text: i.text, sid: i.sid, el: i.el, t0: i.t0, t1: i.t1, rot: i.rot, px: i.px, x0: i.x0, y0: i.y0, x1: i.x1, y1: i.y1, ix0: i.x0 + w * 0.08, ix1: i.x1 - w * 0.08, iy0: i.y0 + h * 0.15, iy1: i.y1 - h * 0.15 }; });
        out.push({ t, still, shot0, it }); }
      return out; }"""
    ts = [round(k * 0.25, 2) for k in range(int(total / 0.25) + 1) if in_ranges(k * 0.25, ranges)]
    samples = []
    for k in range(0, len(ts), 200):
        samples += pg.ev(js, ts[k:k + 200])
    probs, n_still, seen, label = [], 0, {}, {}
    # 归并键＝(问题种类, 笔画在 WB.S 的下标 sid)：同一串字写在两处（如片头公式与代码第 4 行）是两条笔画、分别计时，
    # 不再按字串前 16 字合并（合并时两处同一采样时刻各记一次，会把各自不到 0.5 s 的掠过拼成「切半截 0.5 s」）。
    # 老工程的 wb/common.js 副本不报 sid：退回按字串前 16 字归并（与改前一致）
    def mark(kind, i, t):
        k = (kind, i["sid"] if i.get("sid") is not None else "字串:" + i["text"][:16])
        seen.setdefault(k, []).append(t)
        label.setdefault(k, i["text"][:16])
    for smp in samples:
        t = smp["t"]
        for i in smp["it"]:
            vis = i["ix1"] > 0 and i["ix0"] < 1920 and i["iy1"] > 0 and i["iy0"] < 1080
            cut = vis and (i["ix0"] < 0 or i["ix1"] > 1920 or i["iy0"] < 0 or i["iy1"] > 1080)
            top = vis and i["iy0"] < 60
            for kind, bad in (("切半截", cut), ("离上边<60px", top)):
                if bad:
                    mark(kind, i, t)
        if not smp["still"]:
            continue
        n_still += 1
        for i in smp["it"]:   # 字幕带：画面里任何一行字的包围盒都不得与它相交
            if i["y1"] > BAND and i["y0"] < 1080 and i["x1"] > 0 and i["x0"] < 1920:
                mark("压字幕带", i, t)
        recent = [i for i in smp["it"] if t - i["t0"] <= 6 and i["t0"] >= smp["shot0"] - 0.2 and t >= i["t1"] and not i["rot"]]   # 当前镜头里写上的
        for i in recent:
            why = []
            if i["x0"] < 110 or i["x1"] > 1810:
                why.append("出左右安全区")
            if i["px"] * 0.85 < 32:
                why.append(f"字高 {i['px'] * 0.85:.0f}px")
            if why:
                probs.append({"t": t, "text": i["text"][:16], "why": "、".join(why), "box": [round(v) for v in (i["x0"], i["y0"], i["x1"], i["y1"])]})
        for a in range(len(recent)):
            for b in range(a + 1, len(recent)):
                A, B = recent[a], recent[b]
                ins = lambda r: (r["x0"] + (r["x1"] - r["x0"]) * .12, r["y0"] + (r["y1"] - r["y0"]) * .12, r["x1"] - (r["x1"] - r["x0"]) * .12, r["y1"] - (r["y1"] - r["y0"]) * .12)
                a0, b0 = ins(A), ins(B)
                ow, oh = min(a0[2], b0[2]) - max(a0[0], b0[0]), min(a0[3], b0[3]) - max(a0[1], b0[1])
                if ow > 0 and oh > 0 and ow * oh > 0.3 * min((a0[2] - a0[0]) * (a0[3] - a0[1]), (b0[2] - b0[0]) * (b0[3] - b0[1])):
                    probs.append({"t": t, "text": A["text"][:10] + "｜" + B["text"][:10], "why": "重叠"})
    for (kind, sid), tl in seen.items():   # 切半截／贴上边：连续 ≥0.5 s（相邻采样 0.25 s，连着 3 个及以上）才算；压字幕带：相机停住时一次即算
        run = [tl[0]]
        for t in tl[1:] + [None]:
            if t is not None and t - run[-1] <= 0.26:
                run.append(t); continue
            if len(run) >= (1 if kind == "压字幕带" else 3):
                probs.append({"t": run[0], "text": label[(kind, sid)], "sid": sid if isinstance(sid, int) else None, "why": f"{kind} {run[-1] - run[0] + 0.25:.2f}s"})
            if t is not None:
                run = [t]
    by_sid = any(isinstance(k[1], int) for k in seen) or any(i.get("sid") is not None for smp in samples for i in smp["it"])
    return item("layout", not probs, {"samples": len(samples), "still_samples": n_still, "merge_key": "sid（WB.S 下标）" if by_sid else "字串前 16 字（老 common.js 无 sid）",
                                      "problems": probs})


def check_pen(pg, ranges, limit=1.5):
    floor = min(1.0, limit)   # 记录下限：阈值配得比 1 s 小时跟着降，否则短闲停在记录这一步就丢了
    r = pg.ev("""(floor) => { const cs = Object.values(TIMING.cues), a = Math.min(...cs.map(c => c.start)), b = Math.max(...cs.map(c => c.end)), out = []; let r0 = null, longest = 0;
      const mv = t => { const p = window.cameraAt(t), q = window.cameraAt(t - 1 / 30); return Math.abs(p.x - q.x) * p.z + Math.abs(p.y - q.y) * p.z > 1 || Math.abs(p.z - q.z) > 1e-4; };
      for (let t = a; t <= b + 1e-9; t += 0.05) { const on = window.penAt(t).length > 0 || mv(t);
        if (!on && r0 == null) r0 = t;
        if ((on || t + 0.05 > b) && r0 != null) { const r1 = on ? t : b; longest = Math.max(longest, r1 - r0); if (r1 - r0 >= floor) out.push([+r0.toFixed(2), +r1.toFixed(2)]); r0 = null; } }
      return { span: [a, b], runs: out, longest }; }""", floor)
    if ranges:   # 只按范围内的交集算连续闲停（例：9.5–12 s 的闲停在 --range 0-10 里只算 0.5 s）
        runs = sorted({(round(max(x[0], a_), 2), round(min(x[1], b_), 2)) for x in r["runs"] for a_, b_ in ranges if x[0] < b_ and x[1] > a_})
        runs = [[a, b] for a, b in runs if b - a >= floor]
        longest = max((x[1] - x[0] for x in runs), default=0.0)
    else:
        runs, longest = r["runs"], r["longest"]
    fails = [x for x in runs if x[1] - x[0] >= limit - 1e-6]
    return item("pen_idle", not fails, {"span": r["span"], "limit_s": limit, "longest_s": round(longest, 2), "fail_runs_ge_1_5s": fails, "runs_ge_1_0s": runs, "record_floor_s": floor})


def check_cam_pen(pg, ranges):
    r = pg.ev("""() => { const ST = WB.SETTLE, bad = [], vis = (s, t) => { const v = WB.view(WB.camAt(t)); return !(s.bb[2] < v[0] || s.bb[0] > v[2] || s.bb[3] < v[1] || s.bb[1] > v[3]); };
      // 糊影区间：画框中心与两角在 1/30 s 里的屏幕位移 ≥24 px（与 drawOne 的运动模糊同口径）
      const toS = (c, x, y) => [(x - c.x) * c.z + 960, (y - c.y) * c.z + 540], blur = []; let b0 = null;
      for (let t = 1 / 30; t <= window.__total + 1e-9; t += 1 / 30) { const a = WB.camAt(t), p = WB.camAt(t - 1 / 30), v = WB.view(a);
        const d = Math.max(...[[a.x, a.y], [v[0], v[1]], [v[2], v[3]]].map(([x, y]) => { const u = toS(a, x, y), w = toS(p, x, y); return Math.hypot(u[0] - w[0], u[1] - w[1]); }));
        if (d >= 24 && b0 == null) b0 = t - 1 / 30; if (d < 24 && b0 != null) { blur.push([b0, t]); b0 = null; } }
      const M = [...WB.moves(), ...blur].sort((x, y) => x[0] - y[0]).reduce((o, m) => { const l = o[o.length - 1]; if (l && m[0] <= l[1] + 1e-3) l[1] = Math.max(l[1], m[1]); else o.push([...m]); return o; }, []);
      // camOk 笔画：起笔 t0 起 0.3 s 内逐 1/30 s 差分——缩放变化率 |Δz/z|（每秒）与画面平移速度（相机中心世界位移×z，屏幕 px/秒）取最大
      const ZR = 0.05, PV = 40, WIN = 0.3, speed = t0 => { let zr = 0, pv = 0; for (let k = 1; k <= Math.round(WIN * 30); k++) { const a = WB.camAt(t0 + (k - 1) / 30), b = WB.camAt(t0 + k / 30);
          zr = Math.max(zr, Math.abs(b.z - a.z) / a.z * 30); pv = Math.max(pv, Math.hypot(b.x - a.x, b.y - a.y) * (a.z + b.z) / 2 * 30); } return [zr, pv]; }, ok = [];
      for (const s of WB.S) { if (s.lead || s.nopen || !s.bb) continue;
        const m = M.find(([a, b]) => s.t0 > a - 1e-3 && s.t0 < b + ST - 1e-3);
        if (s.camOk) { const [zr, pv] = speed(s.t0), seen = vis(s, s.t0) || vis(s, s.t0 + WIN) || (!!m && vis(s, m[1])), fast = zr > ZR || pv > PV;
          const r = { t0: +s.t0.toFixed(2), el: s.el || s.kind, str: s.str || null, zoom_rate_per_s: +zr.toFixed(4), pan_px_per_s: +pv.toFixed(1), in_move: m ? m.map(x => +x.toFixed(2)) : null, on_screen: seen, pass: !(fast && seen) };
          ok.push(r); if (!r.pass) bad.push(Object.assign({ camOk: true, why: `慢推中起笔但相机不够慢（缩放 ${r.zoom_rate_per_s}/s、平移 ${r.pan_px_per_s} px/s；上限 ${ZR}/s、${PV} px/s）` }, r));
          continue; }
        if (m && (vis(s, s.t0) || vis(s, m[1]))) bad.push({ t0: +s.t0.toFixed(2), el: s.el || s.kind, str: s.str || null, move: m.map(x => +x.toFixed(2)) }); }
      return { settle_s: ST, moves: WB.moves().length, blur_spans: blur.length, merged: M.length, shifted_at_build: WB.SHIFT.length,
        cam_ok: { n: ok.length, limits: { zoom_rate_per_s: ZR, pan_px_per_s: PV, window_s: WIN }, strokes: ok }, bad }; }""")
    r["bad"] = [x for x in r["bad"] if in_ranges(x["t0"], ranges)]
    return item("cam_pen", not r["bad"], r)


def check_count_land(pg, out, ranges):
    p = out / "audio" / "cues.json"
    if not p.is_file():
        return item("count_land", True, "无 cues.json（无声版）跳过", info=True)
    cj = {c["id"]: c for c in json.loads(p.read_text(encoding="utf-8"))["cues"]}
    tl = cuelib.load_timeline()
    dflt = (tl.get("motion") or {}).get("land_offset_default", -0.15)
    want = {}
    for sc in tl["scenes"]:
        for b in sc.get("beats") or []:
            for e in b.get("events") or []:
                if e.get("do") == "count":
                    land = cj[e["land_cue"]]["end"] + e.get("land_offset", dflt)
                    if in_ranges(land, ranges):
                        want[(cuelib.beat_key(sc["id"], b), e["el"])] = land
    got = {(e["beat"], e["el"]): e.get("land") for e in pg.ev("eventTimes()") if e["do"] == "count"}
    rows = [{"beat": k[0], "el": k[1], "want": round(w, 3), "got": got.get(k), "err": None if got.get(k) is None else round(got[k] - w, 3)} for k, w in want.items()]
    bad = [r for r in rows if r["got"] is None or abs(r["err"]) > 0.1]
    return item("count_land", not bad, {"n": len(rows), "max_abs_err": max((abs(r["err"]) for r in rows if r["err"] is not None), default=None), "bad": bad, "rows": rows})


def check_still(video, T, ranges, source="video"):
    if ranges:
        return [item("still_video", True, "分段拼接的草稿不做（口播时刻对不上拼接后的时间轴）", info=True)]
    W_, H_ = 640, 360
    qcfg = json.loads(cuelib.CFG.path("qa.config").read_text(encoding="utf-8"))
    STILL_MAX = (qcfg.get("still_video") or {}).get("max_s", 1.5)
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=12,scale={W_}:{H_}:flags=area", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    F = np.frombuffer(r.stdout, np.uint8)
    n = len(F) // (W_ * H_)
    F = F[: n * W_ * H_].reshape(n, H_, W_)[:, : int(H_ * BAND / 1080)].astype(np.int16)
    cnt = (np.abs(np.diff(F, axis=0)) > 12).reshape(n - 1, -1).sum(1)
    cs = T["cues"].values()
    a, b = min(c["start"] for c in cs), max(c["end"] for c in cs)
    tail = [int(cnt[i]) for i in range(n - 1) if i / 12 >= b + 0.2 and (i + 2) / 12 <= n / 12 - 0.1]
    K = max(8, 3 * max(tail, default=0))
    runs, r0, longest = [], None, 0.0
    for i in range(n - 1):
        t = (i + 1) / 12
        if t < a or t > b:
            continue
        still = cnt[i] < K
        if still and r0 is None:
            r0 = t
        if (not still or t + 1 / 12 > b) and r0 is not None:
            d = t - r0 + (1 / 12 if still else 0)
            longest = max(longest, d)
            if d >= 1.0:
                runs.append([round(r0, 2), round(r0 + d, 2)])
            r0 = None
    if r0 is not None:   # 口播到片尾、循环没机会结算的静止段
        d = b - r0
        longest = max(longest, d)
        if d >= 1.0:
            runs.append([round(r0, 2), round(b, 2)])
    fails = [x for x in runs if x[1] - x[0] >= STILL_MAX - 1e-6]
    sv = item("still_video", not fails, {"K_changed_px": K, "tail_noise_max": max(tail, default=None), "tail_pairs": len(tail), "longest_s": round(longest, 2),
                                         "limit_s": STILL_MAX, "fail_runs": fails, "runs_ge_1_0s": runs, "source": source, "measured": str(video)})
    # 审片标过的死帧处（按 [节拍, 字] 锚点登记，起止从 timing.js 取）：处内任一 1.2 s 窗（14 个帧对），逐帧对变化像素累计 ≥ 整幅（遮字幕带）的 min_pct%
    cfg = qcfg.get("still_flagged") or {}
    win_s = cfg.get("window_s", 1.2)
    area, w = F.shape[1] * F.shape[2], int(round(win_s * 12))
    cs = np.concatenate([[0], np.cumsum(cnt)])
    def at(anchor):   # [节拍, 字]：字在该节拍口播里第一次出现的起读时刻；字为 None＝该节拍口播末尾
        beat, word = anchor
        B = T["beats"][beat]
        return B["end"] if word is None else B["charStart"][B["text"].index(word)]
    rows = []
    for sp in cfg.get("spots", []):
        a0, b0 = at(sp["from"]), at(sp["to"])
        ks = [k for k in range(n - 1 - w) if k / 12 >= a0 - 1e-6 and (k + w) / 12 <= b0 + 1e-6]
        vals = [(float(cs[k + w] - cs[k]) / area * 100, k / 12) for k in ks]
        lo = min(vals, default=(None, None))
        rows.append({"id": sp["id"], "from": sp["from"], "to": sp["to"], "span_s": [round(a0, 2), round(b0, 2)], "windows": len(vals),
                     "min_window_pct": None if lo[0] is None else round(lo[0], 3), "min_at_s": None if lo[1] is None else round(lo[1], 2)})
    mp = G["sample_change_min"] * 100 if G.get("sample_change_min") is not None else cfg.get("min_pct", 0.4)   # qa.gates 是占比（0.004），这里用百分数
    bad = [r for r in rows if r["min_window_pct"] is None or r["min_window_pct"] < mp]
    sf = gated(item("still_flagged", not bad, {"min_pct": mp, "window_s": win_s, "rows": rows, "bad": bad, "source": cfg.get("source"), "video_source": source}),
               G.get("sample_change_min", 0.004) is not None)
    return [sv, sf]


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    return json.loads(m[-1]) if m else None


def probe(path, entries):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", str(path)], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def check_av(video, out, ranges=None):
    info = probe(video, "format=duration:stream=codec_type,duration")
    has_a = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    wav = out / "audio" / "narration.wav"
    if not has_a or not wav.exists():
        return [item("av", True, "无口播音轨（声音未认可前的无声版），跳过", info=True), item("loudness", True, "无口播，跳过", info=True)]
    if ranges:   # 分段拼接的草稿：比它自己的画面流与声音流（口播按同样段界切来）
        sd = {s["codec_type"]: float(s.get("duration") or 0) for s in info["streams"]}
        vd, ad = sd.get("video", 0.0), sd.get("audio", 0.0)
    else:        # 成片：视频流、音频流各自时长（不看容器总时长），都要和 narration.wav 在 ±0.1 s 内
        vs = probe(video, "stream=codec_type,duration,nb_frames,avg_frame_rate")["streams"]
        v = next(s for s in vs if s["codec_type"] == "video"); a_ = next(s for s in vs if s["codec_type"] == "audio")
        num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
        vd = int(v["nb_frames"]) * den / num if v.get("nb_frames") and num else float(v["duration"])
        ad = float(a_["duration"])
        nd = float(probe(wav, "format=duration")["format"]["duration"])
        L = loudness(wav)
        li, tp = float(L["input_i"]), float(L["input_tp"])
        return [item("av", abs(vd - nd) <= 0.1 and abs(ad - nd) <= 0.1, {"video_stream_s": vd, "audio_stream_s": ad, "narration_s": nd}),
                item("loudness", abs(li + 16) <= 1 and tp <= -1.5, {"lufs": li, "true_peak": tp})]
    L = loudness(wav)
    li, tp = float(L["input_i"]), float(L["input_tp"])
    return [item("av", abs(vd - ad) <= 0.1, {"video_s": vd, "audio_s": ad}),
            item("loudness", abs(li + 16) <= 1 and tp <= -1.5, {"lufs": li, "true_peak": tp})]


def check_subtitles(T):
    caps = []
    for seg in T["seg"].values():
        caps += [{"start": seg["t0"] + c["start"], "end": seg["t0"] + c["end"], "text": c["text"]} for c in seg["captions"]]
    caps.sort(key=lambda c: c["start"])
    say = "".join(b["say"] for sc in cuelib.load_timeline()["scenes"] for b in (sc.get("beats") or []))
    bad, last = [], -1
    for c in caps:
        if c["end"] - c["start"] < 0.83 - 1e-6:
            bad.append({"text": c["text"], "why": f"{c['end'] - c['start']:.2f}s"})
        if cuelib.vis_len(c["text"]) > 32:
            bad.append({"text": c["text"], "why": "两行也放不下"})
        if c["start"] < last - 1e-6:
            bad.append({"text": c["text"], "why": "不单调"})
        last = c["end"]
    over16 = [c["text"] for c in caps if cuelib.vis_len(c["text"]) > 16]
    joined = "".join(c["text"] for c in caps) == say
    return item("subtitles", not bad and not over16 and joined, {"n": len(caps), "problems": bad, "over16": over16, "concat_equals_say": joined})


def check_redlines(out):
    r = subprocess.run([PY, str(cuelib.CFG.skill_dir / "scripts/check_redlines.py"), "--project", str(cuelib.PROJ), str(out)], capture_output=True, text=True)
    return item("redlines", r.returncode == 0, (r.stdout + r.stderr).strip()[-600:])


def check_storyboard(out):
    """分镜画面类型（1.3.0）：调 check_storyboard.py，按退出码记；老工程（skipped）、脚手架（scaffold）、未要求（not required）记 INFO。"""
    r = subprocess.run([PY, str(cuelib.CFG.skill_dir / "scripts/check_storyboard.py"), "--project", str(cuelib.PROJ), "--cues", str(Path(out) / "audio" / "cues.json")],
                       capture_output=True, text=True)
    info = r.returncode == 0 and any(f"STORYBOARD: {k}" in r.stdout for k in ("skipped", "scaffold", "not required"))
    return item("storyboard", r.returncode == 0, (r.stdout + r.stderr).strip()[-900:], info=info)


def hints(video, pg, ranges):
    """相机停留时长、推近次数（静止段已改成硬项 still_video / pen_idle）。"""
    keys = pg.ev("WB.K.map(k => [k.t, k.x, k.y, k.z])")
    holds, pushes = [], []
    for a, b in zip(keys, keys[1:]):
        moving = abs(a[1] - b[1]) + abs(a[2] - b[2]) > 2 or abs(a[3] - b[3]) > 1e-3
        if not moving:
            holds.append(round(b[0] - a[0], 2))
        elif b[3] > a[3] * 1.04:
            pushes.append(round(a[0], 2))
    return {"camera_holds_s": holds, "longest_hold_s": max(holds, default=0), "push_ins": pushes,
            "push_in_per_min": round(len([p for p in pushes if in_ranges(p, ranges)]) / max(1e-6, (sum(b - a for a, b in ranges) if ranges else keys[-1][0]) / 60), 2)}


def main():
    global BAND, G, RO
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", help="产物根（缺省 EF_OUT／project.json out_root）")
    ap.add_argument("--qa-dir", default="")
    ap.add_argument("--beats", default="")
    ap.add_argument("--range", default="", help="只查这些时段（全片秒，a-b,c-d）")
    ap.add_argument("--threshold", type=float, default=None, help="语义动作阈值临时覆盖（不写就读 tools/qa_config.json 的标定值）")
    ap.add_argument("--det-n", type=int, default=30)
    ap.add_argument("--skip", default="")
    a = ap.parse_args()
    cfg = cuelib.init(a.project)
    BAND, G, RO = int(cfg.get("qa.band_top", 880)), cfg.get("qa.gates") or {}, set(cfg.get("qa.record_only") or [])
    out, video = (Path(a.out) if a.out else cfg.out_root), Path(a.video)
    qdir = Path(a.qa_dir or out / "out")
    qdir.mkdir(parents=True, exist_ok=True)
    ranges = [tuple(float(x) for x in r.split("-")) for r in a.range.split(",") if r] if a.range else []
    beats = {b for b in a.beats.split(",") if b}
    skip = {s for s in a.skip.split(",") if s}
    T = cuelib.read_timing()
    res = {"video": str(video), "timing_meta": T.get("meta"), "ranges": ranges, "checks": []}
    if "style" in cfg.data:   # 新格式工程：记画法，跑 style_lint
        res["style"] = cfg.get("style")
        if "style_lint" not in skip:
            sl = check_style_lint(cfg)
            res["checks"].append(sl)
            print("style_lint", sl["status"], len(sl["detail"]["problems"]), flush=True)
    if "film_gate" not in skip:
        g, _ = check_film_gate(video, qdir)
        res["checks"].append(g)
        print("film_gate", g["status"], g["detail"] if isinstance(g["detail"], dict) else "", flush=True)
    with Page() as pg:
        total = pg.ev("window.__total")
        if "gates_qa" not in skip:
            j, _ = check_jumps(pg, qdir, ranges)
            res["checks"].append(j)
            print("jumps", j["status"], len(j["detail"]["unlabelled"]) if isinstance(j["detail"], dict) else j["detail"], flush=True)
        if "semantic" not in skip:
            qc = json.loads(cfg.path("qa.config").read_text(encoding="utf-8"))
            thr, cal = (a.threshold, False) if a.threshold is not None else (qc["semantic_threshold"], bool(qc.get("calibrated")))
            sm = gated(check_semantic(pg, beats, thr, ranges, T, cal), G.get("mentioned_el_must_move", True))
            res["checks"].append(sm)
            print("semantic", sm["status"], {k: sm["detail"][k] for k in ("threshold", "calibrated", "events", "events_pass", "beats_expected", "beats_fail", "beats_unregistered", "diff_q10")}, flush=True)
        if "layout" not in skip:
            ly = check_layout(pg, total, ranges)
            res["checks"].append(ly)
            print("layout", ly["status"], len(ly["detail"]["problems"]), flush=True)
        if "pen_idle" not in skip:
            lim = G.get("still_in_speech_s", 1.5)
            pi = gated(check_pen(pg, ranges, lim or 1.5), bool(lim))
            res["checks"].append(pi)
            print("pen_idle", pi["status"], {k: pi["detail"][k] for k in ("longest_s", "fail_runs_ge_1_5s")}, flush=True)
        if "cam_pen" not in skip:
            cp = gated(check_cam_pen(pg, ranges), G.get("camera_settle", True))
            res["checks"].append(cp)
            print("cam_pen", cp["status"], len(cp["detail"]["bad"]), flush=True)
        if "count_land" not in skip:
            cl = gated(check_count_land(pg, out, ranges), G.get("number_land", True))
            res["checks"].append(cl)
            print("count_land", cl["status"], cl["detail"]["max_abs_err"] if isinstance(cl["detail"], dict) else cl["detail"], flush=True)
        res["hints"] = hints(video, pg, ranges)
        res["page_errors"] = pg.errors
    if "determinism" not in skip:
        dt = check_determinism(a.det_n, total, ranges, qdir)
        res["checks"].append(dt)
        print("determinism", dt["status"], flush=True)
    if "still_video" not in skip:
        src = json.loads(cfg.path("qa.config").read_text(encoding="utf-8")).get("still_video_source", "video")
        sv_video, sv_err = video, None
        if src not in ("video", "noambient_draft"):
            sv_err = f"tools/qa_config.json 的 still_video_source 只能是 video 或 noambient_draft：{src!r}"
        elif src == "noambient_draft" and not ranges:   # 无装饰动作草稿：WB.ambientT 恒 0，装饰性持续动作冻住，只剩内容揭开
            sv_video = qdir / "still-noambient-draft.mp4"
            r = subprocess.run(["bash", str(cfg.skill_dir / "scripts/render.sh"), "--project", str(cuelib.PROJ), "draft", "--noambient", str(sv_video)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not sv_video.is_file():
                sv_err = f"still_video_source=noambient_draft：无装饰草稿没渲出来（退出 {r.returncode}）：{(r.stdout + r.stderr).strip()[-400:]}"
        if sv_err:
            res["checks"].append(item("still_video", False, sv_err))
            print("still_video FAIL", sv_err, flush=True)
        for sv in ([] if sv_err else check_still(sv_video, T, ranges, src)):
            res["checks"].append(sv)
            d = sv["detail"]
            print(sv["name"], sv["status"], d if isinstance(d, str) else ({k: d[k] for k in ("K_changed_px", "longest_s", "fail_runs")} if sv["name"] == "still_video" else d["bad"]), flush=True)
    res["checks"] += check_av(video, out, ranges)
    res["checks"].append(check_subtitles(T))
    if "redlines" not in skip:
        res["checks"].append(check_redlines(out))
    if "storyboard" not in skip:
        sb = check_storyboard(out)
        res["checks"].append(sb)
        print("storyboard", sb["status"], flush=True)
    fails = [c["name"] for c in res["checks"] if c["status"] == "FAIL"]
    res["verdict"] = "FAIL" if fails else "PASS"
    (qdir / "qa.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in res["checks"]:
        print(f"  {c['status']:<4} {c['name']}")
    print(f"QA {'不通过：' + '、'.join(fails) if fails else '硬门禁全过'} → {qdir / 'qa.json'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
