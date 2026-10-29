// 本片主题（色板、字体、笔速、版式行、字幕、纸纹）：由 scripts/new_project.py 按 project.json 的 theme 生成，勿手改。
// 改主题＝改 project.json 的 theme，再跑 new_project.py --dest <项目> --theme（先校验、写临时文件原子替换、出帧自检，失败即还原）。
// wb/common.js 开头 Object.assign(默认, window.WB_THEME) 读它；SCENE_LIBS 顺序固定 [timing, theme, tmb, strokes, common]。
window.WB_THEME = __THEME_JSON__;
