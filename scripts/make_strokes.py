#!/usr/bin/env python3
"""按全片实际上板的字重抽笔顺中线 → engine/<片名>/wb/strokes.js。

做法：先确保 strokes.js 存在（没有就写空表，页面才能启动），用 render.py 同一套方式起本地服务、无头 Chromium
打开 index.html?film=<片名>，等 __ready 后读 WB.texts（WB.text / WB.pop / 场景手动登记的全部上板字符串），
取其中的汉字，到 hanzi-writer-data（Make Me a Hanzi 衍生，Arphic 公共许可）逐字读 <字>.json 的 medians，
写成 window.WB_STROKES = {字: [[[x,y],…],…]}（1024 格，y 朝上，顶边 900，与参考片 strokes.js 同格式）。
抽不到的汉字和非汉字字符（拉丁字母、标点；数字有手写中线不算）在页面里退化为之字形揭开，这里只报清单。

用法：make_strokes.py [--project P] [--data-dir <hanzi-writer-data 包目录>] [--out engine/<片名>/wb/strokes.js] [--report <json>]
      --data-dir 缺省 ~/.cache/explainer-film/hwd/package（没有就从 skill 的 vendor/hanzi-writer-data-2.0.1.tgz 解到那里）。
退出码：0 成功（未命中字照样写出并报清单）；1 页面起不来或数据目录不对。
"""
import argparse
import functools
import http.server
import json
import shutil
import socketserver
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import efconfig  # noqa: E402

DATA_DEFAULT = Path.home() / ".cache/explainer-film/hwd/package"
HEADER = ("// 汉字笔顺中线（来源：hanzi-writer-data 2.0.1 / Make Me a Hanzi，Arphic 公共许可，见同目录 ARPHICPL.TXT）：\n"
          "// 只用来决定「按笔顺露出字」的路径，字形本身仍是 Songti SC / PingFang SC。由 tools/make_strokes.py 按全片上板用字生成，勿手改。\n")


def is_han(ch):
    o = ord(ch)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF


def drawn_texts(engine, film):
    """无头打开整片，读 WB.texts。"""
    from playwright.sync_api import sync_playwright

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x):
            pass

    class S(socketserver.ThreadingTCPServer):
        request_queue_size = 128
        daemon_threads = True

    srv = S(("127.0.0.1", 0), functools.partial(Q, directory=str(engine)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    errors = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html?render=1&film={film}")
            pg.wait_for_function("window.__ready === true || !!window.__bootFailed", timeout=120000)
            bf = pg.evaluate("window.__bootFailed || null")
            if bf:
                raise SystemExit("页面起不来：\n" + bf)
            texts = pg.evaluate("WB.texts.slice()")
            b.close()
    finally:
        srv.shutdown()
        srv.server_close()
    if errors:
        print("页面报错（不影响抽字）：" + "；".join(errors[:3]), file=sys.stderr)
    return texts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--data-dir", help="hanzi-writer-data 包目录（含 <字>.json）")
    ap.add_argument("--out")
    ap.add_argument("--report", default="", help="未命中清单写成 json（可选）")
    a = ap.parse_args()
    cfg = efconfig.load(a.project)
    engine = cfg.project_dir / "engine"
    data = Path(a.data_dir).expanduser() if a.data_dir else DATA_DEFAULT
    if not a.data_dir and not (data / "年.json").exists():
        import tarfile
        with tarfile.open(cfg.skill_dir / "vendor" / "hanzi-writer-data-2.0.1.tgz") as tf:
            tf.extractall(data.parent, filter="data")
    if not (data / "年.json").exists():
        print(f"数据目录不对：{data} 里没有 年.json", file=sys.stderr)
        return 1
    out = Path(a.out) if a.out else engine / cfg.film / "wb" / "strokes.js"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(HEADER + "window.WB_STROKES = {};\n", encoding="utf-8")
    texts = drawn_texts(engine, cfg.film)
    chars = sorted({ch for s in texts for ch in s})
    han = [ch for ch in chars if is_han(ch)]
    table, miss = {}, []
    for ch in han:
        f = data / f"{ch}.json"
        if not f.exists():
            miss.append(ch)
            continue
        table[ch] = json.loads(f.read_text(encoding="utf-8"))["medians"]
    other = [ch for ch in chars if not is_han(ch) and not ch.isspace() and not ch.isdigit()]
    out.write_text(HEADER + "window.WB_STROKES = " + json.dumps(table, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    lic = data / "ARPHICPL.TXT"
    if lic.exists():
        shutil.copyfile(lic, out.parent / "ARPHICPL.TXT")
    rep = {"strings": len(texts), "chars": len(chars), "han": len(han), "han_hit": len(table),
           "han_miss": miss, "zigzag_non_han": other}
    print(f"上板字符串 {len(texts)} 条，字符 {len(chars)} 个，汉字 {len(han)} 个，抽到 {len(table)} 个；"
          f"未命中汉字 {len(miss)} 个：{''.join(miss) or '无'}；之字形揭开的非汉字 {len(other)} 个：{''.join(other)}")
    print(f"写出 {out}（{out.stat().st_size / 1024:.0f} KB）")
    if a.report:
        Path(a.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
