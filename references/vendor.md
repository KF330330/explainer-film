# 引擎来源、零改动纪律与升级

> 何时读：只在要升级引擎、核对「零改动」或引擎跑不起来时。

- 来源：`alchaincyf/huashu-art-motion`，commit `8a0d7d72`，MIT（字体 OFL；笔顺 medians 来自 hanzi-writer-data 2.0.1，Arphic 许可 `ARPHICPL.TXT`）。细节见 `vendor/VENDOR.md`。
- `vendor/engine/`、`vendor/gates/` 零改动；`vendor/docs/` 是上游规则文档加我们写的接口速查（`接口速查.md` 只删过本机路径）。`vendor/vendor_manifest.json` 记 vendor 下每个文件的 sha256，`scripts/selfcheck.sh` 抽核；项目里的 `engine/` 是复制 13 个根文件＋软链 8 个大目录（`new_project.py`），我方文件只在 `engine/eras_<film>.js` 与 `engine/<film>/`。
- 升级：`git clone --depth 1 https://github.com/alchaincyf/huashu-art-motion` 到临时目录 → 对照 `VENDOR.md` 列的文件把 `scripts/engine/`、`scripts/{film_gate,qa,storyboard_lint,clip_lint}.py`、`references/*.md` 拷进新的 vendor 目录 → 跑参考片冒烟（`render.py --film wbx --stills 1,5`）并用一支旧片重渲几帧比对 → 改 `project.json.vendor.commit`、`python3 scripts/new_project.py --write-manifest` 重算清单、`new_project.py --dest <项目> --relink`。接口变了先改 `templates/common.js` 与 `references/scene-writing.md`。
- 引擎跑不起来的分诊：装配错误（路径、片名、缺文件、字体）修装配；`__bootErrors` 看缺哪个场景文件；每帧 >400 ms 或崩溃才是引擎问题。
