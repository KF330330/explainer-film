// 三维可选件（explainer-film 1.3.1；1.3.2 加暗底配色与显存按最近使用释放）：WB.three 把一块 three.js 三维场景立在纸面上，外加配色、材质、相机、投影器、代理件与跟着三维点走的叠加件。
// 不并进 parts.js：new_project.py --three（建工程时）或 --dest <工程> --add-three（已有新格式工程）把本文件复制到 engine/<片名>/wb/three.js，
// project.json 的 libs 写 "lib/three.min.js"（vendor 自带 r160 UMD，挂 window.THREE）与 "<片名>/wb/three.js"，经 SCENE_LIBS 在各段场景之前加载。
// 签名、一例用法、硬事实与经验见 skill 的 references/three.md。
// 规矩：只在 WB 上挂新名字（WB.three 及其属性），不给 common.js 的引擎函数重新赋值；颜色只从 WB.C 令牌派生，字体只走 WB.BODY；不用无种子的随机数。
// 三维全程走浏览器默认的 WebGL（出片链里是软件渲染），不加任何显卡参数。整份包在一个函数里，不往全局放顶层名字。
//
// WB.three({box:[x0, y0, x1, y1], t0, until=null, el, px=1280, build(THREE, rng) → {scene, camera, update(tContent, tAmbient)}, nopen=true}) → 自定义件
//   box 是**两角坐标**（同 WB.frame），w＝x1−x0、h＝y1−y0；绘制范围与上报包围盒（静态 bb＝box）是同一矩形。
//   **全片共用一个 WebGLRenderer**（首个件建时建，WebGL 上下文恒为 1，与件数、章节数无关）：{antialias, alpha, preserveDrawingBuffer}、pixelRatio 1、
//   PCFSoft 软阴影、ACESFilmic 色调映射、输出 sRGB、清屏透明（纸面透出来，三维物件立在白板上；地面请用 ShadowMaterial 接阴影）。
//   每个件持有自己的 2D 缓存画布 px × round(px·h/w)；透视相机的宽高比由件设为 w/h。
//   draw(g, q, t)：t < t0 或 t ≥ until 不画；缓存按 (t, 装饰时刻 a＝WB.ambientT(t)) 认——本件缓存的不是这一对才依次 renderer.setSize(本件尺寸)
//   → update(t − t0, a − t0) → renderer.render → 清空缓存画布并把 GL 画布拷进来、记下 (t, a)（糊影时同一帧会以不同 t 调多次 draw，各 t 各渲一次；
//   同一 (t, a) 重复调用只渲一次；QA 在同一 t 换 WB.lockcam 时 a 变了，照样重渲；别的件渲染不冲掉本件缓存，除非本件因常驻数超过 keep 被释放——见下），然后 g.drawImage(缓存画布, x0, y0, w, h)。
//   update 必须是 (tContent, tAmbient) 的纯函数：不读 Date.now／performance、不用 mixer.update、不累积状态；随机只用 build 拿到的 rng（种子由 el 定）。
//   tContent 承载内容（房子升起、相机推街区）；tAmbient 只给装饰动作（相机 ±0.3° 摆动），QA 锁相机时冻结、render.sh --noambient 时为 −t0。
//   无 act、nopen 缺省 true：本件不算「笔在动」；要让门禁认三维里的内容块，每块另登记一个代理件（WB.three.proxy）。
//   返回的件多挂 .three = {THREE, scene, camera, renderer, canvas（本件的 2D 缓存画布）, box, w, h, pose(t), cache}（pose(t) 只摆姿势不渲；计时与投影用）。
//   renderer 是全片共用的那一个：场景里别改它的状态（尺寸、阴影、色调映射），改了会带到别的件。
//   显存按最近使用释放：真渲（缓存未命中）的件记为常驻、移到常驻表尾；渲完常驻数超过 WB.three.keep（缺省 4，须是 ≥1 的整数）就从表头释放最久没用的件
//   （几何、材质、材质上的贴图、scene.environment／background 贴图、灯的阴影图，2D 缓存画布宽高置 0、缓存置 NaN；CPU 侧场景图与贴图数据保留，不重跑 build）。
//   再渲到被释放的件时 three 自动重传、画面逐字节相同。同一帧要画的三维件多于 keep 会反复释放重传（画面照样对，只是慢）：keep 至少设成同屏最多的三维件数。
// WB.three.stats() → {parts 建过的件数, resident 常驻件数, evictions 累计释放次数, geometries, textures（后两项取共用渲染器的 info.memory，渲染器未建时为 0）}。
(() => {
const need = () => {
  if (!window.THREE || !window.THREE.WebGLRenderer)
    throw new Error('WB.three：THREE 没载入——project.json 的 libs 要有 "lib/three.min.js" 与 "<片名>/wb/three.js"；已有工程跑 new_project.py --dest <工程> --add-three');
  return window.THREE;
};
const seedOf = s => { let sd = 7; for (const ch of String(s)) sd = (sd * 31 + ch.charCodeAt(0)) >>> 0; return sd; };   // 同 WB.walker 的眨眼种子算法
let R = null;                                                                                      // 全片共用的渲染器（首个件建时建）
const shared = (THREE, cw, ch) => {
  if (R) return R;
  const canvas = document.createElement('canvas'); canvas.width = cw; canvas.height = ch;
  R = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  R.setPixelRatio(1); R.setSize(cw, ch, false);
  R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
  R.toneMapping = THREE.ACESFilmicToneMapping; R.outputColorSpace = THREE.SRGBColorSpace;
  R.setClearAlpha(0);                                                                              // 透明清屏：纸面透出来
  return R;
};
const live = [];                                                                                   // 常驻件（显存里有它的资源），按最近一次真渲排序，表头最久没用
let built = 0, evictions = 0;                                                                     // 建过的件数、累计释放次数
const keepOf = () => { const k = WB.three.keep;
  if (!(Number.isInteger(k) && k >= 1)) throw new Error(`WB.three.keep 要 ≥1 的整数（至少是同屏最多的三维件数）：${k}`);
  return k; };
// 释放一个件的显存：几何、材质（含数组）与材质上的贴图（含 ShaderMaterial 的 uniforms 贴图）、scene.environment／background 贴图、灯的阴影图；
// 贴图 dispose 时 three 一并释放由它生成的 PMREM 图。阴影图置 null 后 shadow.needsUpdate 置 true：灯设了 shadow.autoUpdate＝false（静态阴影）时，
// r160 碰到 needsUpdate 为 false 的灯会在重建阴影图之前就跳过，阴影建不回来。2D 缓存画布宽高置 0，缓存置 NaN（下一次 draw 必重渲）。CPU 侧场景图、DataTexture 数组都保留。
const release = o => {
  const tex = v => { if (v && v.isTexture) v.dispose(); };
  o.scene.traverse(n => {
    if (n.geometry && typeof n.geometry.dispose === 'function') n.geometry.dispose();
    for (const m of n.material ? (Array.isArray(n.material) ? n.material : [n.material]) : []) {
      for (const k of Object.keys(m)) tex(m[k]);
      if (m.uniforms) for (const u of Object.values(m.uniforms)) tex(u && u.value);
      m.dispose(); }
    if (n.shadow && n.shadow.map) { n.shadow.map.dispose(); n.shadow.map = null; n.shadow.needsUpdate = true; } });   // 静态阴影（autoUpdate＝false）也要重画
  tex(o.scene.environment); tex(o.scene.background);
  o.canvas.width = 0; o.canvas.height = 0; o.cache.t = NaN; o.cache.a = NaN;
  evictions++;
};

WB.three = ({ box, t0, until = null, el, px = 1280, build, nopen = true }) => {
  const THREE = need();
  if (!(Array.isArray(box) && box.length === 4 && box.every(Number.isFinite) && box[2] > box[0] && box[3] > box[1]))
    throw new Error(`WB.three ${el || ''}：box 要两角坐标 [x0, y0, x1, y1]（x1 > x0、y1 > y0）：${JSON.stringify(box)}`);
  if (!Number.isFinite(t0)) throw new Error(`WB.three ${el || ''}：t0 要一个数：${t0}`);
  if (until != null && !(Number.isFinite(until) && until > t0)) throw new Error(`WB.three ${el || ''}：until 要晚于 t0：${until}`);
  if (!(Number.isFinite(px) && px > 0)) throw new Error(`WB.three ${el || ''}：px 要一个正数：${px}`);
  if (typeof build !== 'function') throw new Error(`WB.three ${el || ''}：build(THREE, rng) 必填`);
  const [x0, y0, x1, y1] = box, w = x1 - x0, h = y1 - y0, cw = Math.max(1, Math.round(px)), ch = Math.max(1, Math.round(px * h / w));
  const renderer = shared(THREE, cw, ch), sz = new THREE.Vector2();
  const canvas = document.createElement('canvas'); canvas.width = cw; canvas.height = ch;         // 本件的 2D 缓存画布
  const cg = canvas.getContext('2d');
  const made = build(THREE, U.rng(seedOf(el == null ? 'three' : el)));
  if (!made || !made.scene || !made.camera || typeof made.update !== 'function')
    throw new Error(`WB.three ${el || ''}：build 要返回 {scene, camera, update(tContent, tAmbient)}`);
  const { scene, camera, update } = made;
  if (camera.isPerspectiveCamera) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
  const cache = { t: NaN, a: NaN };                                                               // 缓存里那张画的 (t, 装饰时刻)
  const pose = t => { update(t - t0, WB.ambientT(t) - t0); };
  const me = { scene, canvas, cache };                                                            // 常驻表里的本件
  built++;
  const part = WB.custom({ t0, t1: t0, until, el, bb: [x0, y0, x1, y1], nopen, draw(g, q, t) {
    if (t < t0 || (until != null && t >= until)) return null;
    const a = WB.ambientT(t);
    if (cache.t !== t || cache.a !== a) {
      const keep = keepOf(), i = live.indexOf(me);
      if (i >= 0) live.splice(i, 1);
      live.push(me);                                                                               // 标为常驻、移到表尾
      if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }  // 被释放过：缓存画布恢复原尺寸
      renderer.getSize(sz); if (sz.x !== cw || sz.y !== ch) renderer.setSize(cw, ch, false);     // 共用渲染器先换成本件尺寸
      pose(t); renderer.render(scene, camera);
      cg.clearRect(0, 0, cw, ch); cg.drawImage(renderer.domElement, 0, 0); cache.t = t; cache.a = a;
      while (live.length > keep && live[0] !== me) release(live.shift()); }                       // 超过 keep：从表头释放最久没用的（不释放本件）
    g.drawImage(canvas, x0, y0, w, h);
    return null; } });
  part.three = { THREE, scene, camera, renderer, canvas, box: [x0, y0, x1, y1], w, h, pose, cache };
  return part;
};
WB.three.keep = 4;                                                                                 // 常驻件上限（场景可改，≥1 的整数）
WB.three.stats = () => { const m = R ? R.info.memory : null;
  return { parts: built, resident: live.length, evictions, geometries: m ? m.geometries : 0, textures: m ? m.textures : 0 }; };

// WB.three.project(part, v3, t=null) → [板 x, 板 y]：三维点 v3（THREE.Vector3，世界坐标）经本件相机投影到板上：
//   v＝v3.clone().project(camera)，x＝x0 + (v.x+1)/2·w、y＝y0 + (1−v.y)/2·h。给了 t 就先按 t 摆好姿势再投影——**这会冲掉件的缓存**（下一次 draw 必重渲）；
//   不给 t 用相机当前姿势（上一次 draw 或 pose 的那个 t）。每帧跟着走的叠加件一律用 WB.three.projector（自带相机、不碰缓存）。
WB.three.project = (part, v3, t = null) => {
  const o = part && part.three;
  if (!o) throw new Error('WB.three.project：第一个参数要是 WB.three 返回的件');
  if (t != null) { o.pose(t); o.cache.t = NaN; o.cache.a = NaN; }   // 姿势改过了：下一次 draw 必重渲
  o.scene.updateMatrixWorld(); o.camera.updateMatrixWorld();
  const v = v3.clone().project(o.camera);
  return [o.box[0] + (v.x + 1) / 2 * o.w, o.box[1] + (1 - v.y) / 2 * o.h];
};

// WB.three.palette(THREE) → 材质颜色（THREE.Color，一律由 WB.C 令牌派生：new THREE.Color(WB.C.x).offsetHSL(h, s, l)，或两个令牌之间 lerp；场景文件里不写颜色字面量）。
//   判暗底：board 的 sRGB HSL 亮度 < 0.5（techdark、chalk 为暗；whiteboard、academic、paperclip、storybook 为浅）。十个键名两套相同。
//   浅底（1.3.1 原式）：wall 墙＝card 亮度 −0.15；wood 木梁与门窗＝soft；tile 瓦顶＝accent 饱和度 −0.4；metal 金属顶＝dim 色相 +0.55（偏蓝，配 metalness 0.85、roughness 0.35）；
//     cloth 布篷与旗＝accent（配 roughness 1）；tree 树冠＝line 色相 +0.25；trunk 树干＝soft；road 路面＝line 亮度 −0.08；sky／ground 半球光上下色＝card／board。
//   暗底（1.3.2，从板面往亮处配）：wall＝card 往 ink 走 0.30；wood、trunk＝card 往 dim 走 0.35（门窗比墙暗）；tile＝accent 饱和度 −0.2、亮度 −0.05；metal＝dim；cloth＝accent；
//     tree＝accent 色相 +0.25、饱和度 −0.45、亮度 −0.15（偏绿）；road＝line 往 dim 走 0.3；sky＝ink、ground＝dim（补光不再近黑）。
//     十栋小屋验收场景实测（1080p 整帧 CIELAB）：墙比板面 L* 高 51（techdark）／38（chalk），屋顶与墙 ΔE76 44／30，门窗与墙 L* 差 25／17。
//   offsetHSL 与 lerp 都在 three 的线性工作色彩空间里算。本画法主题里缺哪个颜色键就抛错点名（不让 THREE.Color(undefined) 静默变白）。
WB.three.palette = THREE => {
  const C = WB.C, col = k => {
    if (!(k in C) || C[k] == null) throw new Error(`WB.three.palette：本画法的主题里没有颜色键 ${k}（WB.C.${k}），三维材质取不到颜色`);
    return new THREE.Color(C[k]); };
  const c = (k, dh = 0, ds = 0, dl = 0) => col(k).offsetHSL(dh, ds, dl), mix = (a, b, u) => col(a).lerp(col(b), u), hsl = {};
  col('board').getHSL(hsl, THREE.SRGBColorSpace);
  if (hsl.l >= 0.5)                                                                                // 浅底：1.3.1 原式
    return { wall: c('card', 0, 0, -0.15), wood: c('soft'), tile: c('accent', 0, -0.4, 0), metal: c('dim', 0.55, 0, 0), cloth: c('accent'),
      tree: c('line', 0.25, 0, 0), trunk: c('soft'), road: c('line', 0, 0, -0.08), sky: c('card'), ground: c('board') };
  return { wall: mix('card', 'ink', 0.30), wood: mix('card', 'dim', 0.35), tile: c('accent', 0, -0.2, -0.05), metal: c('dim'), cloth: c('accent'),
    tree: c('accent', 0.25, -0.45, -0.15), trunk: mix('card', 'dim', 0.35), road: mix('line', 'dim', 0.3), sky: c('ink'), ground: c('dim') };
};

// WB.three.materials(THREE) → 上面颜色配好的 MeshStandardMaterial：wall、wood、tile、metal（metalness 0.85 roughness 0.35）、cloth（roughness 1）、tree、trunk、road。
WB.three.materials = THREE => {
  const P = WB.three.palette(THREE), M = o => new THREE.MeshStandardMaterial(o);
  return { wall: M({ color: P.wall, roughness: 0.9, metalness: 0 }), wood: M({ color: P.wood, roughness: 0.8, metalness: 0 }),
    tile: M({ color: P.tile, roughness: 0.6, metalness: 0 }), metal: M({ color: P.metal, roughness: 0.35, metalness: 0.85 }),
    cloth: M({ color: P.cloth, roughness: 1, metalness: 0 }), tree: M({ color: P.tree, roughness: 0.95, metalness: 0 }),
    trunk: M({ color: P.trunk, roughness: 0.9, metalness: 0 }), road: M({ color: P.road, roughness: 1, metalness: 0 }) };
};

// WB.three.dress(THREE, scene, M, rng) → M（木墙与金属顶的质感靠它）：
//   scene.environment＝64×32 等距柱状渐变（第 0 行＝正下方；下半 wood 渐到 ground、上半 ground 渐到 sky，都取 palette：浅底即木色→板面色→卡面色，暗底即暗木色→dim→ink），金属顶靠它反出亮面；
//   M 里非金属材质的环境强度降到 0.35；墙面贴 64×64 灰度木板纹理（8 块横板、板缝 0.62、逐板 0.90–1.00 深浅、板内细纹 ±0.03，深浅由 rng 定），
//   只是乘在墙色上的明暗系数（墙色再亮 0.06）；M 里没有 wall 就不贴。两张贴图按数值生成（THREE.Color 换 sRGB 字节），不写颜色字面量。
WB.three.dress = (THREE, scene, M, rng) => {
  const P = WB.three.palette(THREE);
  const rgb = col => { const o = {}; col.getRGB(o, THREE.SRGBColorSpace); return [o.r, o.g, o.b]; }, mix = (a, b, u) => a.map((v, k) => v + (b[k] - v) * u);
  const [cTop, cMid, cBot] = [rgb(P.sky), rgb(P.ground), rgb(P.wood)], EW = 64, EH = 32, env = new Uint8Array(EW * EH * 4);
  for (let y = 0; y < EH; y++) { const v = y / (EH - 1), c = v < 0.5 ? mix(cBot, cMid, Math.pow(v / 0.5, 0.6)) : mix(cMid, cTop, (v - 0.5) / 0.5);
    for (let x = 0; x < EW; x++) { const o = (y * EW + x) * 4; env[o] = Math.round(c[0] * 255); env[o + 1] = Math.round(c[1] * 255); env[o + 2] = Math.round(c[2] * 255); env[o + 3] = 255; } }
  const envTex = new THREE.DataTexture(env, EW, EH);
  envTex.mapping = THREE.EquirectangularReflectionMapping; envTex.colorSpace = THREE.SRGBColorSpace; envTex.magFilter = THREE.LinearFilter; envTex.needsUpdate = true;
  scene.environment = envTex;
  for (const k of ['wall', 'wood', 'tile', 'cloth', 'tree', 'trunk', 'road']) if (M[k]) M[k].envMapIntensity = 0.35;
  if (!M.wall) return M;
  const TW = 64, tex = new Uint8Array(TW * TW * 4), shade = Array.from({ length: 8 }, () => 0.9 + rng() * 0.1);
  for (let y = 0; y < TW; y++) for (let x = 0; x < TW; x++) {
    const k = Math.floor(y / 8), seam = y % 8 === 0, f = seam ? 0.62 : shade[k] * (1 + 0.03 * Math.sin(x * 0.35 + k * 1.7)), o = (y * TW + x) * 4, v = Math.round(255 * Math.min(1, f));
    tex[o] = v; tex[o + 1] = v; tex[o + 2] = v; tex[o + 3] = 255; }
  const plank = new THREE.DataTexture(tex, TW, TW);
  plank.magFilter = THREE.LinearFilter; plank.minFilter = THREE.LinearMipmapLinearFilter; plank.generateMipmaps = true; plank.needsUpdate = true;
  M.wall.map = plank; M.wall.color = P.wall.clone().offsetHSL(0, 0, 0.06); M.wall.needsUpdate = true;
  return M;
};

// WB.three.aim(cam, {tx, ty, tz, d, pitch, yaw=0})：相机绕目标点 (tx, ty, tz) 摆——俯角 pitch、距离 d，yaw 绕竖轴转（角度都用度），随后 lookAt 目标并更新矩阵。
WB.three.aim = (cam, p) => { const a = p.pitch * Math.PI / 180, y = (p.yaw || 0) * Math.PI / 180, rh = p.d * Math.cos(a);
  cam.position.set(p.tx + rh * Math.sin(y), p.ty + p.d * Math.sin(a), p.tz + rh * Math.cos(y)); cam.lookAt(p.tx, p.ty, p.tz); cam.updateMatrixWorld(); };

// WB.three.projector(box, fov, poseAt) → (p3:[x, y, z], t) → 板上 [x, y]：投影器。poseAt(t, WB.ambientT(t)) 返回 WB.three.aim 的机位参数；
//   自带一台透视相机（fov、宽高比 w/h，与件的渲染相机同参数即同投影），不碰件的渲染缓存；换算同 WB.three.project。纯函数（同一 t 同一结果）。
//   件的 update 与投影器用同一个机位函数，叠加件（年份牌、数字、虚线、代理件）就每帧跟着三维走、相机移动时一起移。
WB.three.projector = (box, fov, poseAt) => {
  const THREE = need(), [x0, y0, x1, y1] = box, w = x1 - x0, h = y1 - y0, cam = new THREE.PerspectiveCamera(fov, w / h, 1, 400), v = new THREE.Vector3();
  return (p, t) => { WB.three.aim(cam, poseAt(t, WB.ambientT(t))); v.set(p[0], p[1], p[2]).project(cam); return [x0 + (v.x + 1) / 2 * w, y0 + (1 - v.y) / 2 * h]; };
};

// WB.three.proxy({el, t0, t1, box3, P, act=null, jump='three', pad=0}) → 自定义件（代理件：每个三维内容块一个，供门禁认元素；el 与 timeline 事件同名）。
//   box3＝三维包围盒 [[x0, y0, z0], [x1, y1, z1]]，或返回它的函数 t => …（块在长高时给函数）；P＝WB.three.projector 返回的投影函数。
//   bbAt(t)＝8 个角经 P(·, t) 投影后的 min/max，外扩 pad；draw 返回 null（画面由 WB.three 件画）。act 不给＝按 [t0, t1) 算笔在动；
//   jump 缺省 'three'（qa 的 jumps 认作有意跳变）。登记事件：WB.ev(拍, el, 动作, 代理件, dur)。
WB.three.proxy = ({ el, t0, t1, box3, P, act = null, jump = 'three', pad = 0 }) => {
  if (typeof P !== 'function') throw new Error(`WB.three.proxy ${el || ''}：P 要一个投影函数（WB.three.projector 的返回值）`);
  const ok = b => Array.isArray(b) && b.length === 2 && b.every(c => Array.isArray(c) && c.length === 3 && c.every(Number.isFinite));
  const bbAt = t => { const b = typeof box3 === 'function' ? box3(t) : box3;
    if (!ok(b)) throw new Error(`WB.three.proxy ${el || ''}：box3 要 [[x0, y0, z0], [x1, y1, z1]]：${JSON.stringify(b)}`);
    const q = [];
    for (const x of [b[0][0], b[1][0]]) for (const y of [b[0][1], b[1][1]]) for (const z of [b[0][2], b[1][2]]) q.push(P([x, y, z], t));
    return [Math.min(...q.map(p => p[0])) - pad, Math.min(...q.map(p => p[1])) - pad, Math.max(...q.map(p => p[0])) + pad, Math.max(...q.map(p => p[1])) + pad]; };
  return WB.custom(Object.assign({ el, t0, t1, jump, bbAt, draw() { return null; } }, act ? { act } : {}));
};

// ---- 跟着三维点走的叠加件（P＝WB.three.projector 的返回值；相机移动时每帧按当时投影定位） ----
// WB.three.pop(str, at, size, anchor, o={col=WB.C.soft, fam=WB.BODY, wt='600', el}) → 砸入字（年份牌）：anchor(t) → 字底线中点 [x, y]；
//   砸入同 WB.pop 的 slam（0.17 s，at＝砸到底那一刻），textAt 报当前框。
WB.three.pop = (str, at, size, anchor, o = {}) => {
  const { col = WB.C.soft, fam = WB.BODY, wt = '600', el } = o, dur = MO.PULSE.slam, t0 = at - dur * 0.6, w = WB.measure(str, size, fam, wt);
  const rb = t => { const [x, y] = anchor(t); return [x - w / 2 - 12, y - size * 1.05, x + w / 2 + 12, y + size * 0.35]; };
  WB.texts.push(str);
  return WB.custom({ t0, t1: t0 + dur, el, size, bbAt: t => { const [x, y] = anchor(t); return [x - w / 2 - size * 0.3, y - size * 1.3, x + w / 2 + size * 0.3, y + size * 0.5]; },
    textAt: t => ({ text: str, bb: rb(t) }), draw(g, q, t) {
      const [x, y] = anchor(t), e = MO.slamK(q); g.font = WB.cf('', size, fam, wt); g.fillStyle = col; g.textBaseline = 'alphabetic'; g.textAlign = 'center';
      g.globalAlpha *= U.clamp(q * 4); g.translate(x, y - size * 0.35); g.scale(e, e); g.fillText(str, 0, size * 0.35); return null; } });
};
// WB.three.dash(pts3, t0, dur, P, o={el, w=5, col=WB.C.ink, dash=[18, 14]}) → 虚线（屋顶连线）：pts3 三维点列，t0 起 dur 秒按弧长描出（sineInOut），
//   每帧按当时投影画；act 只覆盖描线那段。dash 给 null 画实线。
WB.three.dash = (pts3, t0, dur, P, o = {}) => {
  const { el, w = 5, col = WB.C.ink, dash = [18, 14] } = o, at = t => pts3.map(p => P(p, t)), pad = w + 8;
  return WB.custom({ t0, t1: t0 + dur, el, act: t => t >= t0 && t < t0 + dur,
    bbAt: t => { const q = at(t), xs = q.map(p => p[0]), ys = q.map(p => p[1]); return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad]; },
    draw(g, q, t) { const p = at(t), cum = DG.cum(p); g.strokeStyle = col; g.lineWidth = w; g.lineCap = 'round'; if (dash) g.setLineDash(dash);
      DG.drawPartial(g, p, cum, cum[cum.length - 1] * MO.sineInOut(q)); g.setLineDash([]); return null; } });
};
// WB.three.head(pts3, t0, dur, P, o={el, w=5, col=WB.C.ink, hd=28}) → 箭头头（两笔，实线）：方向取 pts3 末点与倒数第三点的投影；接在 dash 画完之后。
WB.three.head = (pts3, t0, dur, P, o = {}) => {
  const { el, w = 5, col = WB.C.ink, hd = 28 } = o, n = pts3.length;
  const arms = t => { const e = P(pts3[n - 1], t), pr = P(pts3[Math.max(0, n - 3)], t), an = Math.atan2(e[1] - pr[1], e[0] - pr[0]);
    return [[e[0] - Math.cos(an - 0.5) * hd, e[1] - Math.sin(an - 0.5) * hd], e, [e[0] - Math.cos(an + 0.5) * hd, e[1] - Math.sin(an + 0.5) * hd]]; };
  return WB.custom({ t0, t1: t0 + dur, el, act: t => t >= t0 && t < t0 + dur,
    bbAt: t => { const a = arms(t), xs = a.map(p => p[0]), ys = a.map(p => p[1]); return [Math.min(...xs) - 10, Math.min(...ys) - 10, Math.max(...xs) + 10, Math.max(...ys) + 10]; },
    draw(g, q, t) { const a = arms(t), cum = DG.cum(a); g.strokeStyle = col; g.lineWidth = w; g.lineCap = 'round'; g.lineJoin = 'round'; DG.drawPartial(g, a, cum, cum[2] * q); return null; } });
};
})();
