#!/usr/bin/env python3
"""explainer-film 脚手架（只用标准库；出帧自检调 scripts/selfcheck.sh）。
建项目：--dest D --film F --title T [--slug S] [--version v1] [--out-root R] [--copy-engine] [--tmp DIR]
  D 已存在且非空 → 拒绝、退出 2、不碰；D 不得在 skill 里；F 须 ^[a-z0-9_]+$ 且不与引擎自带目录、参考片 wbx 重名。
  复制 vendor/engine 的 13 个根文件＋软链 8 个大目录（--copy-engine 整份复制）；生成最小可渲染项目（B0 一拍写标题）与 project.json；
  建 out_root/{audio,review,out}；跑 selfcheck.sh --project D --no-voice（建项目不查 ElevenLabs 配置），不过 → 只删本次新建的目录与文件
  （产物侧只删本次新建且仍为空的目录），退出 2。
画法：--style ID（缺省 whiteboard）＝画法包 templates/styles/ID/：project.json 写 style（有这个键＝新格式工程）与 assets，theme＝模板主题逐键叠
  style.json 的 theme（required_fonts 取并集、extra_colors 写进主题），style.js 复制到 engine/<F>/wb/style.js，style.json 的 assets 复制到 engine/<F>/，
  qa 缺省项合并进 tools/qa_config.json；SCENE_LIBS／EXTRA_ASSETS 由 efconfig.scene_libs／extra_assets 生成。--list-styles 列出全部画法。
通用件与分镜（1.3.0）：templates/parts.js 复制到 engine/<F>/wb/parts.js，project.json 写 libs: ["<F>/wb/parts.js"]（经 SCENE_LIBS 加载）与 storyboard 段（模板缺省）；
  templates/CREDITS.md 写到 D/CREDITS.md（原件出处表）；脚手架 timeline 的 B0 拍带 "look": "字卡"。
三维可选件（1.3.1）：建项目加 --three ＝ templates/three.js 复制到 engine/<F>/wb/three.js，libs 写 ["<F>/wb/parts.js", "lib/three.min.js", "<F>/wb/three.js"]。
  已有新格式工程用 --dest D --add-three（老工程零写入拒绝）：写前校验（eras 能认出格式、工程里的 wb/three.js 不在或与模板字节相同），任何一条不过 → 零写入、退出 2；
  已带三维（libs 已含两项、three.js 与模板相同、eras 已一致）→ 零写入、退出 0；否则先把 project.json、eras_<F>.js、wb/three.js（在就备）备份到
  D/.add-three-bak-<epoch>/ 并核对（失败 → 工程零改动、退出 2），再在 libs 末尾补上缺的项、复制 three.js、重写 eras 的 SCENE_LIBS；
  任一步失败整体拷回（只删执行前不存在、由本次新建的文件，备份目录删掉）并退出 2，成功保留备份目录。index.html 不动。
更新：--dest D --relink（重建 8 个软链；遇真目录报错不碰）／--dest D --theme（按 project.json 的 theme 重写 engine/<F>/theme.js；新格式工程同时重拷 style.js）：
  先写临时文件／临时软链再原子替换，随后自检，不过 → 还原、退出 2。老工程（无 style 键）两者行为不变。
换画法：--dest D --restyle ID（只对新格式工程；老工程零写入拒绝）：先把 project.json、theme.js、wb/common.js、wb/style.js、eras_<F>.js 备份到
  D/.restyle-bak-<epoch>/（备份阶段任何失败 → 工程零改动、退出 2），再改 style、theme 重置为新画法默认、重拷 common.js 与新 style.js、重写 theme.js
  与 eras 的 SCENE_LIBS／EXTRA_ASSETS，全片自检（逐 0.25 s＋各段起点、中点 renderFrame）；任何一步失败整体拷回（只删执行前不存在、由本次新建的文件，
  备份目录删掉）并退出 2，成功保留备份目录。
清单：--write-manifest 重算 vendor/vendor_manifest.json（升级 vendor 后用；内容不变就不写）。
"""
import argparse, ast, copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time  # noqa: E401
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "scripts"))
import efconfig  # noqa: E402
VENG = SK / "vendor" / "engine"
TPL = SK / "templates"
STYLES = TPL / "styles"
STYLE_KEYS = ("id", "label", "summary", "fits", "avoid", "signature", "theme", "extra_colors", "required_fonts", "assets", "qa")
ROOT_FILES = ["index.html", "engine.js", "transitions.js", "render.py", "spec_assets.py", "audit_clip.py", "clip.html", "clip.js",
              "clip_schema.json", "eras.js", "eras_wbx.js", "LICENSE", "README-参考片.md"]
LINK_DIRS = ["lib", "scenes", "demos", "spacex", "spacex_wb", "transitions", "clips", "examples"]
RESERVED = set(LINK_DIRS) | {"wbx", "__pycache__"}
MOTION = {"enter": 0.35, "exit": 0.18, "zeta": 0.8, "lag": 0.08, "write_cps": 15, "title_cps": 7.5, "num_hold": 0.5, "creep": 0,
          "count_dur": [0.9, 1.3], "land_offset_default": -0.15}   # 动效契约缺省值（写进 timeline.json 的 motion）
COLOR_RE = re.compile(r"^(#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|(rgb|rgba|hsl|hsla)\([^()]*\)|[a-zA-Z]+)$")
THREE_LIBS = lambda film: ["lib/three.min.js", f"{film}/wb/three.js"]  # noqa: E731   三维可选件的两项 libs（排在 parts.js 之后）

class Fail(Exception):
    pass

def norm(p):
    """展开 ~ 后按操作系统物理解析（realpath：软链按目标、.. 在解析后的父目录上回退；尾部不存在的段按字面）：所有检查都在其后做。"""
    return Path(os.path.realpath(os.path.expanduser(str(p))))

def tilde(p):
    s, h = str(p), str(Path.home())
    return "~" + s[len(h):] if s == h or s.startswith(h + os.sep) else s

def jdump(o, compact=False):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(o, ensure_ascii=False, indent=1) + "\n"

def atomic_write(path, data):
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    os.replace(tmp, path)

def fill(name, **kv):
    s = (TPL / name).read_text(encoding="utf-8")
    for k, v in kv.items():
        s = s.replace(f"__{k}__", v)
    return s

COLORS = ["ink", "accent", "board", "wash", "dim", "soft", "card", "line", "tape", "card_band", "caption.bg", "paper.dots", "paper.light", "paper.warm"]
NUMS = ["speed", "lw", "settle", "caption.band", "caption.size", "caption.max_chars"]

def check_theme(th):
    """Python 侧先挡明显不合法的主题值（类型、颜色写法）；颜色是否真被浏览器认可由 common.js 启动时 CSS.supports 再核。"""
    if not isinstance(th, dict):
        raise Fail("project.json 的 theme 不是对象")
    g = lambda k: _dig(th, k)  # noqa: E731
    bad = [k for k in COLORS if not (isinstance(g(k), str) and COLOR_RE.match(g(k).strip()))]
    bad += [k for k in NUMS if not (isinstance(g(k), (int, float)) and not isinstance(g(k), bool) and g(k) > 0)]
    bad += [k for k in ("fonts.title", "fonts.body", "fonts.num") if not (isinstance(g(k), str) and g(k).strip())]
    gr, rf, ex = g("paper.grain"), g("required_fonts"), g("extra_colors")
    bad += [] if isinstance(gr, list) and len(gr) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in gr) else ["paper.grain"]
    bad += [] if isinstance(rf, list) and rf and all(isinstance(v, str) and v for v in rf) else ["required_fonts"]
    if ex is not None:   # 画法包的额外颜色键（style.json extra_colors）：列表本身合法，且每个键都是颜色写法
        bad += ([k for k in ex if not (isinstance(th.get(k), str) and COLOR_RE.match(th[k].strip()))]
                if isinstance(ex, list) and all(isinstance(k, str) and k for k in ex) else ["extra_colors"])
    if bad:
        raise Fail("主题值不合法：" + "；".join(f"{k}={g(k)!r}" for k in bad))

def _dig(d, key):
    for part in key.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d

def mkdirs(p, made):
    """逐级建目录，把本次新建的每一级记进 made（失败回滚时只 rmdir 这些）。"""
    todo = []
    while not p.exists():
        todo.append(p)
        p = p.parent
    for q in reversed(todo):
        q.mkdir()
        made.append(q)

def theme_js(th):
    check_theme(th)
    return fill("theme.js", THEME_JSON=jdump(th, compact=True))

def selfcheck(dest, tmp):
    print(f"自检：selfcheck.sh --project {dest} --no-voice", flush=True)
    args = ["bash", str(SK / "scripts" / "selfcheck.sh"), "--project", str(dest), "--no-voice"] + (["--tmp", str(tmp)] if tmp else [])
    return subprocess.run(args).returncode

def eras_js(pj, title, fps):
    film, libs = pj["film"], efconfig.scene_libs(pj)
    return (f"// {title}（?film={film}）。脚手架最小版，由 scripts/new_project.py 生成；写好 timeline 后由 make_timing.py 覆盖，勿手改。\n"
            f"window.PUNCH = 0;\nwindow.FPS_HINT = {fps};\nwindow.SCENE_LIBS = {json.dumps(libs)};\n"
            f"window.SCENE_DIR = '{film}/scenes';\nwindow.EXTRA_ASSETS = {json.dumps(efconfig.extra_assets(pj), ensure_ascii=False)};\n"
            'window.ERAS = ["B0"].map(id => ({ id, get dur() { return TIMING.seg[id].dur; } }));\n')

def rewrite_eras(text, pj):
    """把已有 eras 文件的 SCENE_LIBS、EXTRA_ASSETS 两行按 pj 重写（写法同 make_timing.py），其余行原样。"""
    libs = ", ".join("'" + x.replace("\\", "\\\\").replace("'", "\\'") + "'" for x in efconfig.scene_libs(pj))   # 单引号串：先转义 \ 与 '（普通路径逐字节不变）
    for key, val in (("SCENE_LIBS", f"[{libs}]"), ("EXTRA_ASSETS", json.dumps(efconfig.extra_assets(pj), ensure_ascii=False))):
        text, n = re.subn(rf"^window\.{key} = .*;$", lambda m, k=key, v=val: f"window.{k} = {v};", text, flags=re.M)
        if n != 1:
            raise Fail(f"eras 文件里 window.{key} 行有 {n} 处（应恰好 1 处），不认识它的格式")
    return text

def load_style(sid):
    """读画法包 templates/styles/<sid>/：返回 (目录, style.json)；缺文件、缺字段、类型不对即 Fail（不写任何东西）。"""
    if not isinstance(sid, str) or not re.match(r"^[a-z0-9_]+$", sid):
        raise Fail(f"画法 id 须为 ^[a-z0-9_]+$：{sid!r}")
    d = STYLES / sid
    if not (d / "style.json").is_file() or not (d / "style.js").is_file():
        raise Fail(f"没有画法 {sid}（{tilde(d)}/ 下要有 style.json 与 style.js）；--list-styles 列出全部画法")
    try:
        sj = json.loads((d / "style.json").read_text(encoding="utf-8"))
    except ValueError as e:
        raise Fail(f"{tilde(d / 'style.json')} 不是合法 JSON：{e}")
    miss = [k for k in STYLE_KEYS if k not in sj] if isinstance(sj, dict) else list(STYLE_KEYS)
    if miss:
        raise Fail(f"{tilde(d / 'style.json')} 缺字段：{miss}")
    strs = lambda v: isinstance(v, list) and all(isinstance(x, str) and x for x in v)  # noqa: E731
    bad = [k for k in ("id", "label", "summary", "fits", "avoid") if not (isinstance(sj[k], str) and sj[k].strip())]
    bad += [] if sj["id"] == sid else ["id（与目录名不同）"]
    bad += [] if strs(sj["signature"]) and 5 <= len(sj["signature"]) <= 8 else ["signature（5–8 条字符串）"]
    bad += [k for k in ("theme", "qa") if not isinstance(sj[k], dict)]
    bad += [k for k in ("extra_colors", "required_fonts", "assets") if not strs(sj[k])]
    bad += [f"assets:{x}" for x in (sj["assets"] if strs(sj["assets"]) else []) if Path(x).is_absolute() or ".." in Path(x).parts]
    if bad:
        raise Fail(f"{tilde(d / 'style.json')} 字段不合法：{bad}")
    return d, sj

def style_theme(sj):
    """画法默认主题：模板主题逐键叠 style.json 的 theme（嵌套对象逐子键），required_fonts 取并集，extra_colors 非空才写进主题。"""
    th = json.loads((TPL / "project.json").read_text(encoding="utf-8"))["theme"]
    for k, v in sj["theme"].items():
        th[k] = dict(th[k], **v) if isinstance(v, dict) and isinstance(th.get(k), dict) else copy.deepcopy(v)
    rf = list(th.get("required_fonts") or [])
    th["required_fonts"] = rf + [f for f in sj["required_fonts"] if f not in rf]
    if sj["extra_colors"]:
        th["extra_colors"] = list(sj["extra_colors"])
    return th

def list_styles():
    rows = []
    for d in sorted(STYLES.iterdir()) if STYLES.is_dir() else []:
        if d.is_dir() and (d / "style.json").is_file():
            try:
                rows.append(load_style(d.name)[1])
            except Fail as e:
                print(f"{d.name}\t（画法包不合法：{e}）")
    for s in sorted(rows, key=lambda s: (s["id"] != "whiteboard", s["id"])):
        print(f"{s['id']}\t{s['label']}\t{s['summary']}\t适合：{s['fits']}")
    return 0

def create(a):
    film, title = a.film, (a.title or "").strip()
    if not film or not re.match(r"^[a-z0-9_]+$", film) or film in RESERVED:
        raise Fail(f"--film 须为 ^[a-z0-9_]+$ 且不能是 {sorted(RESERVED)}：{film!r}")
    if not title or any(c in title for c in "/\\\n\r\t"):
        raise Fail("--title 不能为空，也不能含 / \\ 换行与制表符")
    dest = norm(a.dest)
    if dest.is_symlink() or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))):
        raise Fail(f"--dest 已存在且非空（或不是目录）：{dest}，拒绝创建，未改动任何文件")
    if dest.resolve() == SK or SK in dest.resolve().parents:
        raise Fail("--dest 不能放在 skill 目录里")
    pj = json.loads((TPL / "project.json").read_text(encoding="utf-8"))
    sdir, sj = load_style(a.style)   # 画法包不合法即拒绝（还没写任何东西）
    out = norm(a.out_root) if a.out_root else Path.home() / "Movies" / "讲解视频" / dest.name
    pj.update(film=film, slug=a.slug or film, title=title, version=a.version, deliverable_name=f"样片-{title}-{a.version}", out_root=tilde(out))
    pj["vendor"]["path"] = tilde(SK / "vendor")
    pj.update(style=sj["id"], assets=list(sj["assets"]), theme=style_theme(sj))
    pj["libs"] = [f"{film}/wb/parts.js"] + (THREE_LIBS(film) if a.three else [])   # 通用件（templates/parts.js 的副本），排在 SCENE_LIBS 最后；--three 再接三维库与三维件
    th, cv = pj["theme"], pj["canvas"]
    existed, made_out = dest.exists(), []
    try:
        mkdirs(dest.parent, made_out)
        dest.mkdir(exist_ok=True)
        eng, fdir = dest / "engine", dest / "engine" / film
        for d in (eng, fdir / "wb", fdir / "scenes", dest / "tools"):
            d.mkdir(parents=True, exist_ok=True)
        for n in ROOT_FILES:
            shutil.copy2(VENG / n, eng / n)
        for d in LINK_DIRS:
            if a.copy_engine:
                shutil.copytree(VENG / d, eng / d, symlinks=False)
            else:
                os.symlink(VENG / d, eng / d)
        (eng / "VENDOR.md").write_text(f"# 引擎来源（new_project.py 生成）\n\n根目录 13 个文件复制自 `{tilde(VENG)}/`（huashu-art-motion {pj['vendor']['commit']}，MIT，零改动）；"
                                       f"{'、'.join(LINK_DIRS)} 8 个目录{'整份复制' if a.copy_engine else '软链'}到同处。本片自己的文件只在 `eras_{film}.js` 与 `{film}/`。"
                                       f"软链失效跑 `new_project.py --dest <项目> --relink`；来源与许可见 `{tilde(SK / 'vendor/VENDOR.md')}`。\n", encoding="utf-8")
        timing = {"total": 3, "seg": {"B0": {"text": title, "dur": 3, "t0": 0, "voStart": 0, "voEnd": 0, "charStart": [0] * len(title),
                  "charEnd": [0] * len(title), "match": 1.0, "lines": [], "captions": []}}, "beats": {}, "cues": {}, "events": {}, "motion": MOTION,
                  "meta": {"engine": None, "voice_fp": None, "provisional": True, "cues_file": None, "scaffold": True}}
        (fdir / "timing.js").write_text(fill("timing_min.js", TIMING_JSON=jdump(timing, compact=True)), encoding="utf-8")
        (fdir / "theme.js").write_text(theme_js(th), encoding="utf-8")
        shutil.copy2(TPL / "tmb.js", fdir / "tmb.js")
        shutil.copy2(TPL / "common.js", fdir / "wb" / "common.js")
        shutil.copy2(sdir / "style.js", fdir / "wb" / "style.js")
        shutil.copy2(TPL / "parts.js", fdir / "wb" / "parts.js")
        a.three and shutil.copy2(TPL / "three.js", fdir / "wb" / "three.js")
        for x in sj["assets"]:   # 画法包自带的图片（相对 engine/<F>/）
            (fdir / x).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sdir / x, fdir / x)
        (fdir / "wb" / "strokes.js").write_text("// 笔顺数据：make_strokes.py 按全片用字重抽；空表时汉字按之字形揭开（不报错）。\nwindow.WB_STROKES = {};\n", encoding="utf-8")
        (fdir / "scenes" / "B0.js").write_text(fill("scene_min.js", TITLE_JSON=jdump(title, compact=True)), encoding="utf-8")
        (eng / f"eras_{film}.js").write_text(eras_js(pj, title, cv["fps"]), encoding="utf-8")
        tl = {"title": title, "version": a.version, "fps": cv["fps"], "width": cv["width"], "height": cv["height"], "source": {"file": None, "lines": None},
              "world": {"w": th["world"]["w"], "h": th["world"]["h"], "caption_band": th["caption"]["band"], "rows": th["rows"]}, "motion": MOTION,
              "voice": {"engines": ["elevenlabs"], "approval_file": "audio/approved_voice.json"},
              "scenes": [{"id": "B0", "kind": "title", "hold_secs": 3, "beats": [
                  {"k": 1, "n": 1, "say": title, "tts": title, "cues": [{"id": "B0_01", "text": title}], "events": [], "look": "字卡"}]}]}
        (dest / "timeline.json").write_text(jdump(tl), encoding="utf-8")
        ov = json.loads((TPL / "tts_overrides.json").read_text(encoding="utf-8"))
        (dest / "tools" / "tts_overrides.json").write_text(jdump({"_说明": ov.get("_说明", ""), "whole_beats": {}}), encoding="utf-8")
        qc = json.loads((TPL / "qa_config.json").read_text(encoding="utf-8"))   # 模板带样片的标定值与死帧处：标定值沿用但记未标定，死帧处清空
        qc.pop("note", None)
        qc.update(calibrated=False, source="沿用 skill 模板的标定值（来自样片的认可草稿）；本项目草稿认可后按事件差值分布重新标定")
        qc.setdefault("still_flagged", {}).update(spots=[], source="本项目审片后按 [节拍, 字] 锚点登记")
        for k, v in sj["qa"].items():   # 画法包的 qa 缺省项（如 still_video_source）
            qc[k] = dict(qc[k], **v) if isinstance(v, dict) and isinstance(qc.get(k), dict) else copy.deepcopy(v)
        (dest / "tools" / "qa_config.json").write_text(jdump(qc), encoding="utf-8")
        for n in ("redlines.txt", "redlines-names.txt"):
            shutil.copy2(TPL / n, dest / "tools" / n)
        (dest / "脚本与分镜.md").write_text(fill("脚本与分镜.md", TITLE=title, VERSION=a.version, FILM=film), encoding="utf-8")
        (dest / "CREDITS.md").write_text(fill("CREDITS.md", TITLE=title, FILM=film), encoding="utf-8")
        (dest / "存根-产物位置.md").write_text(fill("存根-产物位置.md", OUT_ROOT=tilde(out) + "/", DELIVERABLE=pj["deliverable_name"]), encoding="utf-8")
        (dest / ".gitignore").write_text(fill("gitignore", FILM=film), encoding="utf-8")
        (dest / "project.json").write_text(jdump(pj), encoding="utf-8")
        for sub in ("audio", "review", "out"):
            mkdirs(out / sub, made_out)
        if selfcheck(dest, a.tmp) != 0:
            raise Fail("自检不过")
    except BaseException as e:
        for c in ([dest] if not existed else list(dest.iterdir())):   # 原来就有的空目录只清里面（里面全是本次建的）
            if c.is_symlink() or c.is_file():
                c.unlink()
            elif c.is_dir():
                shutil.rmtree(c, ignore_errors=True)
        for q in reversed(made_out):   # 本次新建的上级目录与产物目录：只删仍为空的
            q.exists() and not any(q.iterdir()) and q.rmdir()
        if isinstance(e, Exception):
            raise Fail(f"{e if isinstance(e, Fail) else repr(e)}；已删掉本次新建的 {dest}{'' if not existed else ' 里的内容'}，以及本次新建且仍为空的上级目录与产物目录")
        raise
    print(f"项目已建：{dest}\n  片名 {film}、画法 {sj['id']}（{sj['label']}）、产物根 {tilde(out)}/、project.json schema {pj['schema']}"
          + ("\n  带三维可选件：wb/three.js、libs 含 lib/three.min.js（用法见 references/three.md）" if a.three else ""))
    return 0

def load_pj(dest):
    p = norm(dest) / "project.json"
    if not p.is_file():
        raise Fail(f"{p} 不存在（--relink／--theme 只用于已有项目）")
    return p.parent, json.loads(p.read_text(encoding="utf-8"))

def relink(a):
    dest, pj = load_pj(a.dest)
    eng = dest / "engine"
    real = [d for d in LINK_DIRS if (eng / d).exists() and not (eng / d).is_symlink()]
    if real:
        raise Fail(f"engine/ 下这些是真目录（--copy-engine 项目？），--relink 不碰：{real}")
    saved = {d: os.readlink(eng / d) if (eng / d).is_symlink() else None for d in LINK_DIRS}

    def put(d, target):
        tmp = eng / f".{d}.lnk-{os.getpid()}"
        os.symlink(target, tmp)
        os.replace(tmp, eng / d)
    for d in LINK_DIRS:
        put(d, VENG / d)
    if selfcheck(dest, a.tmp) != 0:
        for d, old in saved.items():
            (eng / d).unlink() if old is None else put(d, old)
        raise Fail("--relink 后自检不过，已还原原软链")
    print(f"软链已重建（{len(LINK_DIRS)} 个 → {tilde(VENG)}/）")

def retheme(a):
    dest, pj = load_pj(a.dest)
    film = pj.get("film") or ""
    if not re.match(r"^[a-z0-9_]+$", film) or film in RESERVED or (dest / "engine" / film).is_symlink():
        raise Fail(f"project.json 的 film 不合法或 engine/{film} 是软链：{film!r}")
    path = dest / "engine" / film / "theme.js"
    new = theme_js(pj.get("theme"))   # 不合法即抛错，文件未动
    sty = None
    if "style" in pj:   # 新格式工程：同时按 style 键重拷画法包的 style.js
        sty = (load_style(pj["style"])[0] / "style.js", dest / "engine" / film / "wb" / "style.js")
    olds = [(p, p.read_bytes() if p.exists() else None) for p in [path] + ([sty[1]] if sty else [])]
    atomic_write(path, new)
    sty and atomic_write(sty[1], sty[0].read_bytes())
    if selfcheck(dest, a.tmp) != 0:
        for p, old in olds:
            p.unlink(missing_ok=True) if old is None else atomic_write(p, old)
        raise Fail("--theme 后自检不过，已还原原 theme.js" + ("与 wb/style.js" if sty else ""))
    print(f"主题已重写：{path}" + (f"；style.js 已按画法 {pj['style']} 重拷" if sty else ""))

def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# 换画法自检（用项目 python 跑，代码从 stdin 传入）：engine/ 起只读本地服务，无头开 index.html?render=1&film=<F>，等 __ready（或 __bootFailed），
# 对 0…__total 每 0.25 s、外加每段（ERAS）的起点与中点逐时刻 prepare＋renderFrame（不截图）；收集 __bootFailed、pageerror、console.error 与逐帧异常。
CHECK_JS = """async () => { const T = window.__total, ts = [], out = [];
  for (let k = 0; k * 0.25 <= T + 1e-9; k++) ts.push(k * 0.25);
  for (const e of ERAS) { const a = e.t0, z = Math.min(e.t1, T); ts.push(a, (a + z) / 2); }
  for (const t of ts) { try { await window.prepare(t); window.renderFrame(t); }
    catch (err) { out.push('t=' + t.toFixed(3) + ' ' + String(err && err.stack || err)); if (out.length >= 5) break; } }
  return { n: ts.length, frame_errors: out }; }"""
CHECK_PY = """
import functools, http.server, json, socketserver, sys, threading
from playwright.sync_api import sync_playwright
eng, film, js = sys.argv[1], sys.argv[2], sys.argv[3]
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
class Srv(socketserver.ThreadingTCPServer):
    daemon_threads, request_queue_size = True, 128
srv = Srv(("127.0.0.1", 0), functools.partial(Q, directory=eng))
threading.Thread(target=srv.serve_forever, daemon=True).start()
errs, res = [], {"boot": None, "n": 0, "frame_errors": []}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append("console.error: " + m.text) if m.type == "error" else None)
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html?render=1&film={film}")
        pg.wait_for_function("window.__ready === true || !!window.__bootFailed", timeout=120000)
        res["boot"] = pg.evaluate("window.__bootFailed || null")
        if not res["boot"]:
            res.update(pg.evaluate(js))
        b.close()
finally:
    srv.shutdown(); srv.server_close()
res["page_errors"] = errs[:5]
print(json.dumps(res, ensure_ascii=False))
sys.exit(0 if not res["boot"] and not res["frame_errors"] and not errs else 1)
"""

def render_check(dest, pj):
    """换画法后的全片自检：逐 0.25 s 与各段起点、中点 renderFrame（不截图、不写字节码）；无启动失败、无页面错误、无逐帧异常返回 None，否则返回原因。"""
    film, eng = pj["film"], dest / "engine"
    r = subprocess.run([os.path.expanduser(pj.get("python") or sys.executable), "-I", "-B", "-", str(eng), film, CHECK_JS], input=CHECK_PY, cwd=tempfile.gettempdir(),
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return f"自检脚本没跑起来（退出 {r.returncode}）：{(r.stdout + r.stderr).strip()[-700:]}"
    if r.returncode != 0:
        if res.get("boot"):
            return f"全片自检不过（引擎启动失败）：{str(res['boot'])[:900]}"
        why = "；".join(res.get("frame_errors", []) + res.get("page_errors", []))
        return f"全片自检不过（逐 0.25 s＋各段起点、中点共 {res.get('n', 0)} 个时刻）：{why[:900]}"
    print(f"自检：全片 {res['n']} 个时刻 renderFrame 无页面错误", flush=True)
    return None

def restyle(a):
    dest, pj = load_pj(a.dest)
    if "style" not in pj:
        raise Fail("老工程（project.json 没有 style 键）不能 --restyle，未改动任何文件。老工程请用 --style 新建工程，再复制 timeline.json、脚本与分镜、tools/")
    film = pj.get("film") or ""
    if not re.match(r"^[a-z0-9_]+$", film) or film in RESERVED or (dest / "engine" / film).is_symlink():
        raise Fail(f"project.json 的 film 不合法或 engine/{film} 是软链：{film!r}")
    sdir, sj = load_style(a.restyle)
    try:
        drop = set(load_style(pj["style"])[1]["assets"])   # 旧画法包自带的图片从 assets 里剔掉（文件留着）
    except Fail:
        drop = set()
    eng, fd = dest / "engine", dest / "engine" / film
    eras = eng / f"eras_{film}.js"
    if not eras.is_file():
        raise Fail(f"缺 {eras}")
    keep = [x for x in (pj.get("assets") or []) if x not in drop]
    npj = copy.deepcopy(pj)
    npj.update(style=sj["id"], theme=style_theme(sj), assets=keep + [x for x in sj["assets"] if x not in keep])
    theme_text, eras_text = theme_js(npj["theme"]), rewrite_eras(eras.read_text(encoding="utf-8"), npj)   # 都先算好：不合法即 Fail，还没写
    pairs = [(sdir / x, fd / x) for x in sj["assets"]]
    miss = [str(s) for s, _ in pairs if not s.is_file()]
    if miss:
        raise Fail(f"画法包缺图片：{miss}")
    targets = [dest / "project.json", fd / "theme.js", fd / "wb" / "common.js", fd / "wb" / "style.js", eras] + [d for _, d in pairs]
    bak = dest / f".restyle-bak-{int(time.time())}"
    if bak.exists():
        raise Fail(f"{bak} 已存在，过一秒再试")
    existed = {p: p.exists() for p in targets}   # 执行前在不在（与备份成没成分开记）
    baks, bak_made = {}, False
    try:   # 备份阶段：在动任何工程文件之前做完；任何失败 → 只删本次建的备份目录，工程零改动
        bak.mkdir()
        bak_made = True
        for p in targets:
            if existed[p]:
                b = bak / p.relative_to(dest)
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, b)
                if _sha(b) != _sha(p):
                    raise OSError(f"备份核对不符：{p}")
                baks[p] = b
    except BaseException as e:
        bak_made and shutil.rmtree(bak, ignore_errors=True)
        if not isinstance(e, Exception):
            raise
        raise Fail(f"--restyle {sj['id']} 备份阶段失败，工程未改动：{e!r}")
    created, made = [], []

    def put(p, data):   # 写一个目标文件；执行前不存在的记进 created（回滚时只删这些）
        atomic_write(p, data)
        existed[p] or created.append(p)
    try:
        put(dest / "project.json", jdump(npj))
        put(fd / "theme.js", theme_text)
        put(fd / "wb" / "common.js", (TPL / "common.js").read_bytes())
        put(fd / "wb" / "style.js", (sdir / "style.js").read_bytes())
        put(eras, eras_text)
        for s, d in pairs:
            mkdirs(d.parent, made)
            put(d, s.read_bytes())
        why = render_check(dest, npj)
        if why:
            raise Fail(why)
    except BaseException as e:
        left = []
        for p, b in baks.items():   # 整体拷回；拷回后逐个核 sha256
            try:
                shutil.copy2(b, p)
                _sha(p) == _sha(b) or left.append(str(p))
            except OSError as err:
                left.append(f"{p}：{err}")
        for p in created:   # 只删确认「执行前不存在、由本次新建」的文件
            try:
                p.unlink(missing_ok=True)
            except OSError as err:
                left.append(f"{p}：{err}")
        for q in reversed(made):
            q.exists() and not any(q.iterdir()) and q.rmdir()
        left or shutil.rmtree(bak, ignore_errors=True)
        if not isinstance(e, Exception):
            raise
        raise Fail(f"--restyle {sj['id']} 失败：{e if isinstance(e, Fail) else repr(e)}；"
                   + (f"回滚没做完（{left}），备份留在 {bak}" if left else "已把备份整体拷回、工程恢复原样（常见原因：场景用了旧画法的专用件）"))
    print(f"画法已换成 {sj['id']}（{sj['label']}），theme 重置为该画法默认；备份在 {bak}")

def _eras_has(text, pj):
    """eras 文件的 SCENE_LIBS、EXTRA_ASSETS 两行按值（不论单双引号）已与 pj 一致：True。脚手架写双引号、make_timing／rewrite_eras 写单引号，只差引号不算要改。"""
    def val(key):
        m = re.search(rf"^window\.{key} = (.*);$", text, flags=re.M)
        try:
            return ast.literal_eval(m.group(1)) if m else None
        except (ValueError, SyntaxError):
            return None
    return val("SCENE_LIBS") == efconfig.scene_libs(pj) and val("EXTRA_ASSETS") == efconfig.extra_assets(pj)

def add_three(a):
    """--dest D --add-three：给已有新格式工程补上三维可选件（事务写法同 restyle：写前校验 → 备份并核对 → 执行，失败整体拷回）。"""
    dest, pj = load_pj(a.dest)
    if "style" not in pj:
        raise Fail("老工程（project.json 没有 style 键）不能 --add-three，未改动任何文件。老工程请用 --style 新建工程（可带 --three），再复制 timeline.json、脚本与分镜、tools/")
    film = pj.get("film") or ""
    if not re.match(r"^[a-z0-9_]+$", film) or film in RESERVED or (dest / "engine" / film).is_symlink():
        raise Fail(f"project.json 的 film 不合法或 engine/{film} 是软链：{film!r}")
    eng, fd = dest / "engine", dest / "engine" / film
    eras = eng / f"eras_{film}.js"
    if not eras.is_file():
        raise Fail(f"缺 {eras}")
    libs = pj.get("libs")
    if libs is not None and not (isinstance(libs, list) and all(isinstance(x, str) and x for x in libs)):
        raise Fail(f"project.json 的 libs 不是字符串列表，未改动任何文件：{libs!r}")
    npj = copy.deepcopy(pj)
    npj["libs"] = list(libs or []) + [x for x in THREE_LIBS(film) if x not in (libs or [])]   # 末尾补上缺的项
    eras_old = eras.read_text(encoding="utf-8")
    eras_text = rewrite_eras(eras_old, npj)   # 试跑：认不出格式即 Fail，还没写
    src, dst = TPL / "three.js", fd / "wb" / "three.js"
    tpl = src.read_bytes()
    if dst.is_symlink() or (dst.exists() and (not dst.is_file() or dst.read_bytes() != tpl)):
        raise Fail(f"工程里的 three.js 改过（与 skill 的 {tilde(src)} 字节不同），手动合并，未改动任何文件：{dst}")
    todo = [(dest / "project.json", jdump(npj))] if npj["libs"] != libs else []
    todo += [] if dst.is_file() else [(dst, tpl)]
    todo += [] if _eras_has(eras_old, npj) else [(eras, eras_text)]
    if not todo:
        print(f"已带三维：libs 已含 {THREE_LIBS(film)}、wb/three.js 与模板相同、eras 已一致，未改动任何文件")
        return
    targets = [dest / "project.json", eras, dst]
    bak = dest / f".add-three-bak-{int(time.time())}"
    if bak.exists():
        raise Fail(f"{bak} 已存在，过一秒再试")
    existed = {p: p.exists() for p in targets}   # 执行前在不在（与备份成没成分开记）
    baks, bak_made = {}, False
    try:   # 备份阶段：在动任何工程文件之前做完；任何失败 → 只删本次建的备份目录，工程零改动
        bak.mkdir()
        bak_made = True
        for p in targets:
            if existed[p]:
                b = bak / p.relative_to(dest)
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, b)
                if _sha(b) != _sha(p):
                    raise OSError(f"备份核对不符：{p}")
                baks[p] = b
    except BaseException as e:
        bak_made and shutil.rmtree(bak, ignore_errors=True)
        if not isinstance(e, Exception):
            raise
        raise Fail(f"--add-three 备份阶段失败，工程未改动：{e!r}")
    created = []
    try:
        for p, data in todo:   # 顺序：project.json（libs）→ wb/three.js → eras
            atomic_write(p, data)
            existed[p] or created.append(p)
    except BaseException as e:
        left = []
        for p, b in baks.items():   # 整体拷回；拷回后逐个核 sha256
            try:
                shutil.copy2(b, p)
                _sha(p) == _sha(b) or left.append(str(p))
            except OSError as err:
                left.append(f"{p}：{err}")
        for p in created:   # 只删确认「执行前不存在、由本次新建」的文件
            try:
                p.unlink(missing_ok=True)
            except OSError as err:
                left.append(f"{p}：{err}")
        left or shutil.rmtree(bak, ignore_errors=True)
        if not isinstance(e, Exception):
            raise
        raise Fail(f"--add-three 失败：{e if isinstance(e, Fail) else repr(e)}；"
                   + (f"回滚没做完（{left}），备份留在 {bak}" if left else "已把备份整体拷回、工程恢复原样"))
    print(f"已带上三维：libs＝{npj['libs']}、wb/three.js 已就位、eras 的 SCENE_LIBS 已重写（用法见 references/three.md）；备份在 {bak}")

def write_manifest():
    root = SK / "vendor"
    mp = root / "vendor_manifest.json"
    old_text = mp.read_text(encoding="utf-8") if mp.exists() else ""
    files = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for f in fns:
            p = Path(dp) / f
            if p.is_symlink():
                raise Fail(f"vendor 里不该有软链：{p}")
            if p != mp and f != ".DS_Store":
                files[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    commit = json.loads(old_text).get("commit", "8a0d7d72") if old_text else "8a0d7d72"
    text = json.dumps({"commit": commit, "files": dict(sorted(files.items())), "n": len(files), "root": "vendor"}, ensure_ascii=False, indent=1)
    if text != old_text:
        atomic_write(mp, text)
    print(f"vendor_manifest.json {'无变化' if text == old_text else '已重写'}（{len(files)} 个文件）")
    return 0

def main():
    ap = argparse.ArgumentParser(description="explainer-film 脚手架：建项目／重建软链／重写主题／换画法／加三维／列画法／重算 vendor 清单")
    for k, h in (("--dest", None), ("--film", None), ("--title", None), ("--slug", "TTS 缓存名，缺省＝片名"), ("--out-root", "产物根，缺省 ~/Movies/讲解视频/<项目目录名>/"),
                 ("--tmp", "自检出帧与日志放这里（缺省临时目录，全过即删）")):
        ap.add_argument(k, help=h)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--style", default="whiteboard", help="建项目用的画法 id（templates/styles/<id>/），缺省 whiteboard")
    ap.add_argument("--restyle", help="新格式工程换画法：--dest D --restyle <id>")
    for k in ("--copy-engine", "--relink", "--theme", "--write-manifest", "--list-styles"):
        ap.add_argument(k, action="store_true")
    ap.add_argument("--three", action="store_true", help="建项目时带上三维可选件（wb/three.js＋lib/three.min.js，见 references/three.md）")
    ap.add_argument("--add-three", action="store_true", help="已有新格式工程补上三维可选件：--dest D --add-three")
    a = ap.parse_args()
    try:
        if a.write_manifest:
            return write_manifest()
        if a.list_styles:
            return list_styles()
        if not a.dest:
            raise Fail("要 --dest")
        if a.add_three:
            if a.restyle or a.relink or a.theme or a.three:
                raise Fail("--add-three 不和 --restyle／--relink／--theme／--three 同用")
            add_three(a)
            return 0
        if a.three and (a.restyle or a.relink or a.theme):
            raise Fail("--three 只用于建项目；已有工程用 --dest D --add-three")
        if a.restyle:
            if a.relink or a.theme:
                raise Fail("--restyle 不和 --relink／--theme 同用")
            restyle(a)
            return 0
        if a.relink or a.theme:
            a.relink and relink(a)
            a.theme and retheme(a)
            return 0
        if not (a.film and a.title):
            raise Fail("建项目要 --film 与 --title")
        return create(a)
    except Fail as e:
        print(f"new_project: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
