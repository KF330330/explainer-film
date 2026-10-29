# 三维可选件：templates/three.js（1.3.1；1.3.2 加暗底配色、显存按最近使用释放）

> 何时读：分镜里有 `look:"三维"` 的拍；`project.json` 的 `libs` 含 `lib/three.min.js` 的工程，写场景前必读。

## 何时用

- 讲**地点**或**事情**的拍：一条街长出房子、一片城对比另一片城、一间屋子里发生的事。三维要承载内容（数量、位置、先后），数字落到三维物件上。
- **不用于装饰**：只为「看起来高级」加一块三维，换成二维件。三维每帧约是二维的 1.4 倍耗时，还多一套要核的东西（投影、阴影、材质）。

## 开法

- 建新工程：`new_project.py --dest D --film F --title T --three`。`three.js` 复制到 `engine/F/wb/three.js`，libs 为 `["F/wb/parts.js", "lib/three.min.js", "F/wb/three.js"]`。
- 已有新格式工程：`new_project.py --dest D --add-three`。先备份到 `D/.add-three-bak-<时刻>/`，再补 libs、复制 `three.js`、重写 eras 的 SCENE_LIBS；任一步失败就整体还原。以下情况零写入：已带三维（退出 0）、老工程、eras 认不出格式、工程里的 `three.js` 改过（都退出 2；改过的要手动合并）。
- `lib/three.min.js` 是 vendor 自带的 three.js r160（UMD，挂 `window.THREE`），`index.html` 不用改。载入时有一条「r150+ 弃用」warning、每次载入有几条「GPU stall due to ReadPixels」warning，门禁不收。
- 工程里那份 `three.js` 是**副本**，升级 skill 不会改它。

## 接口（场景里直接用 `WB.three…`）

**1. `WB.three({box:[x0, y0, x1, y1], t0, until=null, el, px=1280, build, nopen=true})`** → 自定义件
- `box` 是两角坐标（同 `WB.frame`），既是绘制范围，也是上报的静态包围盒。离屏尺寸为 `px × round(px·h/w)`，1080p 上不想发虚就给到约 1600。
- `build(THREE, rng)` 返回 `{scene, camera, update(tContent, tAmbient)}`。`rng` 的种子由 el 定。`update` 必须是纯函数：不读时钟、不用 mixer、不累积状态。
- `tContent = t − t0` 承载内容；`tAmbient = WB.ambientT(t) − t0` 只给装饰摆动。
- 返回件挂 `.three = {THREE, scene, camera, renderer, canvas, box, w, h, pose(t), cache}`，其中 `canvas` 是本件的 2D 缓存画布。缓存按 (t, 装饰时刻 `WB.ambientT(t)`) 认，`cache = {t, a}`。
- 全片**共用一个渲染器**（见硬事实），所以 `renderer` 的状态（尺寸、阴影、色调映射）场景里别改。
- `nopen` 为真：件本身不算笔在动。门禁要认的内容块，各登记一个代理件（第 7 条）。
- `WB.three.keep`（缺省 4）：显存里最多常驻几个件，超过就释放最久没真渲过的（见硬事实）。场景可改，须是 ≥1 的整数，否则真渲时抛错点名。**至少设成同屏最多的三维件数。**
- `WB.three.stats()` → `{parts, resident, evictions, geometries, textures}`：建过的件数、常驻件数、累计释放次数，后两项取共用渲染器的 `info.memory`（渲染器还没建时为 0）。

**2. `WB.three.project(part, v3, t=null)`** → `[x, y]`
- 用件自己的相机投影一个 `THREE.Vector3`。**给 t 会冲掉件的缓存**（先按 t 摆姿势，下一次 draw 必重渲）。
- 只在建板时算一次位置用。每帧跟着走的叠加件一律用 projector（第 6 条）。

**3. `WB.three.palette(THREE)`、`WB.three.materials(THREE)`**
- palette 从 `WB.C` 派生十个颜色，**自动认暗底**：board 的 sRGB HSL 亮度 < 0.5 为暗，否则为浅（白板是浅底）。十个键名两套相同。
  - 浅底（1.3.1 原式，画面逐字节不变）：wall＝card 暗 0.15、wood＝soft、tile＝accent 降饱和 0.4、metal＝dim 色相 +0.55、cloth＝accent、tree＝line 色相 +0.25、trunk＝soft、road＝line 暗 0.08、sky／ground＝card／board。
  - 暗底（从板面往亮处配）：wall＝card 往 ink 走 0.30；wood、trunk＝card 往 dim 走 0.35（门窗比墙暗）；tile＝accent 降饱和 0.2、暗 0.05；metal＝dim；cloth＝accent；tree＝accent 色相 +0.25、降饱和 0.45、暗 0.15（偏绿）；road＝line 往 dim 走 0.3；sky＝ink、ground＝dim（半球补光与环境图不再近黑）。
  - 「往 X 走 u」是两令牌的 `Color.lerp`，「暗／降饱和」是 `offsetHSL`，都在 three 的线性工作空间算。
- materials 给其中八个配好的 `MeshStandardMaterial`；metal 为 metalness 0.85、roughness 0.35。
- 主题缺颜色键就抛错点名，不会静默变白。场景里不写颜色字面量。

**4. `WB.three.dress(THREE, scene, M, rng)`** → M
- 给 `scene.environment` 一张由主题派生的等距柱状渐变，金属顶靠它反出亮面；非金属材质的环境强度降到 0.35。
- 墙面贴灰度木板纹理。M 里没有 `wall` 就不贴。

**5. `WB.three.aim(cam, {tx, ty, tz, d, pitch, yaw=0})`**：相机绕目标点摆，俯角 pitch、距离 d、yaw 绕竖轴转，角度都用度。

**6. `WB.three.projector(box, fov, poseAt)`** → `(p3:[x, y, z], t) => [x, y]`
- 自带一台相机，机位取 `poseAt(t, WB.ambientT(t))`。纯函数，不碰件缓存。
- 件的 `update` 与投影器要用**同一个机位函数**，叠加件才会跟着三维走。

**7. `WB.three.proxy({el, t0, t1, box3, P, act=null, jump='three', pad=0})`** → 代理件
- `box3` 为 `[[x0, y0, z0], [x1, y1, z1]]`，或返回它的函数（块在长高时给函数）。
- `bbAt(t)` 取 8 个角经 `P` 投影后的外框；不画东西。`act` 不给时，按 `[t0, t1)` 算笔在动。
- 登记事件：`WB.ev(拍, el, 动作, 代理件, dur)`。

**8. `WB.three.pop(str, at, size, anchor, o)`、`WB.three.dash(pts3, t0, dur, P, o)`、`WB.three.head(pts3, t0, dur, P, o)`**：跟着三维点走的叠加件
- pop 是砸入字（年份牌）。`anchor(t)` 给字底线中点；`o = {col=WB.C.soft, fam=WB.BODY, wt='600', el}`。
- dash 是按弧长描出的虚线；`o = {el, w=5, col=WB.C.ink, dash=[18, 14]}`，`dash:null` 画实线。
- head 是接在线尾的箭头头，`o.hd=28`。
- 上屏字由调用者定。

```js
const box = [200, 1300, 2600, 2300], fov = 26;                                  // 两角坐标
const pose = (t, a) => ({ tx: 0, ty: 0.6, tz: -1.5, d: 60, pitch: 28, yaw: 0.3 * Math.sin(2 * Math.PI * a / 6) });   // 装饰摆动走 a
const P = WB.three.projector(box, fov, pose), t0 = WB.qb('B2_01', '一条街') - 0.1;
const up = t => MO.cubicOut(U.clamp((t - t0 - 0.2) / 0.6));                    // 房子升起（全片秒）
WB.three({ box, t0, el: 'city', px: 1600, build: (THREE, rng) => {
  const scene = new THREE.Scene(), M = WB.three.dress(THREE, scene, WB.three.materials(THREE), rng), C = WB.three.palette(THREE);
  scene.add(new THREE.HemisphereLight(C.sky, C.ground, 0.9));
  const sun = new THREE.DirectionalLight(); sun.intensity = 2.4; sun.position.set(-26, 44, 30); sun.castShadow = true; scene.add(sun);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(160, 120), new THREE.ShadowMaterial({ opacity: 0.25 }));   // 只接阴影，纸面透出来
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  const house = new THREE.Mesh(new THREE.BoxGeometry(2.4, 2, 2.4).translate(0, 1, 0), M.wall); house.castShadow = true; scene.add(house);
  const camera = new THREE.PerspectiveCamera(fov, 2.4, 1, 400);
  return { scene, camera, update: (tC, tA) => { const e = up(tC + t0); house.visible = e > 0; house.scale.y = Math.max(1e-3, e);
    WB.three.aim(camera, pose(tC + t0, tA + t0)); } };              // 件传的是 t − t0：加回 t0 再查同一个机位函数
} });
const px = WB.three.proxy({ el: 'house1', t0: t0 + 0.2, t1: t0 + 0.8, P, box3: t => [[-1.2, 0, -1.2], [1.2, 2 * up(t), 1.2]] });
WB.ev('B2_01', 'house1', 'grow', px, 0.6);
WB.three.pop('2026 年', t0 + 0.9, 58, t => P([0, 2.6, 0], t), { el: 'house1' });   // 年份牌贴着房顶
```

## 硬事实

- **默认软件 WebGL**。出片链与门禁的无头浏览器走 SwiftShader（ANGLE＋SwiftShader，Playwright 缺省带软件回退）。
  - 每帧三维渲染约 54–74 ms（50 栋 1280×533 与 30 栋 1600×667 实测）。1.3.1 实测 10 栋 1280×560 约 28–34 ms，当时同机负载约 24。
  - 三维段整帧约是二维的 **1.4 倍**耗时。
- **不许给出片链加显卡参数**。起浏览器的地方有 10 处，其中 vendor 里写死 2 处；只开一处，各处画面就不一致。
- **同 t 逐字节一致**：同一时刻两次起浏览器渲出的帧，sha 相同。
- **糊影时一帧最多重渲 8 次**：远行运镜会以不同 t 调件多次，每次都要重渲。同一 (t, 装饰时刻) 只渲一次；QA 在同一 t 换锁定时刻（`WB.lockcam`）时装饰时刻变了，照样重渲。
- **全片共用一个 WebGL 上下文**。渲染器在首个件建时建；每件只多一张 2D 缓存画布，渲前把共用渲染器换成本件尺寸。别的件渲染不会冲掉本件缓存（常驻超过 `keep` 被释放的除外，见下条）。
  - 早期版本的旧件是一件一个上下文、从不释放。按全片件数累计，超过浏览器上限（约 16）最早的会丢。
  - 实测四章 23 件：旧件建了 23 个上下文，报「Too many active WebGL contexts」后出帧报错；本件只建 1 个，首末章都有画。
- **显存按最近使用释放（1.3.2）**：真渲过的件记为常驻；常驻超过 `keep` 就释放最久没真渲的件——几何、材质与其上贴图、环境图（连同 PMREM 图）、阴影图、2D 缓存画布（宽高置 0）。场景图与贴图数据留在 CPU，不重跑 `build`；再渲到它时自动重传，画面逐字节相同。
  - 60 件压测（12 段×5 件、每件 300 个网格、阴影图 2048、px 1600，各渲 3 帧；同机负载约 4–7）：
  - 1.3.1：Chromium RSS 每件涨约 47 MB，第 12 件 1281 MB → 第 60 件 3534 MB（+176%），60 件内没崩、上下文没丢。
  - 1.3.2：常驻 4 件后停在约 920–944 MB，第 12 件 923 MB → 第 60 件 944 MB（+2.2%），无报错、上下文没丢。
  - **同屏三维件多于 `keep` 会变慢**：同一帧里反复释放、重传（画面照样对）。同屏件多的段落把 `keep` 调大。
- **palette 自动认暗底**（1.3.2 起）：板面是暗色时自动换暗底派生（接口第 3 条）；白板是浅底，走浅底配色。用前仍出一张静帧看；太阳用白色（`new THREE.DirectionalLight()`），别设成 `P.sky` 之类的主题色。
- **装饰摆动走 tAmbient**：qa 锁相机与 `render.sh --noambient` 时冻结。片尾三维还在摆时，`qa_config.still_video_source` 设 `"noambient_draft"`，否则片尾噪声会抬高静止阈值。

## 经验（一支「三维小城」样片）

- **数字与街区同帧落定**：每栋房子的落定时刻用 sineInOut 的反函数排，最后一栋和数字同一帧落定。做法同 `WB.stack` 的「每摞两步」：

```js
const inv = v => Math.acos(1 - 2 * U.clamp(v)) / Math.PI;                       // MO.sineInOut 的反函数
const rise = (n0, n1, ta, tb, k) => { const land = ta + (tb - ta) * inv((k + 1 - n0) / (n1 - n0)); return [Math.max(ta, land - 0.4), land]; };   // 第 k 栋 [起, 落定]
```

- **叠加件一律用 projector**：年份牌、数字、虚线、代理件、小人的位置，都每帧按投影器算，三维相机移动时一起移。数字落定窗口内让三维相机静止，只留 ±0.3° 装饰摆动。
- **60 px 宽的房子看不出材质**：样片里有一档每栋在屏上约 60 px 宽，审片说看不出木纹与金属感。要靠材质说话的镜头，让房子在屏上大一些。
- **推近会切掉早建的东西**：新东西总长在一侧时，机位每档要框住已建的全部加下一块空地；只在最后一档居中推近。
- **相机移动登记成跳变**：每次三维相机移动，另登记一个 `WB.custom({el:'cam3', t0, t1, bb: box, jump:'camera', act, draw(){return null;}})`，qa 的 jumps 认作有意运镜。
