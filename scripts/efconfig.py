#!/usr/bin/env python3
"""explainer-film 项目配置（只用标准库）。全套脚本的两个根目录：
  SK＝skill 根，按本文件位置推导（scripts/ 的上一级），子脚本一律 SK/scripts/<名>；
  PROJ＝项目根，只由本模块决定：--project P ＞ 环境变量 EF_PROJECT ＞ 从 cwd 向上找 project.json，都没有就报错退出 2（P 可为目录或 project.json）。
库：cfg = efconfig.load([project])；cfg.project_dir / out_root / film / slug / skill_dir；cfg.get("timing.max_cue", 默认)；
    cfg.path("voice.elevenlabs.voice_id_file")（展开 ~、相对路径按项目根、null 给 None）；out_root：EF_OUT ＞ project.json ＞ ~/Movies/讲解视频/<项目目录名>/；
    scene_libs(cfg)／extra_assets(cfg)：eras 文件里 SCENE_LIBS、EXTRA_ASSETS 的单一来源（有 style 键＝新格式工程才加 wb/style.js 与图片；
    project.json 的 libs 键（相对 engine/ 的脚本路径表）原样按序追加在最后，无此键行为不变）。
命令行：python3 efconfig.py [--project P] get a.b.c（标量原样；布尔 true/false；null 空行；对象/数组 JSON）
        python3 efconfig.py [--project P] path a.b.c（同 cfg.path）；get 的 project_dir/skill_dir/out_root/film/slug 打解析后的值。
退出码：0 成功；1 键不存在；2 找不到项目或 project.json 不合法。
"""
import json, os, sys  # noqa: E401
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA = 1
_MISSING = object()

def _die(msg, code=2):
    print("efconfig: " + msg, file=sys.stderr)
    raise SystemExit(code)

def find_project(project=None):
    """返回项目根目录（含 project.json）；找不到退出 2。"""
    for src, val in (("--project", project), ("EF_PROJECT", os.environ.get("EF_PROJECT"))):
        if val:
            p = Path(val).expanduser().resolve()
            if p.name == "project.json" and p.is_file():
                p = p.parent
            if not (p / "project.json").is_file():
                _die(f"{src} 指向的 {p} 里没有 project.json")
            return p
    cur = Path.cwd().resolve()
    for d in [cur] + list(cur.parents):
        if (d / "project.json").is_file():
            return d
    _die("找不到项目：没给 --project、没设 EF_PROJECT，从当前目录向上也没有 project.json")

class Cfg:
    def __init__(self, project_dir, data):
        self.project_dir, self.data, self.skill_dir = Path(project_dir), data, SKILL_DIR

    def get(self, key, default=None):
        cur = self.data
        for part in key.split("."):
            if not (isinstance(cur, dict) and part in cur):
                return default
            cur = cur[part]
        return cur

    def _expand(self, val):
        p = Path(os.path.expanduser(str(val)))
        return p if p.is_absolute() else (self.project_dir / p)

    def path(self, key, default=None):
        val = self.get(key, default)
        return None if val is None else self._expand(val)

    @property
    def film(self):
        return self.data.get("film")

    @property
    def slug(self):
        return self.data.get("slug") or self.film

    @property
    def out_root(self):
        val = os.environ.get("EF_OUT") or self.data.get("out_root")
        return (self._expand(val) if val else Path.home() / "Movies" / "讲解视频" / self.project_dir.name).resolve()

def _data(cfg):
    return cfg.data if isinstance(cfg, Cfg) else cfg

def scene_libs(cfg):
    """window.SCENE_LIBS 的单一来源（new_project.py、make_timing.py 共用；cfg 为 Cfg 或 project.json 字典）。
    有 style 键的新格式工程在 wb/common.js 之后加 wb/style.js；无 style 键＝老工程，列表与加画法包之前逐项相同。
    project.json 有 libs 键（1.3.0 起；相对 engine/ 的路径，如 "<片名>/wb/parts.js"、"lib/three.min.js"）时，在上面列表之后原样按序追加；无此键不变。"""
    d = _data(cfg)
    libs = [f"{d['film']}/{x}" for x in ("timing.js", "theme.js", "tmb.js", "wb/strokes.js", "wb/common.js")]
    libs = libs + [f"{d['film']}/wb/style.js"] if "style" in d else libs
    return libs + list(d.get("libs") or [])

def extra_assets(cfg):
    """window.EXTRA_ASSETS：新格式工程＝project.json assets（相对 engine/<片名>/）加片名前缀；老工程恒为空。"""
    d = _data(cfg)
    return [f"{d['film']}/{a}" for a in (d.get("assets") or [])] if "style" in d else []

def load(project=None):
    d = find_project(project)
    try:
        data = json.loads((d / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _die(f"{d / 'project.json'} 读不了：{e}")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        _die(f"{d / 'project.json'} 的 schema 不是 {SCHEMA}")
    return Cfg(d, data)

def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (dict, list)) else str(v)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="读 explainer-film 项目的 project.json")
    ap.add_argument("--project", help="项目目录或 project.json 路径（缺省：EF_PROJECT，再缺省从 cwd 向上找）")
    ap.add_argument("op", choices=["get", "path"])
    ap.add_argument("key")
    a = ap.parse_args(argv)
    cfg = load(a.project)
    if a.op == "get" and a.key in ("project_dir", "skill_dir", "out_root", "film", "slug"):
        print(_fmt(getattr(cfg, a.key)))
        return 0
    v = cfg.get(a.key, _MISSING)
    if v is _MISSING:
        print(f"efconfig: project.json 里没有键 {a.key}", file=sys.stderr)
        return 1
    print(_fmt(cfg.path(a.key) if a.op == "path" else v))
    return 0

if __name__ == "__main__":
    sys.exit(main())
