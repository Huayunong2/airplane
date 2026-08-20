Python 二维飞机对战游戏（单人/多人联机 + 开放接口）
================================================

快速开始
--------------------------------
- **环境要求**  
  - Python 3.8 及以上（推荐 Python 3.12，已在 Windows 10、macOS 13、Ubuntu 22.04 实测）  
  - GPU 非必需；建议使用具备 OpenGL 的显卡以获得更顺畅的渲染体验  
  - 资产资源体积约 60 MB，安装前请预留磁盘空间  

- **安装依赖**


```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

- **启动客户端入口**

```bash
# 推荐方式：进入主菜单，可选择单人、联机、设置等功能
python -m game

# 开发调试：直接进入单人无尽模式
python game/single_player.py

# 仅运行联机战斗（跳过主菜单，默认读取 settings_store 的联机配置）
python game/online_coop.py
```

- **启动后端组件**

```bash
# WebSocket 联机服务器（权威帧同步、房间匹配）
python -m net.server

# FastAPI REST 接口（角色、道具、关卡、对战记录等开放数据）
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

> 联机体验建议先确保 server 与客户端在同一局域网，或配置公网端口转发。客户端 `设置 → 联机服务器` 可直接修改 host/port，修改结果保存在 `settings_store.json`，重启依旧生效。


目录结构详解
--------------------------------
- `core/`：引擎抽象层  
  - `engine.py`：封装 Pygame 初始化、帧循环、事件泵、屏幕渲染流程  
  - `entities.py`：玩家、敌机、子弹、道具等基本实体定义  
  - `collision.py`：AABB 碰撞检测工具  
- `game/`：所有客户端逻辑  
  - `main_menu.py`：主菜单与 UI 动画、房间加入、服务器配置入口  
  - `single_player.py`：完整单人战斗流程（限时 & 无尽）；含本地 AI、生存统计、道具系统  
  - `online_coop.py`：多人战斗场景，包含网络客户端、HUD、断线重连、等待队友、房间码显示等  
  - `settings.py`：设置面板；静音、分辨率、控制方式、自定义掉落等  
  - `settings_store.py`：持久化读取/写入（会在 Windows 下使用 `%APPDATA%\AirBattle\settings_store.json`，非打包模式使用 `data/configs/settings_store.json`）  
  - 其他模块如 `boss_system.py`、`endless_spawner.py`、`enemy_types.py` 提供敌机 AI、随机生成、Boss 行为等  
- `net/`：服务端权威世界  
  - `server.py`：房间注册、玩家接入、状态广播、断线清理  
  - `room.py`：房间结构，负责玩家绑定、状态迁移、断线快照  
  - `world_endless.py`：无尽模式权威世界逻辑，处理敌机生成、子弹运算、碰撞判定、快照输出  
  - `crypto.py`、`protocol.py`：轻量安全封装，序列化帧数据并附带时间戳校验  
- `api/`：FastAPI 轻量接口（角色、道具、关卡、对战记录等增查改）  
- `data/`：运行期数据持久化  
  - `configs/`：默认配置与本地保存的设置  
  - `game.db`：SQLite 数据库，配合 `dao.py` 管理角色、道具、关卡、战斗记录等  
- `assets/`：美术资源  
  - `images/`：背景、玩家/敌机立绘、子弹、道具、UI 图标  
  - `sounds/`：BGM、爆炸、拾取、点击等音效  
- `utils/`：工具类模块  
  - `config.py`：合并默认配置与外部 JSON  
  - `assets.py`：统一资源加载、缓存、音频初始化  
  - `logger.py`：基础日志封装  
- `dist/`（可选）：存放 PyInstaller 打包出来的 `AirBattle.exe` 与必要数据


核心系统设计
--------------------------------
- **渲染循环**：基于 `core.engine.Engine`，60 FPS 目标帧率，统一调度事件、更新逻辑、绘制输出，对主菜单、单人、多人模式保持一致流程。  
- **实体与碰撞**：所有实体继承统一基类，碰撞检测采用轴对齐包围盒（AABB），在 `core.collision` 中实现，可根据需求扩展为像素级检测。  
- **单人模式**：  
  - 限时模式提供预设难度与自定义难度（自定义允许覆盖敌机生成、掉落概率、血量等参数）。  
  - 无尽模式通过 `power_step` 动态提升敌机速度、发射频率、Boss 强度，并同步背景淡入效果。  
  - HUD 展示血量、得分、连击、Buff 倒计时、敌机/子弹数量等信息，方便调试战斗节奏。  
- **多人模式（在线）**：  
  - `net.server` 维护房间、广播快照、处理断线与状态迁移。  
  - 客户端 `NetClient` 采用 asyncio + threading，后台线程管理 WebSocket，主线程渲染并进行输入预测。  
  - 断线保护：服务器保存最后一帧玩家状态（血量、位置、Buff 等），玩家重连后恢复；同时客户端屏幕显示“等待队友”遮罩并暂停输入。  
  - 房间码在 HUD 显示醒目标牌，保持清晰可读。  
- **音频与资源**：通过 `utils.assets` 中的缓存机制避免重复加载资源，BGM 支持立即切换音量与静音；音效按需加载并缓存，确保在 PyInstaller 打包后的 `_MEIPASS` 目录同样可用。  
- **设置持久化**：`game/settings_store.py` 自动选择可写路径保存设置，支持键位、静音、连机主机地址、端口、掉落策略等。  
- **开放接口**：`api/server.py` 打包 FastAPI 应用，提供角色、道具、关卡、战斗记录的增删查改，适合与外部系统联动或构建前端后台管理界面。


玩法与操作详解
--------------------------------
- **主菜单**  
  - 方向键 / W S：切换菜单项  
  - 回车 / 空格：确认选择  
  - ESC：退出程序  
  - 多人模式子菜单：可创建房间、输入房间码加入、配置服务器地址/端口  
- **单人模式**  
  - 移动：W A S D  
  - 开火：空格  
  - 暂停：P 或 ESC（暂停后可选择继续、设置、返回主菜单）  
  - 限时/无尽均支持进化机制（收集进化币达到阈值提升等级，外观与火力同步增强）  
- **多人模式**  
  - 操作同单人模式  
  - HUD 左上角显示 HP、得分、进化、Buff；右上角显示房间信息、网络状态  
  - 当队友离线时客户端自动暂停并提示等待；所有玩家阵亡后若任一玩家退出，其他玩家直接返回上一层  
  - 支持本地预测，尽量减少延迟造成的操作迟滞感  


配置与数据管理
--------------------------------
- `data/configs/config.json`：覆盖默认配置（窗口、网络、数据库路径等），配合 `utils.config.DEFAULT_CONFIG` 自动合并。  
- `data/configs/settings_store.json`：存放运行时设置；若文件损坏或希望恢复默认，可删除重新生成。  
- `data/dao.py`：封装 SQLite 访问逻辑，首次调用自动建表。  
- 若通过 PyInstaller 打包，设置文件会存放在 `%APPDATA%\AirBattle` 或 `~/AirBattle` 目录，便于普通用户写入权限管理。  


部署与打包
--------------------------------
- **开发环境推荐流程**

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python -m game  # 进入主菜单
```

- **打包为单文件 exe**

```bash
pyinstaller --noconfirm ^
  --clean ^
  --name AirBattle ^
  --windowed ^
  --collect-all pygame ^
  --add-data "assets;assets" ^
  --add-data "data;data" ^
  game\__main__.py
```

产物位于 `dist/AirBattle.exe`，运行时自动加载同级 `assets/` 与 `data/`。如需缩小体积，可在打包前对图片进行 WebP 压缩、音频转码为 OGG/Vorbis。

- **常见发布策略**  
  - Windows：提供 exe + 资源目录，或使用 Inno Setup/wix 打包安装器  
  - macOS：通过 `py2app` 或 `pyinstaller --collect-all pygame --windowed` 打包 .app  
  - Linux：直接分发虚拟环境或使用 AppImage


排错与 FAQ
--------------------------------
- **无法连接联机服务器**  
  - 确认 `net.server` 已启动；同一设备可使用默认 `ws://127.0.0.1:8765` 测试  
  - 若跨设备联机，需保证处于同一局域网或配置端口转发；客户端在设置中填写服务器内网/公网地址  
  - 若使用打包 exe，可在主菜单 → 多人联机 → 服务器设置中直接输入地址  
- **Boss 出场音效未播放**  
  - 服务器会为每次 Boss 生成递增事件号 `boss_spawn_event_id`，客户端收到不同事件号即播放；若仍无声音，检查是否开启静音或设备音量  
- **退出战斗卡顿**  
  - 客户端已经对 WebSocket 关闭与线程 join 进行了超时处理（默认 0.8s）；若在极慢网络环境仍卡，可在 `game/online_coop.py` 中调小超时时间  
- **设置未保存**  
  - 检查 `%APPDATA%\AirBattle\settings_store.json` 是否可写；若运行在只读盘，可手动创建并授予写权限  
- **打包后字体/音频异常**  
  - 确认打包命令包含 `--collect-all pygame` 与 `--add-data "assets;assets"`，并在目标机器上安装中文字体  
- **多人模式敌机首次出现仍有爆炸**  
  - 若修改过代码，请检查 `have_prev_enemy_snapshot` 标记与 `enemy.net_uid` 逻辑是否完整；默认项目已修复该问题  
- **数据库文件过大**  
  - `data/game.db` 只存结构化配置，不随战斗增长；若需要清空记录，可调用 `DAO.clear_records()` 或直接删除 `game.db`


开发与维护建议
--------------------------------
- 建议在修改 `game/online_coop.py`、`net/server.py` 等关键文件后，执行一次本地双人联机回归测试（本机开两份客户端或局域网两台设备）。  
- 如需扩展更多模式，可在 `game/spawner.py` / `game/endless_spawner.py` 基础上添加自定义敌机或事件，并在 `net/world_endless.py` 中同步相同逻辑。  
- 若引入第三方依赖，请更新 `requirements.txt` 并在 README 中说明用途。  
- PyInstaller 打包后，记得清理 `build/`、`__pycache__` 等缓存目录减小仓库体积。


许可证
--------------------------------
本仓库用于教学与原型验证，可在保留署名的前提下自由二次开发与分发。若用于商业项目，请确保自行替换原创或具有合法授权的美术与音频资源。
