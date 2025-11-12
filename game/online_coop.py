import sys
import os
import asyncio
import json
import time
import uuid
import hashlib
import threading
import pygame
from typing import Optional

if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.engine import Engine
from core.entities import Player
from utils import assets
from utils.logger import get_logger
from game.props_system import PROP_SPECS
from game.pause_menu import PauseMenu
from game import settings_store
logger = get_logger("online_coop")


def choose_font(size: int) -> pygame.font.Font:
    # Prefer fonts with CJK glyphs to avoid garbled HUD text
    candidates = [
        "Microsoft YaHei",  # 微软雅黑
        "SimHei",           # 黑体
        "SimSun",           # 宋体
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "Segoe UI Symbol",
    ]
    for name in candidates:
        try:
            path = pygame.font.match_font(name, bold=False, italic=False)
            if path:
                return pygame.font.Font(path, size)
        except Exception:
            continue
    return pygame.font.SysFont(None, size)


class NetClient:
    def __init__(self, uri: str, player_id: str, invite_code: Optional[str] = None, create_new: bool = False):
        self.uri = uri
        self.player_id = player_id
        self.invite_code = invite_code.upper() if invite_code else None
        self.create_new = create_new
        self.state_remote = {}  # {player_id: {x,y,hp}}
        self.state_world = {"players": {}, "enemies": [], "player_bullets": [], "enemy_bullets": [], "props": [], "coins": [], "status": "connecting", "countdown": None, "tick": 0}
        self.ws = None
        self._lock = threading.Lock()
        self._stop = False
        self.connected = False
        self.last_error = ""
        self.last_state_ts = 0.0
        self.meta_status = {"status": "connecting", "countdown": None, "invite_code": ""}
        self.start_time = 0.0

    async def _run_ws(self):
        import websockets
        try:
            # 构建连接URI，包含房间号信息
            connect_uri = self.uri
            if self.invite_code or self.create_new:
                from urllib.parse import urlparse, urlencode, urlunparse
                parsed = urlparse(connect_uri)
                params = {}
                if self.invite_code:
                    params["invite_code"] = self.invite_code
                if self.create_new:
                    params["create"] = "true"
                query = urlencode(params)
                parsed = parsed._replace(query=query)
                connect_uri = urlunparse(parsed)

            async with websockets.connect(connect_uri, ping_interval=10) as ws:
                self.ws = ws
                # 发送加入消息（如果通过查询参数无法传递，则通过消息传递）
                if self.invite_code or self.create_new:
                    try:
                        from net.protocol import make_envelope
                        join_payload = {}
                        if self.invite_code:
                            join_payload["invite_code"] = self.invite_code
                        if self.create_new:
                            join_payload["create"] = True
                        env = make_envelope("join", join_payload, time.time())
                        await ws.send(env.to_json())
                    except Exception:
                        pass

                self.connected = True
                async for msg in ws:
                    try:
                        obj = json.loads(msg)
                        if obj.get("t") == "state":
                            d = obj.get("d", {})
                            tok = d.get("token", "")
                            payload = {}
                            if tok:
                                try:
                                    from net.crypto import decode_with_timestamp
                                    raw = decode_with_timestamp(tok)
                                    payload = json.loads(raw.decode("utf-8"))
                                except Exception:
                                    payload = {}
                            players = payload.get("players", {})
                            enemies = payload.get("enemies", [])
                            with self._lock:
                                self.state_remote = players
                                self.state_world = payload
                                current_status = payload.get("status") or self.meta_status.get("status", "waiting")
                                current_countdown = payload.get("countdown")
                                current_invite = payload.get("invite_code", self.meta_status.get("invite_code", ""))
                                self.meta_status = {
                                    "status": current_status,
                                    "countdown": current_countdown,
                                    "invite_code": current_invite,
                                }
                                self.last_state_ts = time.time()
                                # 如果游戏开始，同步开始时间
                                if payload.get("status") == "running" and payload.get("start_time"):
                                    self.start_time = payload.get("start_time")
                        elif obj.get("t") == "welcome":
                            data = obj.get("d", {})
                            pid = data.get("player_id")
                            if pid:
                                self.player_id = pid
                            if data.get("invite_code"):
                                self.meta_status["invite_code"] = data["invite_code"]
                                self.invite_code = data.get("invite_code", self.invite_code)
                    except Exception:
                        pass
        except Exception as e:
            logger.error("ws error: %s", e)
            self.last_error = str(e)
        finally:
            self.connected = False
            self.ws = None

    def start(self):
        loop = asyncio.new_event_loop()
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_ws())
        t = threading.Thread(target=run_loop, daemon=True)
        t.start()

    async def send_input(self, move_x: float, move_y: float, fire: bool):
        if self.ws is None:
            return
        from net.protocol import make_envelope
        from net.crypto import encode_with_timestamp
        payload = {"player_id": self.player_id, "state": {"mx": move_x, "my": move_y, "fire": fire, "ts": time.time()}}
        token, ts = encode_with_timestamp(json.dumps(payload).encode("utf-8"))
        env = make_envelope("input", {"token": token, "player_id": self.player_id, "state": payload["state"]}, ts)
        try:
            await self.ws.send(env.to_json())
        except Exception:
            pass

    def get_remote_players(self):
        with self._lock:
            return dict(self.state_remote)

    def get_world(self):
        with self._lock:
            return dict(self.state_world)

    def get_status(self):
        info = {"connected": self.connected, "last_error": self.last_error, "last_state_ts": self.last_state_ts}
        info.update(self.meta_status)
        return info


def run(as_child: bool = True, engine: "Engine | None" = None, invite_code: Optional[str] = None, create_new: bool = False) -> None:
    """
    局域网双人（预览版）：
    - 本地运行 coop_local 的单人视角（含敌机/子弹），并叠加远端玩家位置
    - 未来阶段将把敌机/Boss与碰撞搬到服务器侧。本版用于联机架构预热和键位验证
    
    Args:
        as_child: 是否作为子进程运行
        engine: 引擎实例
        invite_code: 房间号（6位字母数字）
        create_new: 是否创建新房间（如果房间不存在）
    """
    engine = engine or Engine()
    pygame.font.init()

    # 背景与资源
    bg_size = (engine.screen.get_width(), engine.screen.get_height())
    bg_battle = assets.load_image("backgrounds/backgroundbattle.png", size=bg_size)
    # 无尽模式多背景（与单人无尽模式一致）
    endless_bg_list: list = []
    for _name in ("battle1.jpg", "battle2.jpg", "battle3.jpg", "battle4.jpg"):
        _surf = assets.load_image(f"backgrounds/{_name}", size=bg_size)
        if _surf is not None:
            endless_bg_list.append(_surf)
    # 背景切换状态（从服务器同步）
    bg_cur_idx: int = 0
    bg_fading: bool = False
    bg_fade_start: float = 0.0
    bg_next_idx: int = 0
    bg_fade_surface: Optional[pygame.Surface] = None
    bg_switch_interval: float = 20.0
    bg_next_switch_time: float = 0.0
    prev_bg_index: int = -1  # 跟踪服务器背景索引
    
    dim_overlay = pygame.Surface(bg_size, pygame.SRCALPHA)
    dim_overlay.fill((0, 0, 0, 55))
    ship_img = assets.load_image("player/player_ship.png", size=(40, 40))
    # 使用多机型图片系统（与服务器端一致）
    from game.enemy_types import load_enemy_images, EnemyType
    enemy_images = load_enemy_images()
    enemy_base_img = assets.load_image("enemy/enemy_basic.png")  # 备用
    _enemy_img_cache: dict[tuple[int, int], Optional[pygame.Surface]] = {}
    coin_img = assets.load_image("prop/coin.png", size=(26, 26))
    # 玩家进化图片（与单人无尽模式一致）
    evo_ship_imgs = [
        assets.load_image("player/roleplane1.png", size=(40, 40)),
        assets.load_image("player/roleplane2.png", size=(44, 44)),
        assets.load_image("player/roleplane3.png", size=(48, 48)),
        assets.load_image("player/roleplane4.png", size=(52, 52)),
        assets.load_image("player/roleplane5.png", size=(56, 56)),
    ]
    # 子弹资源（与单人无尽模式一致）
    player_size = (56, 42)
    player_plus_size = (28, 62)
    enemy_size = (56, 36)
    bullet_img = assets.load_image("bullet/bullet_role.png", size=player_size)
    if bullet_img is not None:
        bullet_img = pygame.transform.rotate(bullet_img, 90)
    bullet_img_plus = assets.load_image("bullet/bullet_role_plus.png", size=player_plus_size)
    if bullet_img_plus is not None:
        bullet_img_plus = pygame.transform.rotate(bullet_img_plus, -205)
    enemy_bullet_img = assets.load_image("bullet/bullet_enemy.png", size=enemy_size)
    if enemy_bullet_img is not None:
        enemy_bullet_img = pygame.transform.rotate(enemy_bullet_img, 90)
    # 道具资源（与单人无尽模式一致）
    prop_heal_img = assets.load_image("prop/prop_heal.png", size=(32, 32))
    prop_x2_img = assets.load_image("prop/prop_x2.png", size=(32, 32))
    prop_shield_img = assets.load_image("prop/prop_shield.png", size=(32, 32))
    prop_piercing_img = assets.load_image("prop/prop_piercing.png", size=(32, 32))
    prop_spread_img = assets.load_image("prop/prop_spread.png", size=(32, 32))
    prop_haste_img = assets.load_image("prop/prop_haste.png", size=(32, 32))
    prop_power_img = assets.load_image("prop/prop_power.png", size=(32, 32))
    prop_clear_img = assets.load_image("prop/prop_clearscreen.png", size=(32, 32))
    PROP_IMAGES = {
        "heal": prop_heal_img,
        "x2": prop_x2_img,
        "shield": prop_shield_img,
        "piercing": prop_piercing_img,
        "spread": prop_spread_img,
        "haste": prop_haste_img,
        "power": prop_power_img,
        "clearscreen": prop_clear_img,
    }
    # 爆炸资源（与单人无尽模式一致）
    from game.explosion import Explosion, load_explosion_frames
    explosion_frames = load_explosion_frames()
    explosions: list[Explosion] = []
    # 跟踪敌机状态以检测死亡
    prev_enemy_ids: dict[int, tuple] = {}
    # 跟踪已播放爆炸的敌机，避免重复播放
    exploded_enemies: set[int] = set()
    # 每个敌机固定选择的机型索引，防止移动时切换贴图
    enemy_variants: dict[int, int] = {}
    last_boss_event_id: int = -1
    paused_world_snapshot: Optional[dict] = None
    seen_boss_ids: set[int] = set()
    have_prev_enemy_snapshot: bool = False

    # 战斗BGM（客户端本地播放，保证双方一致）
    assets.play_bgm("bgm/battle.ogg", 0.45, loop=True)

    # 网络
    import json as _json
    from utils.config import load_config
    cfg = load_config()
    override_host = settings_store.get_setting("net_host", "")
    if isinstance(override_host, str):
        override_host = override_host.strip()
    else:
        override_host = str(override_host).strip()
    override_port = settings_store.get_setting("net_port", 0)
    try:
        override_port_int = int(override_port)
    except (TypeError, ValueError):
        override_port_int = 0
    ws_host = override_host or cfg["network"]["ws_host"]
    ws_port = override_port_int if override_port_int else cfg["network"]["ws_port"]
    uri = f"ws://{ws_host}:{ws_port}"
    logger.info("Connecting to server %s:%s", ws_host, ws_port)
    player_id = uuid.uuid4().hex[:6]
    net = NetClient(uri, player_id, invite_code=invite_code, create_new=create_new)
    net.start()

    pause_menu = PauseMenu(engine.screen.get_width(), engine.screen.get_height())
    if len(pause_menu.menu_items) > 1:
        pause_menu.menu_items[1]["enabled"] = False
        pause_menu.menu_items[1]["text"] = "重新开始（不可用）"

    # 本地玩家
    p = Player(560, 600)
    p.hp = 100

    font = choose_font(22)
    font_big = choose_font(48)  # 用于游戏结束提示
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    last_send = 0.0
    running = True
    ui_state = "running"
    pending_zero_input = False
    while running:
        engine.begin_frame()
        dt = engine.clock.get_time() / 1000.0
        # 提前获取最新世界状态
        latest_world = net.get_world()
        world = latest_world
        players_snapshot = world.get("players", {})
        status_tag = world.get("status", "waiting")
        if status_tag != "running":
            seen_boss_ids.clear()
            last_boss_event_id = -1
            prev_enemy_ids.clear()
            exploded_enemies.clear()
            enemy_variants.clear()
            explosions.clear()
            paused_world_snapshot = None
            have_prev_enemy_snapshot = False
        all_players_dead = False
        if status_tag == "running" and players_snapshot:
            all_players_dead = True
            for pid, st in players_snapshot.items():
                if st.get("hp", 0) > 0:
                    all_players_dead = False
                    break
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if all_players_dead:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    continue

                if ui_state == "paused":
                    action = pause_menu.handle_key(event.key)
                    if action == "resume":
                        pause_menu.hide()
                        ui_state = "running"
                        pending_zero_input = False
                    elif action == "settings":
                        from game import settings

                        settings.run(as_child=True)
                        pause_menu.show()
                    elif action == "main_menu":
                        running = False
                    # 其余选项（如restart）在多人模式中不可用，忽略
                    continue

                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    pause_menu.show()
                    ui_state = "paused"
                    pending_zero_input = True
                    continue

        # 根据当前UI状态选择用于渲染的世界快照（暂停时冻结画面）
        if ui_state == "paused":
            if paused_world_snapshot is None:
                paused_world_snapshot = latest_world
            world = paused_world_snapshot
        else:
            world = latest_world
            paused_world_snapshot = None

        players_snapshot = world.get("players", {})
        status_tag = world.get("status", "waiting")
        all_players_dead = False
        if status_tag == "running" and players_snapshot:
            all_players_dead = True
            for pid, st in players_snapshot.items():
                if st.get("hp", 0) > 0:
                    all_players_dead = False
                    break

        if ui_state == "paused":
            move_x = 0.0
            move_y = 0.0
            want_fire = False
        else:
            keys = pygame.key.get_pressed()
            move_x = float(keys[pygame.K_d]) - float(keys[pygame.K_a])
            move_y = float(keys[pygame.K_s]) - float(keys[pygame.K_w])
            want_fire = keys[pygame.K_SPACE]

        # 获取世界状态以检查玩家是否死亡（已在事件循环中获取，这里复用）
        local_snapshot = players_snapshot.get(net.player_id, {})
        # 获取游戏状态（从world或status）
        status = net.get_status()
        status_tag = world.get("status") or status.get("status", "waiting")
        
        # 判断玩家是否死亡：
        # 1. 如果玩家状态为空（还没加入游戏），不视为死亡
        # 2. 如果游戏还没开始（waiting/countdown），不视为死亡
        # 3. 只有在游戏进行中（running）且HP <= 0时，才视为死亡
        is_local_dead = False  # 默认不死亡
        # 只有在游戏状态为 "running" 时才检查死亡
        if status_tag == "running":
            if local_snapshot:
                # 玩家状态存在，检查HP
                local_hp = local_snapshot.get("hp", 100)
                local_hp_max = local_snapshot.get("hp_max", 100)
                # 如果HP和HP_MAX都为0或未设置，可能是初始化问题，使用默认满血值
                if local_hp == 0 and local_hp_max == 0:
                    # 初始化问题，不视为死亡，使用默认满血值
                    is_local_dead = False
                elif local_hp <= 0 and local_hp_max > 0:
                    # HP <= 0 且 max_hp > 0，说明确实死亡了
                    is_local_dead = True
                else:
                    # HP > 0，玩家存活
                    is_local_dead = False
            # 如果玩家状态为空但游戏已开始，可能是连接问题，不视为死亡（等待状态同步）
            else:
                is_local_dead = False

        # 如果玩家死亡，无法移动和开火
        if not is_local_dead and ui_state != "paused":
            # 客户端预测：先按输入移动，服务器快照会校准
            p.rect.x += int(move_x * p.speed * dt)
            p.rect.y += int(move_y * p.speed * dt)

        # 边界
        w, h = engine.screen.get_width(), engine.screen.get_height()
        if p.rect.left < 0: p.rect.left = 0
        if p.rect.right > w: p.rect.right = w
        if p.rect.top < 0: p.rect.top = 0
        if p.rect.bottom > h: p.rect.bottom = h

        # 背景（从服务器同步，确保所有玩家看到相同的背景）
        server_bg_index = world.get("bg_index", 0)
        if server_bg_index != prev_bg_index and endless_bg_list:
            # 服务器背景索引变化，同步切换
            if prev_bg_index >= 0:
                bg_fading = True
                bg_fade_start = time.time()
                bg_next_idx = server_bg_index % len(endless_bg_list)
                bg_fade_surface = endless_bg_list[bg_next_idx].copy()
            else:
                bg_cur_idx = server_bg_index % len(endless_bg_list)
            prev_bg_index = server_bg_index
        
        now_bg = time.time()
        if endless_bg_list:
            # 更新淡入状态
            if bg_fading:
                fade_dur = 1.0
                t = (now_bg - bg_fade_start) / fade_dur
                if t >= 1.0:
                    bg_cur_idx = bg_next_idx
                    bg_fading = False
                    bg_fade_surface = None
            
            # 绘制当前底图
            base_bg = endless_bg_list[bg_cur_idx]
            engine.screen.blit(base_bg, (0, 0))
            # 正在淡入则叠加下一张
            if bg_fading and bg_fade_surface is not None:
                fade_dur = 1.0
                t = max(0.0, min(1.0, (now_bg - bg_fade_start) / fade_dur))
                alpha = int(t * 255)
                bg_fade_surface.set_alpha(alpha)
                engine.screen.blit(bg_fade_surface, (0, 0))
            engine.screen.blit(dim_overlay, (0, 0))
        elif bg_battle is not None:
            engine.screen.blit(bg_battle, (0, 0))
            engine.screen.blit(dim_overlay, (0, 0))
        
        # 记录Boss出场事件号，新事件未必立即有实体（作为兜底）
        boss_event_id = int(world.get("boss_spawn_event_id", 0))
        boss_event_triggered = False
        if boss_event_id != last_boss_event_id:
            boss_event_triggered = boss_event_id > 0
            last_boss_event_id = boss_event_id
        elif world.get("boss_spawned", False):
            boss_event_triggered = True
        
        # 检查道具拾取音效
        if world.get("prop_picked", False):
            assets.play_sound("prop/pickup.wav", 0.5)
        
        # 更新爆炸效果
        for ex in list(explosions):
            ex.update()
            if ex.done:
                explosions.remove(ex)

        # 检测敌机死亡并添加爆炸效果（基于服务器下发的唯一ID）
        current_enemy_map: dict[int, tuple] = {}
        for e in world.get("enemies", []):
            ex = int(e.get("x", 0))
            ey = int(e.get("y", 0))
            etype = e.get("type", "default")
            ew = int(e.get("w", 36))
            eh = int(e.get("h", 36))
            ehp = e.get("hp", 1)
            variant_net = e.get("variant")
            raw_id = int(e.get("id", 0))
            has_uid = raw_id != 0
            enemy_id = raw_id if has_uid else hash((ex, ey, etype, ew, eh))
            current_enemy_map[enemy_id] = (ex, ey, ew, eh, ehp, etype, variant_net, has_uid)
            if variant_net is not None:
                try:
                    enemy_variants[enemy_id] = int(variant_net)
                except (TypeError, ValueError):
                    pass

        # 通过检测新出现的Boss实体，确保每次出场都播放音效
        current_boss_ids = {
            enemy_id for enemy_id, data in current_enemy_map.items() if data[5] and data[5].upper() == "BOSS"
        }
        played_boss_sound = False
        for boss_id in current_boss_ids:
            if boss_id not in seen_boss_ids:
                assets.play_sound("fx/boss.wav", 0.9)
                seen_boss_ids.add(boss_id)
                played_boss_sound = True
        if seen_boss_ids:
            seen_boss_ids.intersection_update(current_boss_ids)
        if boss_event_triggered and not played_boss_sound:
            assets.play_sound("fx/boss.wav", 0.9)
        
        if have_prev_enemy_snapshot:
            # 检测消失的敌机（从prev中移除的）并添加爆炸效果
            for prev_key, prev_data in prev_enemy_ids.items():
                if prev_key not in current_enemy_map:
                    prev_has_uid = prev_data[7] if len(prev_data) > 7 else True
                    # 如果之前没有服务器分配的唯一ID（临时哈希），第一次同步到正式ID时忽略“消失”判定
                    if prev_key not in exploded_enemies and prev_has_uid:
                        prev_x, prev_y, prev_w, prev_h, _, _, _, _ = prev_data
                        ex_x = prev_x + prev_w // 2
                        ex_y = prev_y + prev_h // 2
                        explosions.append(Explosion(ex_x, ex_y, explosion_frames))
                        exploded_enemies.add(prev_key)
                        # 播放敌机死亡音效
                        assets.play_sound("fx/bomb.wav", 0.6)
                else:
                    # 检查HP从>0变为<=0的情况（敌机死亡）
                    _, _, _, _, prev_hp, _, _, _ = prev_data
                    _, _, _, _, curr_hp, _, _, _ = current_enemy_map[prev_key]
                    if prev_hp > 0 and curr_hp <= 0:
                        # 敌机死亡，添加爆炸效果（只播放一次）
                        if prev_key not in exploded_enemies:
                            prev_x, prev_y, prev_w, prev_h, _, _, _, _ = prev_data
                            ex_x = prev_x + prev_w // 2
                            ex_y = prev_y + prev_h // 2
                            explosions.append(Explosion(ex_x, ex_y, explosion_frames))
                            exploded_enemies.add(prev_key)
                            # 播放敌机死亡音效
                            assets.play_sound("fx/bomb.wav", 0.6)
            
            # 清理已不存在的敌机的爆炸记录（避免内存泄漏）
            exploded_enemies = {k for k in exploded_enemies if k in current_enemy_map or k in prev_enemy_ids}
        else:
            have_prev_enemy_snapshot = True

        prev_enemy_ids = current_enemy_map
        enemy_variants = {eid: enemy_variants[eid] for eid in prev_enemy_ids if eid in enemy_variants}
        if local_snapshot:
            p.rect.x = int(local_snapshot.get("x", p.rect.x))
            p.rect.y = int(local_snapshot.get("y", p.rect.y))

        for pid, st in players_snapshot.items():
            rx = int(st.get("x", 0))
            ry = int(st.get("y", 0))
            # 根据进化等级调整玩家尺寸
            evo_level = st.get("evo_level", 1)
            idx = min(4, max(0, evo_level - 1))
            player_size = [40, 44, 48, 52, 56][idx]
            rect = pygame.Rect(rx, ry, player_size, player_size)
            # 使用进化图片（与单人无尽模式一致）
            cur_player_img = ship_img
            if 0 <= idx < len(evo_ship_imgs) and evo_ship_imgs[idx] is not None:
                cur_player_img = evo_ship_imgs[idx]
            if cur_player_img is not None:
                engine.screen.blit(cur_player_img, rect)
            else:
                color = (80, 200, 255) if pid == net.player_id else (255, 220, 120)
                pygame.draw.rect(engine.screen, color, rect)
            hp = st.get("hp", 0)
            hp_max = max(1, st.get("hp_max", 1))
            ratio = max(0.0, min(1.0, hp / hp_max))
            pygame.draw.rect(engine.screen, (40, 40, 40), pygame.Rect(rect.x, rect.y - 8, rect.width, 4))
            pygame.draw.rect(engine.screen, (90, 220, 120), pygame.Rect(rect.x, rect.y - 8, int(rect.width * ratio), 4))

        # 玩家子弹（使用图片资源）
        for b in world.get("player_bullets", []):
            rect = pygame.Rect(int(b.get("x", 0)), int(b.get("y", 0)), int(b.get("w", 8)), int(b.get("h", 16)))
            # 检查是否有power buff（从本地玩家状态获取）
            use_plus = False
            if local_snapshot:
                buffs = local_snapshot.get("buffs", {})
                use_plus = buffs.get("power", 0) > now_bg
            img = bullet_img_plus if use_plus and bullet_img_plus is not None else bullet_img
            if img is not None:
                dst = img.get_rect(center=rect.center)
                engine.screen.blit(img, dst)
            else:
                pygame.draw.rect(engine.screen, (255, 245, 120), rect)

        # 敌机子弹（使用图片资源）
        for eb in world.get("enemy_bullets", []):
            rect = pygame.Rect(int(eb.get("x", 0)), int(eb.get("y", 0)), int(eb.get("w", 8)), int(eb.get("h", 16)))
            if enemy_bullet_img is not None:
                dst = enemy_bullet_img.get_rect(center=rect.center)
                engine.screen.blit(enemy_bullet_img, dst)
            else:
                pygame.draw.rect(engine.screen, (255, 110, 110), rect)

        for e in world.get("enemies", []):
            w = max(8, int(e.get("w", 36)))
            h = max(8, int(e.get("h", 36)))
            ex = int(e.get("x", 0))
            ey = int(e.get("y", 0))
            rect = pygame.Rect(ex, ey, w, h)
            enemy_id = int(e.get("id", 0) or 0)
            if enemy_id == 0:
                enemy_id = hash((ex, ey, w, h, e.get("type", "default")))
            # 根据服务器发送的敌机类型使用对应的多机型图片
            enemy_type_str = e.get("type", "default")
            surf = None
            try:
                if enemy_type_str != "default" and enemy_type_str:
                    enemy_type = None
                    for et in EnemyType:
                        if et.name == enemy_type_str.upper():
                            enemy_type = et
                            break
                    if enemy_type and enemy_type in enemy_images and enemy_images[enemy_type]:
                        img_list = enemy_images[enemy_type]
                        if img_list:
                            variant_idx = enemy_variants.get(enemy_id)
                            variant_net = e.get("variant")
                            if variant_net is not None:
                                try:
                                    variant_net = int(variant_net)
                                except (TypeError, ValueError):
                                    variant_net = None
                            if variant_net is not None:
                                if variant_idx != variant_net:
                                    variant_idx = max(0, variant_net) % len(img_list)
                                    enemy_variants[enemy_id] = variant_idx
                            if variant_idx is None:
                                seed = f"{enemy_id}-{enemy_type_str}"
                                variant_idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(img_list)
                                enemy_variants[enemy_id] = variant_idx
                            base_surf = img_list[variant_idx % len(img_list)]
                            key = (w, h, enemy_type_str, variant_idx)
                            surf = _enemy_img_cache.get(key)
                            if surf is None:
                                try:
                                    surf = pygame.transform.smoothscale(base_surf, (w, h))
                                except Exception:
                                    surf = None
                                if surf:
                                    _enemy_img_cache[key] = surf
            except Exception:
                pass
            
            # 如果没有找到对应机型图片，使用基础图片缩放
            if surf is None:
                key = (w, h)
                if enemy_base_img is not None:
                    surf = _enemy_img_cache.get(key)
                    if surf is None:
                        try:
                            surf = pygame.transform.smoothscale(enemy_base_img, (w, h))
                        except Exception:
                            surf = None
                        if surf:
                            _enemy_img_cache[key] = surf
            
            if surf is not None:
                engine.screen.blit(surf, rect)
            else:
                pygame.draw.rect(engine.screen, (255, 120, 120), rect, 1)
            hp = e.get("hp")
            hp_max = e.get("hp_max", hp or 1)
            if hp is not None and hp_max:
                ratio = max(0.0, min(1.0, hp / max(1, hp_max)))
                pygame.draw.rect(engine.screen, (60, 60, 60), pygame.Rect(rect.x, rect.y - 6, rect.width, 3))
                pygame.draw.rect(engine.screen, (255, 120, 120), pygame.Rect(rect.x, rect.y - 6, int(rect.width * ratio), 3))

        # 道具（使用图片资源）
        for pr in world.get("props", []):
            rect = pygame.Rect(int(pr.get("x", 0)), int(pr.get("y", 0)), 32, 32)
            kind = pr.get("kind", "")
            img = PROP_IMAGES.get(kind)
            if img is not None:
                engine.screen.blit(img, rect)
            else:
                color = PROP_SPECS.get(kind, {}).get("color", (220, 220, 220))
                pygame.draw.rect(engine.screen, color, rect, border_radius=6)
        
        # 绘制爆炸效果
        for ex in explosions:
            ex.draw(engine.screen)

        for c in world.get("coins", []):
            rect = pygame.Rect(int(c.get("x", 0)), int(c.get("y", 0)), 28, 28)
            if coin_img is not None:
                dst = coin_img.get_rect(center=rect.center)
                engine.screen.blit(coin_img, dst)
            else:
                pygame.draw.circle(engine.screen, (255, 220, 80), rect.center, rect.width // 2)

        # HUD（与单人无尽模式同步，并加上多人信息）
        status = net.get_status()
        fps = engine.clock.get_fps()
        # 如果游戏还没开始，不显示已用时间
        if status.get("status") == "running" and net.start_time > 0:
            elapsed = int(time.time() - net.start_time)
        else:
            elapsed = 0
        power_step = world.get("power_step", 0)
        status_tag = status.get("status", "waiting")
        countdown = status.get("countdown")
        # 获取房间码：优先从status获取，如果没有则从world获取，最后从net.meta_status获取
        invite_code = (status.get("invite_code") or 
                      world.get("invite_code") or 
                      net.meta_status.get("invite_code", "") or 
                      (net.invite_code if hasattr(net, 'invite_code') and net.invite_code else ""))
        # 确保是字符串类型
        invite_code = str(invite_code) if invite_code else ""
        remote_count = max(0, len(players_snapshot) - (1 if net.player_id in players_snapshot else 0))
        
        # 第一行：主要信息（与单人无尽模式格式一致）
        # 如果玩家状态为空，使用默认值（表示玩家还没加入或游戏还没开始）
        if not local_snapshot:
            # 玩家还没加入游戏，使用默认值
            local_hp = 100
            local_hp_max = 100
            local_score = 0
            evo_level = 1
            evo_coins = 0
            revives = 0
        else:
            # 玩家已加入，使用服务器返回的值
            local_hp = local_snapshot.get("hp", 100)
            local_hp_max = local_snapshot.get("hp_max", 100)
            # 如果HP和HP_MAX都为0或未设置，可能是初始化问题，使用默认满血值
            if local_hp == 0 and local_hp_max == 0:
                local_hp = 100  # PLAYER_MAX_HP
                local_hp_max = 100  # PLAYER_MAX_HP
            # 如果HP为0但max_hp > 0，说明玩家确实死亡了，保持HP为0
            # 如果HP > 0，使用服务器返回的值
            local_score = local_snapshot.get("score", 0)
            evo_level = local_snapshot.get("evo_level", 1)
            evo_coins = local_snapshot.get("evo_coins", 0)
            revives = local_snapshot.get("revives", 0)
        
        time_txt = f"无尽 Elapsed:{elapsed}s Step:{power_step}"
        if countdown is not None:
            time_txt += f"  倒计时:{countdown}s"
        hud_line1 = f"HP:{local_hp}/{local_hp_max}  Score:{local_score}  {time_txt}  FPS:{fps:.0f}  [P]暂停"
        font_small = choose_font(18)
        line1_surf = font_small.render(hud_line1, True, (220, 230, 255))
        engine.screen.blit(line1_surf, (12, 8))
        
        # 第二行：持续效果（buff）
        buffs_dict = local_snapshot.get("buffs", {})
        now_buff = time.time()
        active_buffs = []
        buff_labels_map = {
            "shield": "护盾",
            "piercing": "穿透",
            "spread": "散射",
            "haste": "连射",
            "power": "强化",
            "x2": "双倍得分",
        }
        for buff_name, end_time in buffs_dict.items():
            if isinstance(end_time, (int, float)) and end_time > now_buff:
                label = buff_labels_map.get(buff_name, buff_name)
                remain = int(end_time - now_buff)
                active_buffs.append(f"{label}({remain}s)")
        
        def wrap_items(items: list, per_line: int = 4) -> list:
            if not items:
                return []
            lines = []
            for i in range(0, len(items), per_line):
                lines.append("、".join(items[i:i+per_line]))
            return lines
        
        if active_buffs:
            # 每行最多4个
            wrapped = wrap_items(active_buffs, per_line=4)
            for idx, line_txt in enumerate(wrapped):
                prefix = "持续效果: " if idx == 0 else "           "
                buff_surf = font_small.render(prefix + line_txt, True, (220, 220, 220))
                engine.screen.blit(buff_surf, (12, 32 + idx * 20))
        else:
            buff_surf = font_small.render("持续效果: 无", True, (180, 180, 180))
            engine.screen.blit(buff_surf, (12, 32))
            wrapped = []
        
        # 第三行：统计信息
        y_cursor = 32 + (len(wrapped) if active_buffs else 1) * 20
        stats_txt = f"统计: 敌机 {len(world.get('enemies', []))}  敌弹 {len(world.get('enemy_bullets', []))}  掉落 {len(world.get('props', []))}"
        stats_surf = font_small.render(stats_txt, True, (205, 205, 205))
        engine.screen.blit(stats_surf, (12, y_cursor))
        
        # 第四行：进化币和多人信息
        y_cursor += 20
        if coin_img is not None:
            icon_rect = coin_img.get_rect(topleft=(12, y_cursor - 2))
            engine.screen.blit(coin_img, icon_rect)
            if evo_level >= 5:
                txt = font_small.render("已最终进化", True, (230, 230, 255))
            else:
                txt = font_small.render(f"x{evo_coins}/3 进化币", True, (235, 235, 180))
            engine.screen.blit(txt, (icon_rect.right + 6, icon_rect.top + 2))
            # 复活次数显示
            if revives > 0:
                rebirth_img = assets.load_image("ui/rebirth.png", size=(20, 20))
                if rebirth_img is not None:
                    rebirth_rect = rebirth_img.get_rect(topleft=(icon_rect.right + txt.get_width() + 20, y_cursor - 2))
                    engine.screen.blit(rebirth_img, rebirth_rect)
                    revive_txt = font_small.render(f"x{revives}", True, (255, 200, 200))
                    engine.screen.blit(revive_txt, (rebirth_rect.right + 4, rebirth_rect.top + 2))
        
        # 第五行：多人信息和连接状态
        y_cursor += 25
        conn_text = "已连接" if status["connected"] else "未连接"
        multi_info = f"多人: 房间码:{invite_code}  玩家数:{len(players_snapshot)}  远端:{remote_count}"
        multi_surf = font_small.render(multi_info, True, (200, 220, 240))
        engine.screen.blit(multi_surf, (12, y_cursor))
        
        # 错误信息
        if status.get("last_error") and not status["connected"]:
            err = font_small.render(f"错误:{status['last_error']}", True, (255, 120, 120))
            engine.screen.blit(err, (12, y_cursor + 20))
        
        # 玩家死亡提示（只在游戏进行中且玩家确实死亡时显示）
        if status_tag == "running" and is_local_dead:
            death_msg = font_small.render("你已死亡", True, (255, 100, 100))
            engine.screen.blit(death_msg, (12, y_cursor + 40))
        
        # 检查其他玩家死亡状态（只在游戏进行中）
        if status_tag == "running":
            for pid, st in players_snapshot.items():
                if pid != net.player_id and st.get("hp", 0) <= 0:
                    # 显示其他玩家死亡提示（在HUD下方）
                    other_death_y = y_cursor + 40
                    if is_local_dead:
                        other_death_y += 25
                    other_death_msg = font_small.render(f"玩家 {pid[:6]} 已死亡", True, (200, 150, 150))
                    engine.screen.blit(other_death_msg, (12, other_death_y))
        
        # 游戏结束提示（所有玩家都死亡，且游戏进行中）
        if status_tag == "running" and players_snapshot and all_players_dead:
            game_over_y = engine.screen.get_height() // 2 - 80
            game_over_surf = font_big.render("GAME OVER", True, (255, 120, 120))
            game_over_rect = game_over_surf.get_rect(center=(engine.screen.get_width() // 2, game_over_y))
            engine.screen.blit(game_over_surf, game_over_rect)
            
            hint = font_small.render("[ESC] 返回主菜单", True, (220, 220, 220))
            hint_rect = hint.get_rect(center=(engine.screen.get_width() // 2, game_over_y + 60))
            engine.screen.blit(hint, hint_rect)

        if ui_state == "paused":
            pause_menu.render(engine.screen, None)

        engine.end_frame()

        # 发送输入/状态（~30Hz）
        now = time.time()
        if now - last_send > 1 / 30:
            should_send = ui_state != "paused" or pending_zero_input
            if should_send:
                try:
                    loop.run_until_complete(net.send_input(move_x, move_y, bool(want_fire)))
                except Exception:
                    pass
                last_send = now
                if pending_zero_input:
                    pending_zero_input = False

    if as_child:
        assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)

    if not as_child:
        engine.quit()
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    run(as_child=False)


