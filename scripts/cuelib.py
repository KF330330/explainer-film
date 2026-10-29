#!/usr/bin/env python3
"""口播 cue 的共用逻辑（make_audio / provisional_cues / make_timing / compose 共用）。

- load_cues(timeline)：按 timeline 顺序展开全部 cue（含子 cue），每条带显示稿 text 与读法稿 tts（tools/tts_overrides.json 可覆盖个别 cue 的读法，只许改标点空格）。
- head_only(timeline)：只有片头（一拍都没有）时给各段 hold_secs 与缺 hold_secs 的段名（provisional_cues、make_timing 共用）。
- WHOLE_BEATS（tts_overrides.json 的 whole_beats）：这些节拍的子 cue 读法稿拼成一整句送 ElevenLabs 合成一次，make_audio 再按停顿切回子 cue。
  子 cue 的读法稿由节拍 tts 按 voice_diff.norm 对齐切出：逐条找 norm(tts 前缀) 恰好等于前面各子 cue
  norm 拼接的最短位置，再把其后紧跟的标点吞进当前子 cue；切完逐条核 norm(读法片段)==norm(显示片段)，不等即报错。
- gap_ms(tts)：cue 之后的气口，与 el_cued.effective_inter_cue_gap_ms 同规则
  （默认 150 ms；读法稿以 。！？.!? 结尾（后面可跟右引号）抬到 450 ms，问号 550 ms）。
- pack_cues(say)：字幕切块（split_chunks/pack_cues），MAX＝project.json timing.max_cue。
项目常量（产物根、片头片尾静音、气口、字幕长、BREAKS、读法覆盖）由 init(project) 从 project.json 载入；各脚本 main() 开头调一次。
"""
import json
import math
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import efconfig  # noqa: E402
from voice_diff import norm  # noqa: E402

CFG = PROJ = OUT_DEFAULT = None   # init() 后：项目配置、项目根、产物根
HEAD_SILENCE, TAIL_SILENCE = 3.0, 1.2     # 片头／片尾静音（timing.head_silence／tail_silence），make_audio 加进音轨
BASE_GAP_MS, SENT_GAP_MS, Q_GAP_MS = 150, 450, 550
OVERRIDES, WHOLE_BEATS = {}, {}   # tools/tts_overrides.json；WHOLE_BEATS＝{节拍: {why, …}}：整拍一次合成再切回子 cue（只用于 elevenlabs）
_CLOSE = "”’」』】\""


def init(project=None):
    """载入项目（--project ＞ EF_PROJECT ＞ cwd 向上找 project.json），把本模块的项目常量换成 project.json 的值。"""
    global CFG, PROJ, OUT_DEFAULT, HEAD_SILENCE, TAIL_SILENCE, BASE_GAP_MS, SENT_GAP_MS, Q_GAP_MS, MAX_CUE, BREAKS, OVERRIDES, WHOLE_BEATS
    CFG = efconfig.load(project)
    PROJ, OUT_DEFAULT, t = CFG.project_dir, CFG.out_root, CFG.get("timing") or {}
    HEAD_SILENCE, TAIL_SILENCE = float(t.get("head_silence", 3.0)), float(t.get("tail_silence", 1.2))
    g = t.get("gaps_ms") or {}
    BASE_GAP_MS, SENT_GAP_MS, Q_GAP_MS = int(g.get("base", 150)), int(g.get("sentence", 450)), int(g.get("question", 550))
    MAX_CUE, BREAKS = int(t.get("max_cue", 16)), dict(t.get("breaks") or [])
    p = PROJ / "tools" / "tts_overrides.json"
    ov = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    OVERRIDES, WHOLE_BEATS = {k: v for k, v in ov.items() if not k.startswith("_") and k != "whole_beats"}, ov.get("whole_beats", {})
    os.environ["PATH"] = str(CFG.path("ffmpeg_bin_dir", "~/.venvs/explainer-film/bin")) + os.pathsep + os.environ.get("PATH", "")
    return CFG


def timing_js():
    return PROJ / "engine" / CFG.film / "timing.js"


def read_timing():
    s = timing_js().read_text(encoding="utf-8")
    return json.loads(s[s.index("{"): s.rindex("}") + 1])


def file_fp(path):
    """文件内容 sha256 前 12 位（音色指纹）。"""
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def load_timeline(path=None):
    return json.loads(Path(path or PROJ / "timeline.json").read_text(encoding="utf-8"))


def beat_key(scene_id, b):
    return f"{scene_id}_{b['k']:02d}"


def split_tts(beat, key=""):
    cues = beat["cues"]
    tts = beat["tts"]
    if len(cues) == 1:
        return [tts]
    targets = [norm(c["text"]) for c in cues]
    if "".join(targets) != norm(tts):
        raise ValueError(f"{key}: 子 cue 显示稿归一后拼接 ≠ 读法稿归一（{''.join(targets)} / {norm(tts)}）")
    parts, pos = [], 0
    for i in range(len(targets) - 1):
        want = "".join(targets[: i + 1])
        j = pos
        while j <= len(tts) and norm(tts[:j]) != want:
            j += 1
        if j > len(tts):
            raise ValueError(f"{key}: 读法稿里找不到子 cue {cues[i]['id']} 的切点")
        while j < len(tts) and norm(tts[j]) == "":
            j += 1
        parts.append(tts[pos:j])
        pos = j
    parts.append(tts[pos:])
    for c, p, t in zip(cues, parts, targets):
        if norm(p) != t or not p.strip():
            raise ValueError(f"{key}: 子 cue {c['id']} 读法片段「{p}」与显示稿「{c['text']}」对不上")
    if "".join(parts) != tts:
        raise ValueError(f"{key}: 读法片段拼接 ≠ 读法稿")
    return parts


def load_cues(tl=None):
    tl = tl or load_timeline()
    out = []
    for sc in tl["scenes"]:
        for b in sc.get("beats") or []:
            key = beat_key(sc["id"], b)
            if "".join(c["text"] for c in b["cues"]) != b["say"]:
                raise ValueError(f"{key}: 子 cue 显示稿拼接 ≠ say")
            for c, t in zip(b["cues"], split_tts(b, key)):
                ov = OVERRIDES.get(c["id"])
                if ov:                                   # 读法覆盖：只许改标点、空格
                    if norm(ov["tts"]) != norm(t):
                        raise ValueError(f"{c['id']}: 读法覆盖「{ov['tts']}」归一后 ≠ 原读法「{t}」")
                    t = ov["tts"]
                out.append({"id": c["id"], "beat": key, "scene": sc["id"], "text": c["text"], "tts": t})
    ids = [c["id"] for c in out]
    if len(set(ids)) != len(ids):
        raise ValueError("cue id 有重复")
    return out


def head_only(tl=None):
    """只有片头的时间轴（timeline 一拍都没有）：返回 (holds, missing)——holds＝[(段名, hold_secs)…]，missing＝没写正数 hold_secs 的段名；
    有拍或没有场景时返回 None。missing 为空时 provisional_cues 写 cues: []、make_timing 每段时长取 hold_secs；否则两者退出 2。"""
    tl = tl or load_timeline()
    scenes = tl.get("scenes") or []
    if not scenes or any(sc.get("beats") for sc in scenes):
        return None
    def ok(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
    return [(sc["id"], float(sc["hold_secs"])) for sc in scenes if ok(sc.get("hold_secs"))], [sc["id"] for sc in scenes if not ok(sc.get("hold_secs"))]


def gap_ms(tts_text):
    t = (tts_text or "").rstrip()
    m = re.search(r"([。！？.!?])([" + re.escape(_CLOSE) + r"]*)$", t)
    if not m:
        return BASE_GAP_MS
    return Q_GAP_MS if m.group(1) in ("？", "?") else max(BASE_GAP_MS, SENT_GAP_MS)


# ---------------- 字幕切块（MAX＝timing.max_cue） ----------------
# MAX 为 16 时硬切会切出「示，」「7」这类 0.2 s 的孤字幕（违反每条 ≥0.83 s）。改为：超长分句先查
# BREAKS（project.json timing.breaks：[[分句, 前半句可见字数], …]，按词边界给出），查不到就在居中处切，且不切开数字与单位、不切开英文词。
MAX_CUE = 16
PAUSE = set("，。！？；：、」）』”’…—")
OPEN = set("「（『“‘")
PUNCT = PAUSE | OPEN
BREAKS = {}


def vis_len(s):
    return sum(1 for c in s if not c.isspace() and c not in PUNCT)


def _cut_at_vis(c, n):
    """前半句恰好 n 个可见字的切点（字符下标）。"""
    k = 0
    for j, ch in enumerate(c):
        if not ch.isspace() and ch not in PUNCT:
            k += 1
        if k == n:
            return j + 1
    return len(c)


def _balanced_cut(c):
    n = vis_len(c)
    parts = -(-n // MAX_CUE)
    target = -(-n // parts)
    best, best_cost = None, 1e9
    for j in range(1, len(c)):
        a, b = c[j - 1], c[j]
        if a.isascii() and a.isalnum() and b.isascii() and b.isalnum():
            continue                                   # 不切开英文词、多位数
        if a.isdigit() or (a == " " and j >= 2 and c[j - 2].isdigit()):
            continue                                   # 数字后面跟着单位，不切开
        v = vis_len(c[:j])
        if v == 0 or v > MAX_CUE or vis_len(c[j:]) == 0:
            continue
        cost = abs(v - target)
        if cost < best_cost:
            best, best_cost = j, cost
    return best or _cut_at_vis(c, MAX_CUE)


def split_chunks(say):
    chunks, cur, i = [], "", 0
    while i < len(say):
        ch = say[i]
        if ch in OPEN and vis_len(cur) > 0:
            chunks.append(cur)
            cur = ""
        cur += ch
        if ch in PAUSE:
            while i + 1 < len(say) and say[i + 1] in PAUSE:
                i += 1
                cur += say[i]
            chunks.append(cur)
            cur = ""
        i += 1
    if cur:
        chunks.append(cur)
    out = []
    for c in chunks:
        while vis_len(c) > MAX_CUE:
            cut = _cut_at_vis(c, BREAKS[c]) if c in BREAKS else _balanced_cut(c)
            out.append(c[:cut])
            c = c[cut:]
        out.append(c)
    return [c for c in out if c]


def pack_cues(say):
    cues, cur = [], ""
    for c in split_chunks(say):
        if cur and vis_len(cur + c) > MAX_CUE:
            cues.append(cur)
            cur = c
        else:
            cur += c
    if cur:
        cues.append(cur)
    assert "".join(cues) == say, (cues, say)
    return cues


def weighted(ch):
    """线性摊时间时算一份的字符：汉字、字母、数字、% 与数字里的小数点；其余（空白、标点）沿前一字。"""
    return ch.isalnum() or ch in "%."
