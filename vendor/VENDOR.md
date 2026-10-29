# 抄来的引擎（VENDOR）

- 来源：https://github.com/alchaincyf/huashu-art-motion ，分支 main，commit `8a0d7d72ca65fcce6f8ba82c4a6c8dfe35b8422c`（2026-10-22 取 codeload zip）。
- 复制范围：`scripts/engine/` 运行时（index.html、engine.js、scenes/index.js、render.py、spec_assets.py、audit_clip.py、transitions.js、clip.html/clip.js/clip_schema.json、clips/、lib/ 全部含 fonts/ 47 个字体、demos/t3_finance_chart、examples/*.json、eras.js）；白板参考片整套（eras_wbx.js 放 engine 根，spacex/、spacex_wb/、transitions/、README-参考片.md）；门禁脚本放 `gates/`（film_gate.py、qa.py、storyboard_lint.py、clip_lint.py）；规则文档放 `docs/`。
- 未复制：35 个艺术风格场景 `scenes/NN_*.js`、demos 大图与 long_scroll、examples/assets 图片、rick_morty、spacex_lin/spacex_vox 变体、角色帧库。
- 许可：代码与文档 MIT（engine/LICENSE 为原仓 LICENSE）；`lib/fonts/` 各字体 SIL OFL 1.1（见 lib/fonts/LICENSES.md、OFL.txt）；`spacex_wb/assets/strokes.js` 笔顺数据 Arphic Public License（同目录 ARPHICPL.TXT）；`spacex_wb/assets/hand_*.png` 为参考片素材，我们的片不加载。
- 我们对抄来文件的改动：**零**。我们自己的文件只在各项目的 `engine/eras_<片名>.js` 与 `engine/<片名>/`（由 `spacex_wb/common.js` 改出的白板库副本是 skill 的 `templates/common.js`，建项目时复制到 `engine/<片名>/wb/common.js`，原文件不动）。

## explainer-film 的 vendor 副本（2026-10-23 导入）
- `vendor/engine/`＝上述 huashu-art-motion 运行时（commit 8a0d7d72，MIT），**零改动**；去掉了原工程自己的 `b/`、`eras_b.js`。每个项目用 `scripts/new_project.py` 复制根文件＋软链大目录。
- `vendor/gates/`（film_gate/qa/storyboard_lint/clip_lint）同样零改动；`vendor/docs/`（上游规则文档＋我们写的接口速查）里只有 `接口速查.md` 删过一处本机路径。
- `vendor/hanzi-writer-data-2.0.1.tgz`：npm 包 hanzi-writer-data 2.0.1（medians，Arphic 许可 `ARPHICPL.TXT`），首次用时解到 `~/.cache/explainer-film/hwd/package/`。
- 上游仓库不随 skill 提供；要对照原文就从 `https://github.com/alchaincyf/huashu-art-motion` 取 commit 8a0d7d72。
- `vendor/vendor_manifest.json`：vendor 下每个文件的 sha256，`scripts/selfcheck.sh` 与验收用它核「零改动」。
