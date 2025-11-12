Python 二维飞机对战游戏（单人/多人联机 + 开放接口）
================================================

快速开始
--------------------------------
- 环境要求：Python 3.8+（已在 Python 3.12 验证），Windows 10+/macOS 12+/Ubuntu 20.04+
- 安装依赖：

```bash
pip install -r requirements.txt
```

- 运行主菜单（推荐入口）：

```bash
python -m game
```

- 直接运行单人模式（用于开发联调）：

```bash
python game/single_player.py
```

- 启动开放接口（FastAPI）：

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

- 启动联机服务器（WebSocket）：

```bash
python -m net.server
```

目录结构
--------------------------------
- core/        引擎封装、实体与碰撞
- game/        单人/联机客户端与UI
- net/         权威服务器、协议与房间
- api/         FastAPI 网关与开放接口
- data/        SQLite 与 JSON 配置
- utils/       配置、日志、错误码
- tests/       测试脚手架
- docs/        变更记录与下一步计划（重要：清空对话后可快速回忆）
- assets/      图片与音频资源（统一由 `utils/assets.py` 加载与缓存）

设计说明（摘）
--------------------------------
- 60FPS 帧循环、对象回收（后续实现）、AABB 碰撞
- 联机采用服务器权威 + 帧同步（20ms 广播）+ 客户端插值
- WebSocket + Base64 + 时间戳校验，避免基础篡改
- 开放接口 v1：角色、道具、关卡、对战模式、数据统计

单人模式（玩法与操作）
--------------------------------
- 模式：
  - 限时 Timed：支持难度选择（简单/中等/困难/自定义），计时 180s。
  - 无尽 Endless：不选难度，强度每 20s 缓慢提升，含背景自动切换与淡入。
- 操作：
  - WASD 移动，空格 开火，P 暂停/继续。
  - H 历史榜（在单人模式内部菜单中可开关）。
  - 回车开始（在单人模式内部菜单中）。
  - ESC 行为统一：仅在主菜单 ESC 退出程序；在游戏中 ESC 先暂停；在单人模式内部菜单 ESC 返回主菜单。
- HUD：显示 HP/Score/Combo/道具加成/FPS/敌机子弹数等；道具持续类效果以中文列出并带倒计时。

设置与自定义
--------------------------------
- 主菜单 `设置` 页分为五大类：基础与显示、音频、操作与控制、战斗与玩法（自定义测试用）、系统操作。支持滚轮/翻页滚动和长按连续调节。
- `战斗与玩法` 中的参数（敌机生成、掉落概率/权重、碰撞盒显示等）仅在单人模式选择“自定义”难度时生效，其它难度自动使用预设。
- 设置与自定义参数会自动保存到 `data/configs/settings_store.json`；删除该文件即可恢复默认设置。

资源与归档（图片/音频）
--------------------------------
- 统一放置于 `assets/`：
  - 图片：`assets/images/...`
  - 音频：`assets/sounds/...`
- 背景：
  - 主菜单：`assets/images/backgrounds/backgroundmenu.jpg`
  - 战斗（限时模式）：`assets/images/backgrounds/backgroundbattle.png`
  - 无尽模式多背景：支持 `assets/images/backgrounds/battle1.jpg`、`battle2.jpg`、`battle3.jpg`、`battle4.jpg`，每 20s 随机切换并 1s 交叉淡入。
- 其他关键资源（可选，缺失将优雅降级为占位或静音）：
  - 玩家机体：`assets/images/player/player_ship.png`
  - 敌机机体：`assets/images/enemy/enemy_basic.png`
  - 子弹：`assets/images/bullet/bullet_basic.png`、`assets/images/bullet/bullet_enemy.png`
  - 爆炸序列：`assets/images/fx/explosion_sheet.png`
  - 道具图标：`assets/images/prop/prop_*.png`（heal/x2/shield/piercing/spread/haste/power/clearscreen）
  - BGM：`assets/sounds/bgm/menu.mp3`、`assets/sounds/bgm/game.ogg`
  - SFX：`assets/sounds/player/shoot.wav`、`assets/sounds/prop/pickup_buff.wav`、`assets/sounds/fx/explosion_small.wav` 等

常见问题（FAQ）
--------------------------------
- ImportError: attempted relative import with no known parent package
  - 直接运行 `game/single_player.py` 时，文件已自动将项目根目录加入 `sys.path`，并对 `settings_store` 做了兼容导入；若仍报错，请从项目根目录运行：`python game/single_player.py`。
- 依赖安装报错（如 uvicorn 版本不兼容）
  - 本项目 `requirements.txt` 已适配 Python 3.12；如只想先体验单人模式，可先安装 `pygame`：`pip install pygame`。
- 中文显示乱码
  - 已切换 `pygame.freetype`/系统字体探测；如仍异常，请检查操作系统是否安装中文字体（如微软雅黑/思黑体等）。

开发者提示
--------------------------------
- 所有更新会记录在 `docs/CHANGELOG.md`
- 后续计划维护在 `docs/NEXT_STEPS.md`

打包为 Windows 可执行程序（EXE）
--------------------------------
- 先安装打包工具：

```bash
.venv\Scripts\python -m pip install pyinstaller
```

- 在项目根目录执行（包含资源目录与 Pygame 依赖）：

```bash
.venv\Scripts\pyinstaller --noconfirm --clean --name AirBattle --windowed --collect-all pygame --add-data "assets;assets" --add-data "data;data" game\__main__.py
```

- 产物位置：
  - `dist/AirBattle/AirBattle.exe`（双击启动主菜单）
  - 若出现中文字体缺失或音频不可用，程序会降级显示或静默运行

许可证
--------------------------------
本仓库用于教学/原型用途，可自由二次开发。***

