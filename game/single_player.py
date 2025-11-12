import sys
import os
import time
import random
import math
import pygame
from typing import Optional

# allow running this file directly: add project root to sys.path
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.engine import Engine
from core.entities import Player, Enemy, Bullet
from core.collision import rect_collide
from utils.logger import get_logger
from data.dao import dao
from utils import assets
from game.enemy_ai import update_enemy_ai
from game.explosion import Explosion, load_explosion_frames
from game.props_system import PROP_SPECS, DROP_RATE, choose_prop_kind, buff_active, add_buff, cleanup_buffs, Prop
from game.shooting import create_player_bullets, compute_fire_cooldown
from game.hud import render_hud
from game.visual_effects import VisualEffectManager
from game.pause_menu import PauseMenu
# 无尽模式多机型系统
from game.enemy_types import load_enemy_images, EnemyType, choose_enemy_type, get_enemy_type_spec, scale_enemy_spec_for_power_step
from game.endless_spawner import EndlessSpawner
# settings_store 兼容包内/脚本直跑两种方式
try:
    from . import settings_store
except Exception:
    import game.settings_store as settings_store
from game import props_system as props_sys


logger = get_logger("single_player")


def run(as_child: bool = True, game_mode: str = "timed") -> None:
    engine = Engine()
    pygame.font.init()
    # 应用音频静音设置
    try:
        from utils import assets as _assets
        _assets.set_audio_config(muted=bool(settings_store.get_setting("muted", False)))
    except Exception:
        pass

    def choose_font(size: int, bold: bool = False):
        # Prefer CJK-capable fonts on Windows; fallback gracefully
        candidates = [
            "Microsoft YaHei", "微软雅黑", "SimHei", "黑体",
            "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans CN",
            "WenQuanYi Micro Hei",
        ]
        available = set(pygame.font.get_fonts())
        # pygame stores font names lowercased without spaces sometimes
        def key(name: str) -> str:
            return name.lower().replace(" ", "").replace("-", "")
        for name in candidates:
            if key(name) in available:
                return pygame.font.SysFont(name, size, bold=bold)
        return pygame.font.SysFont(None, size, bold=bold)

    font_small = choose_font(18, False)
    font_big = choose_font(36, False)

    # game states: 'menu' | 'running' | 'paused' | 'game_over'
    state = "menu"
    difficulty = "normal"  # 'easy' | 'normal' | 'hard' | 'custom'
    # game_mode 由主菜单传入：'timed' | 'endless'

    def diff_params(name: str):
        # 不同难度的基础参数（生成频率/速度/生命/掉落率/每批生成数量）
        if name == "easy":
            return {
                "spawn_interval": 3.0,
                "enemy_speed": 100.0,
                "player_hp": 120,
                "drop_heal": 0.35,
                "drop_x2": 0.10,
                "trickle_batch": 1,
                "enemy_cap": 24,
                "fire_interval": 3.0,
                "burst_max": 0,
                "burst_gap": 0.18,
            }
        if name == "hard":
            return {
                "spawn_interval": 1.8,
                "enemy_speed": 175.0,
                "player_hp": 90,
                "drop_heal": 0.15,
                "drop_x2": 0.15,
                "trickle_batch": 1,
                "enemy_cap": 42,
                "fire_interval": 1.6,
                "burst_max": 2,
                "burst_gap": 0.14,
            }
        if name == "custom":
            # 默认以 normal 为基线，自定义时会在下方覆盖
            return {
                "spawn_interval": 2.2,
                "enemy_speed": 145.0,
                "player_hp": 100,
                "drop_heal": 0.20,
                "drop_x2": 0.12,
                "trickle_batch": 1,
                "enemy_cap": 34,
                "fire_interval": 2.2,
                "burst_max": 1,
                "burst_gap": 0.16,
            }
        return {
            "spawn_interval": 2.4,
            "enemy_speed": 135.0,
            "player_hp": 100,
            "drop_heal": 0.20,
            "drop_x2": 0.12,
            "trickle_batch": 1,
            "enemy_cap": 28,
            "fire_interval": 2.6,
            "burst_max": 1,
            "burst_gap": 0.16,
        }

    params = diff_params(difficulty)
    # 仅“自定义模式”才应用设置覆盖与掉落调节
    if difficulty == "custom":
        overrides = settings_store.get_overrides()
        for k, v in overrides.items():
            if k in params:
                params[k] = v
        try:
            table_ov = settings_store.get_setting("drop_table", None)
            rate_ov = settings_store.get_setting("drop_rate", None)
            props_sys.set_drop_overrides(table_ov, rate_ov)
        except Exception:
            props_sys.set_drop_overrides()
    else:
        props_sys.set_drop_overrides()

    # load level waves
    import json
    levels_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "configs", "levels.json")
    try:
        with open(levels_path, "r", encoding="utf-8") as f:
            LEVELS = json.load(f)
    except Exception:
        LEVELS = {"single": {d: [] for d in ("easy", "normal", "hard")}}
    player = Player(600, 600)
    player.hp = params["player_hp"]
    bullets = []  # type: list[Bullet]
    class EnemyBullet:
        def __init__(self, x: int, y: int, vx: float, vy: float, speed: float = 360.0, color=(255,120,120), split_at: float = 0.0) -> None:
            self.rect = pygame.Rect(x, y, 8, 16)
            self.vx = vx
            self.vy = vy
            self.speed = speed
            self.color = color
            self.spawn = time.time()
            self.split_at = split_at  # seconds after spawn; 0 means no split
        def update(self, dt: float) -> None:
            self.rect.x += int(self.vx * self.speed * dt)
            self.rect.y += int(self.vy * self.speed * dt)
        def draw(self, surface: pygame.Surface) -> None:
            pygame.draw.rect(surface, self.color, self.rect)

    enemy_bullets: list[EnemyBullet] = []
    # 预加载敌机贴图（用于限时模式随机初始机型；无尽模式也会使用）
    enemy_images: dict = load_enemy_images()

    def create_random_enemy_at(x: int, y: int, power_step: int = 0) -> Enemy:
        # 选择机型并按当前增强步数调整规格（限时模式 power_step 默认为 0）
        etype = choose_enemy_type(power_step)
        spec = get_enemy_type_spec(etype)
        enhanced_spec = scale_enemy_spec_for_power_step(spec, power_step)
        e = Enemy(x, y, etype.value)
        e.enemy_type_enum = etype
        e.hp = enhanced_spec.hp
        e.max_hp = enhanced_spec.hp
        e.speed = enhanced_spec.speed_base
        e.rect.width = enhanced_spec.size[0]
        e.rect.height = enhanced_spec.size[1]
        e.score_value = enhanced_spec.score_value
        # 随机贴图（若有）
        imgs = enemy_images.get(etype) if enemy_images else None
        if imgs:
            import random as _r
            e.image = _r.choice(imgs)
        return e

    # 开局敌机：无尽模式不预放，限时模式随机三架机型
    if game_mode == "endless":
        enemies = []
    else:
        enemies = [
            create_random_enemy_at(200, 50, 0),
            create_random_enemy_at(600, 10, 0),
            create_random_enemy_at(1000, 100, 0),
        ]
    last_shot = 0.0
    spawn_interval = params["spawn_interval"]
    last_spawn = time.time()
    score = 0
    bullet_cap = 120
    enemy_cap = params["enemy_cap"]
    enemy_bullet_cap = 160
    # gameplay ext
    combo = 0
    combo_last_hit = 0.0
    combo_window = 2.0  # seconds to chain hits
    time_limit = 180  # seconds (timed mode only)
    start_time = time.time()
    # 无尽模式强化调度
    endless_step_interval = 20.0  # seconds
    last_step_time = start_time
    power_step = 0
    step_boss_summoned = False

    explosions: list[Explosion] = []

    buffs: dict[str, float] = {}

    def buff_active_local(key: str) -> bool:
        return buff_active(buffs, key)

    BASE_FIRE_COOLDOWN = 0.18
    BASE_BULLET_SPEED = 560.0
    BASE_BULLET_DAMAGE = 30.0
    BASE_BULLET_SIZE = (8, 16)
    BASE_PIERCE = 0
    
    # 进化系统常量（与多人模式同步）
    EVO_ATTACK_SPEED_MULTS = [1.0, 1.10, 1.20, 1.35, 1.50]  # 1-5阶攻击速度倍数
    EVO_DAMAGE_MULTS = [1.0, 1.10, 1.20, 1.35, 1.50]  # 1-5阶伤害倍数
    EVO_PIERCE_BONUS = [0, 0, 1, 1, 2]  # 1-5阶穿透加成

    # 玩家与机体（敌机/Boss）接触伤害的节流（避免每帧多次扣血）
    CONTACT_DAMAGE_COOLDOWN = 0.6  # seconds
    last_contact_damage_time: float = 0.0

    # 无尽进化参数（仅无尽使用）：每3步+1阶，至5阶
    evolution_level: int = 1  # 1..5
    evo_fire_mult = [1.0, 1.10, 1.20, 1.35, 1.50]
    evo_damage_mult = [1.0, 1.10, 1.20, 1.35, 1.50]
    evo_pierce_bonus = [0, 0, 1, 1, 2]

    # 无尽曲线自适应：记录上一步用时，动态调节敌速增幅
    last_step_duration: float = 0.0
    enemy_speed_step_mult: float = 1.08  # >35s 时降为 1.06
    # 精英小队生成节流
    elite_next_time: float = start_time + 6.0


    PROP_SPECS = {
        "heal": {"type": "instant", "color": (120, 255, 140)},
        "x2": {"type": "buff", "duration": 8.0, "color": (255, 215, 120)},
        "shield": {"type": "buff", "duration": 8.0, "color": (140, 210, 255)},
        "piercing": {"type": "buff", "duration": 8.0, "color": (255, 150, 150), "pierce": 2},
        "spread": {"type": "buff", "duration": 8.0, "color": (250, 130, 255)},
        "haste": {"type": "buff", "duration": 8.0, "color": (170, 240, 255)},
        "power": {"type": "buff", "duration": 8.0, "color": (255, 110, 90)},
        "clearscreen": {"type": "instant", "color": (255, 240, 160)},
    }

    DROP_TABLE = {
        "easy": [
            ("heal", 40),
            ("x2", 28),
            ("haste", 24),
            ("power", 24),
            ("spread", 22),
            ("piercing", 20),
            ("shield", 15),
            ("clearscreen", 6),
        ],
        "normal": [
            ("heal", 32),
            ("x2", 26),
            ("haste", 26),
            ("power", 26),
            ("spread", 24),
            ("piercing", 22),
            ("shield", 16),
            ("clearscreen", 8),
        ],
        "hard": [
            ("heal", 26),
            ("x2", 24),
            ("haste", 24),
            ("power", 24),
            ("spread", 22),
            ("piercing", 22),
            ("shield", 18),
            ("clearscreen", 10),
        ],
    }

    # 使用 props_system 提供的 Buff/掉落逻辑
    
    # 视觉特效管理器
    visual_effects = VisualEffectManager()
    
    # 暂停菜单
    pause_menu = PauseMenu(engine.screen.get_width(), engine.screen.get_height())
    
    # 无尽模式多机型系统
    endless_spawner: Optional[EndlessSpawner] = None
    if game_mode == "endless":
        # 生成器使用已预加载的贴图
        endless_spawner = EndlessSpawner(engine.screen.get_width(), enemy_images)

    def clear_screen() -> None:
        nonlocal enemies, enemy_bullets, score, explosions, evolution_level
        if enemies:
            for e in enemies:
                # 结算爆炸与得分
                explosions.append(Explosion(e.rect.centerx, e.rect.centery, explosion_frames))
                score += 20
                # 若为无尽，通知生成器（修复清屏后Boss未进入下一轮的问题）
                if game_mode == "endless" and endless_spawner is not None:
                    # 在清屏时也应触发Boss死亡流程
                    is_boss = hasattr(e, "enemy_type_enum") and e.enemy_type_enum == EnemyType.BOSS
                    endless_spawner.on_enemy_killed(e)
                    # 无尽：Boss清屏死亡时也按规则掉落进化币（若未最终进化）
                    if game_mode == "endless" and is_boss and evolution_level < 5:
                        coins.append(Coin(e.rect.centerx, e.rect.centery, 1))
            enemies = []
        if enemy_bullets:
            enemy_bullets.clear()
        assets.play_sound("fx/bomb.wav", 0.8)

    # explosion frames
    explosion_frames = load_explosion_frames()
    explosions: list[Explosion] = []

    # assets (optional, graceful fallback)
    # 背景图（自适应窗口尺寸）
    bg_size = (engine.screen.get_width(), engine.screen.get_height())
    bg_battle = assets.load_image("backgrounds/backgroundbattle.png", size=bg_size)
    # 无尽模式多背景：支持直接放置 battle1.jpg、battle2.jpg、battle3.jpg、battle4.jpg
    endless_bg_list: list = []
    for _name in ("battle1.jpg", "battle2.jpg", "battle3.jpg", "battle4.jpg"):
        _surf = assets.load_image(f"backgrounds/{_name}", size=bg_size)
        if _surf is not None:
            endless_bg_list.append(_surf)
    # 背景切换状态（无尽模式）
    bg_cur_idx: int = 0
    bg_fading: bool = False
    bg_fade_start: float = 0.0
    bg_next_idx: int = 0
    bg_fade_surface: Optional[pygame.Surface] = None
    bg_switch_interval: float = 20.0  # 每 20s 切换一次
    bg_next_switch_time: float = 0.0
    # 先渲染一帧 Loading，避免黑屏无提示
    engine.screen.fill((0, 0, 0))
    loading_font = pygame.font.SysFont(None, 28, bold=True)
    loading_txt = loading_font.render("Loading assets...", True, (200, 220, 255))
    engine.screen.blit(loading_txt, (engine.screen.get_width()//2 - loading_txt.get_width()//2, engine.screen.get_height()//2 - 14))
    pygame.display.flip()
    # 无尽模式背景切换已移除，如需多背景请直接提供独立文件
    dim_overlay = pygame.Surface(bg_size, pygame.SRCALPHA)
    dim_overlay.fill((0, 0, 0, 55))
    ship_img = assets.load_image("player/player_ship.png", size=(40, 40))
    # 无尽进化用玩家贴图（若缺失则回退到 ship_img）
    evo_ship_imgs = [
        assets.load_image("player/roleplane1.png", size=(40, 40)),
        assets.load_image("player/roleplane2.png", size=(44, 44)),
        assets.load_image("player/roleplane3.png", size=(48, 48)),
        assets.load_image("player/roleplane4.png", size=(52, 52)),
        assets.load_image("player/roleplane5.png", size=(56, 56)),
    ]
    # 多人模式素材：无尽模式使用与多人模式相同的渲染方式
    enemy_base_img = assets.load_image("enemy/enemy_basic.png")
    _enemy_img_cache: dict[tuple[int, int], Optional[pygame.Surface]] = {}
    # 子弹静态贴图（按方向与尺寸预处理）
    # 再放大并适度拉长，便于观感与识别（可按需继续微调）
    player_size = (56, 42)         # 普通子弹（更长一些）
    player_plus_size = (28, 62)    # 强化子弹（更大更长）
    enemy_size = (56, 36)          # 敌机子弹（略放大加长）
    # 玩家普通子弹（朝上）
    bullet_img = assets.load_image("bullet/bullet_role.png", size=player_size)
    if bullet_img is not None:
        bullet_img = pygame.transform.rotate(bullet_img, 90)
    # 玩家强化子弹（朝上）
    bullet_img_plus = assets.load_image("bullet/bullet_role_plus.png", size=player_plus_size)
    if bullet_img_plus is not None:
        bullet_img_plus = pygame.transform.rotate(bullet_img_plus, -205)
    # 敌机子弹（朝下）
    enemy_bullet_img = assets.load_image("bullet/bullet_enemy.png", size=enemy_size)
    if enemy_bullet_img is not None:
        # 使其朝下：采用 +90°（逆时针）
        enemy_bullet_img = pygame.transform.rotate(enemy_bullet_img, 90)
    enemy_img = assets.load_image("enemy/enemy_basic.png", size=(36, 36))
    prop_heal_img = assets.load_image("prop/prop_heal.png", size=(32, 32))
    prop_x2_img = assets.load_image("prop/prop_x2.png", size=(32, 32))
    prop_shield_img = assets.load_image("prop/prop_shield.png", size=(32, 32))
    prop_piercing_img = assets.load_image("prop/prop_piercing.png", size=(32, 32))
    prop_spread_img = assets.load_image("prop/prop_spread.png", size=(32, 32))
    prop_haste_img = assets.load_image("prop/prop_haste.png", size=(32, 32))
    prop_power_img = assets.load_image("prop/prop_power.png", size=(32, 32))
    prop_clear_img = assets.load_image("prop/prop_clearscreen.png", size=(32, 32))
    assets.play_bgm("bgm/battle.ogg", volume=0.35, loop=True)
    # 复活与进化效果资源（进化动画采用程序化特效，不再使用GIF）
    rebirth_img = assets.load_image("ui/rebirth.png", size=(32, 32))  # 放大一些，HUD更清晰
    sfx_shoot = assets.load_sound("player/shoot.wav", 0.5)
    sfx_pick = assets.load_sound("prop/pickup.wav", 0.6)
    sfx_expl = assets.load_sound("fx/bomb.wav", 0.6)
    sfx_over = assets.load_sound("ui/game_over.wav", 0.6)

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

    props: list[Prop] = []

    # 无尽模式：金币实体（进化币）
    class Coin:
        def __init__(self, x: int, y: int, value: int = 1) -> None:
            self.rect = pygame.Rect(x - 16, y - 16, 32, 32)
            self.value = value
            self.spawn = time.time()
            self.ttl = 20.0
        def draw(self, surf: pygame.Surface, img: Optional[pygame.Surface]) -> None:
            if img is not None:
                dst = img.get_rect(center=self.rect.center)
                surf.blit(img, dst)
            else:
                pygame.draw.circle(surf, (255, 215, 0), self.rect.center, 12)

    coins: list[Coin] = []
    # 无尽模式使用与多人模式相同的金币尺寸
    coin_img = assets.load_image("prop/coin.png", size=(26, 26))
    evo_coin_count: int = 0  # 无尽进化币计数（集齐3个进化一次）
    rebirth_count: int = 0   # 最终形态（5阶）奖励一次复活
    evolve_effect_until: float = 0.0  # 进化特效显示到何时

    def active_buff_labels() -> list[str]:
        labels = []
        now = time.time()
        label_map = {
            "shield": "护盾",
            "piercing": "穿透",
            "spread": "散射",
            "haste": "连射",
            "power": "强化",
            "x2": "双倍得分",
        }
        for key, label in label_map.items():
            end_at = buffs.get(key)
            if end_at and end_at > now:
                remain = int(end_at - now)
                labels.append(f"{label} {remain}s")
        return labels

    def wrap_items(items: list[str], per_line: int = 4) -> list[str]:
        if not items:
            return []
        lines: list[str] = []
        for i in range(0, len(items), per_line):
            lines.append("、".join(items[i:i+per_line]))
        return lines

    running = True
    # 敌机射击节流（按敌机维度）
    enemy_fire_state: dict[int, dict[str, float]] = {}
    while running:
        engine.begin_frame()
        dt = engine.clock.get_time() / 1000.0
        cleanup_buffs(buffs)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # global ESC: 在游戏进行中用于暂停，其他状态用于返回上一级
                if event.key == pygame.K_ESCAPE:
                    if state == "running":
                        # 游戏进行中：ESC 和 P 一样都是暂停
                        state = "paused"
                        pause_menu.show()
                        continue
                    elif state == "paused":
                        # 暂停状态：ESC 由暂停菜单处理（继续游戏）
                        action = pause_menu.handle_key(event.key)
                        if action == "resume":
                            state = "running"
                            pause_menu.hide()
                        elif action == "restart":
                            # 重新开始游戏
                            player = Player(600, 600)
                            player.hp = params["player_hp"]
                            bullets.clear()
                            # 重新开始：无尽模式不预放，限时模式随机三架机型
                            if game_mode == "endless":
                                enemies = []
                            else:
                                enemies = [
                                    create_random_enemy_at(200, 50, 0),
                                    create_random_enemy_at(600, 10, 0),
                                    create_random_enemy_at(1000, 100, 0),
                                ]
                            last_shot = 0.0
                            spawn_interval = params["spawn_interval"]
                            last_spawn = time.time()
                            score = 0
                            combo = 0
                            combo_last_hit = 0.0
                            state = "running"
                            waves = [] if game_mode == "endless" else list(LEVELS.get("single", {}).get(difficulty, []))
                            wave_index = 0
                            spawned_flags = [False] * len(waves)
                            enemy_bullets.clear()
                            enemy_fire_state.clear()
                            start_time = time.time()
                            last_step_time = start_time
                            power_step = 0
                            step_boss_summoned = False
                            visual_effects.reset()  # 重置特效
                            pause_menu.hide()
                            if game_mode == "endless":
                                bg_cur_idx = 0
                                bg_fading = False
                                bg_next_switch_time = time.time() + bg_switch_interval
                        elif action == "settings":
                            # 打开设置
                            from game import settings
                            settings.run(as_child=True)
                            pause_menu.show()  # 设置关闭后重新显示暂停菜单
                        elif action == "main_menu":
                            state = "menu"
                            pause_menu.hide()
                            running = False  # 返回主菜单
                        continue
                    elif state == "game_over":
                        # 结束界面按 ESC 返回单人模式内部菜单
                        state = "menu"
                        continue
                    elif state == "menu":
                        # 从单人模式内部菜单返回主菜单
                        running = False
                        continue
                elif state == "menu":
                    # 限时模式可选难度；无尽不处理 1-4
                    if game_mode == "timed" and event.key == pygame.K_1:
                        difficulty = "easy"; params = diff_params(difficulty)
                        props_sys.set_drop_overrides()  # 重置为默认掉落
                    elif game_mode == "timed" and event.key == pygame.K_2:
                        difficulty = "normal"; params = diff_params(difficulty)
                        props_sys.set_drop_overrides()  # 重置为默认掉落
                    elif game_mode == "timed" and event.key == pygame.K_3:
                        difficulty = "hard"; params = diff_params(difficulty)
                        props_sys.set_drop_overrides()  # 重置为默认掉落
                    elif game_mode == "timed" and event.key == pygame.K_4:
                        difficulty = "custom"; params = diff_params(difficulty)
                        overrides = settings_store.get_overrides()
                        for k, v in overrides.items():
                            if k in params:
                                params[k] = v
                        # 应用自定义掉落表和掉落率
                        try:
                            table_ov = settings_store.get_setting("drop_table", None)
                            rate_ov = settings_store.get_setting("drop_rate", None)
                            props_sys.set_drop_overrides(table_ov, rate_ov)
                        except Exception:
                            props_sys.set_drop_overrides()
                    elif event.key == pygame.K_h:
                        # 历史榜开关切换
                        opened = getattr(run, "_hist_open", False)
                        if not opened:
                            try:
                                import asyncio
                                mode_str = f"single_{game_mode}"
                                records_all = asyncio.run(dao.list_recent_records(24))
                                records = [r for r in records_all if r.get("mode") == mode_str][:8]
                            except RuntimeError:
                                records = []
                            setattr(run, "_hist_cache", records)
                            setattr(run, "_hist_cache_time", time.time())
                            setattr(run, "_hist_open", True)
                        else:
                            setattr(run, "_hist_open", False)
                    elif event.key == pygame.K_RETURN:
                        # reset and start
                        player = Player(600, 600)
                        player.hp = params["player_hp"]
                        bullets.clear()
                        if game_mode == "endless":
                            enemies = []
                        else:
                            enemies = [
                                create_random_enemy_at(200, 50, 0),
                                create_random_enemy_at(600, 10, 0),
                                create_random_enemy_at(1000, 100, 0),
                            ]
                        last_shot = 0.0
                        spawn_interval = params["spawn_interval"]
                        last_spawn = time.time()
                        score = 0
                        state = "running"
                        # waves state
                        waves = [] if game_mode == "endless" else list(LEVELS.get("single", {}).get(difficulty, []))
                        wave_index = 0
                        spawned_flags = [False] * len(waves)
                        enemy_bullets.clear()
                        enemy_fire_state.clear()
                        # endless mode runtime init
                        start_time = time.time()
                        last_step_time = start_time
                        power_step = 0
                        step_boss_summoned = False
                        # 无尽模式背景初始化
                        if game_mode == "endless":
                            bg_cur_idx = 0
                            bg_fading = False
                            bg_next_switch_time = time.time() + bg_switch_interval
                elif state == "running":
                    # P 键也可以暂停（ESC 已在上面处理）
                    if event.key == pygame.K_p:
                        state = "paused"
                        pause_menu.show()
                elif state == "paused":
                    # 暂停状态下的按键处理（ESC 已在上面处理，这里处理其他按键）
                    if event.key != pygame.K_ESCAPE:  # ESC 已在上面处理
                        action = pause_menu.handle_key(event.key)
                        if action == "resume":
                            state = "running"
                            pause_menu.hide()
                        elif action == "restart":
                            # 重新开始游戏
                            player = Player(600, 600)
                            player.hp = params["player_hp"]
                            bullets.clear()
                            if game_mode == "endless":
                                enemies = []
                            else:
                                enemies = [
                                    create_random_enemy_at(200, 50, 0),
                                    create_random_enemy_at(600, 10, 0),
                                    create_random_enemy_at(1000, 100, 0),
                                ]
                            last_shot = 0.0
                            spawn_interval = params["spawn_interval"]
                            last_spawn = time.time()
                            score = 0
                            combo = 0
                            combo_last_hit = 0.0
                            state = "running"
                            waves = [] if game_mode == "endless" else list(LEVELS.get("single", {}).get(difficulty, []))
                            wave_index = 0
                            spawned_flags = [False] * len(waves)
                            enemy_bullets.clear()
                            enemy_fire_state.clear()
                            start_time = time.time()
                            last_step_time = start_time
                            power_step = 0
                            visual_effects.reset()  # 重置特效
                            pause_menu.hide()
                            if game_mode == "endless":
                                bg_cur_idx = 0
                                bg_fading = False
                                bg_next_switch_time = time.time() + bg_switch_interval
                        elif action == "settings":
                            # 打开设置
                            from game import settings
                            settings.run(as_child=True)
                            pause_menu.show()  # 设置关闭后重新显示暂停菜单
                        elif action == "main_menu":
                            state = "menu"
                            pause_menu.hide()
                            running = False  # 返回主菜单
                elif state == "game_over":
                    if event.key == pygame.K_r:
                        state = "menu"

        keys = pygame.key.get_pressed()

        if state == "running":
            # input & movement（支持键位方案切换）
            scheme = settings_store.get_setting("key_scheme", "wasd")
            if scheme == "arrows":
                dx = dy = 0.0
                if keys[pygame.K_UP]: dy -= player.speed * dt
                if keys[pygame.K_DOWN]: dy += player.speed * dt
                if keys[pygame.K_LEFT]: dx -= player.speed * dt
                if keys[pygame.K_RIGHT]: dx += player.speed * dt
                player.rect.x += int(dx)
                player.rect.y += int(dy)
            else:
                player.handle_input(keys, dt)
            # clamp to window
            w, h = engine.screen.get_width(), engine.screen.get_height()
            if player.rect.left < 0: player.rect.left = 0
            if player.rect.right > w: player.rect.right = w
            if player.rect.top < 0: player.rect.top = 0
            if player.rect.bottom > h: player.rect.bottom = h

        # 辅助：Boss击杀后立即刷新背景（避免闪屏）
        def _trigger_bg_switch_immediately() -> None:
            nonlocal bg_cur_idx, bg_fading, bg_fade_start, bg_next_idx, bg_fade_surface, bg_next_switch_time
            if len(endless_bg_list) < 2 or bg_fading:
                return
            if len(endless_bg_list) == 2:
                bg_next_idx = 1 - bg_cur_idx
            else:
                import random as _r
                candidates = [i for i in range(len(endless_bg_list)) if i != bg_cur_idx]
                bg_next_idx = _r.choice(candidates)
            bg_fading = True
            bg_fade_start = time.time()
            try:
                bg_fade_surface = endless_bg_list[bg_next_idx].convert_alpha()
                bg_fade_surface.set_alpha(0)
            except Exception:
                bg_fade_surface = None
                bg_fading = False
            bg_next_switch_time = time.time() + bg_switch_interval

        # 无尽：到达步点召唤Boss；Boss被击杀后才进入下一步并刷新场景/结算
        if state == "running" and game_mode == "endless":
            now_step = time.time()
            # 达到步点：若未召唤Boss且当前没有Boss，则立即召唤Boss（等待击杀再进下一步）
            if (now_step - last_step_time >= endless_step_interval) and (endless_spawner is not None) and (not endless_spawner.has_boss()) and (not step_boss_summoned):
                boss, boss_controller = endless_spawner.spawn_boss(power_step)
                # Boss HP 指数增强（按步数）
                try:
                    scale = 1.25 ** max(0, power_step)
                    boss.hp = int(boss.hp * scale)
                    boss.max_hp = int(boss.max_hp * scale)
                except Exception:
                    pass
                enemies.append(boss)
                assets.play_sound("fx/boss.wav", 0.9)
                step_boss_summoned = True

        # firing
        now = time.time()
        if state == "running":
            # 计算基础冷却时间
            base_cooldown = compute_fire_cooldown(BASE_FIRE_COOLDOWN, buffs)
            
            # 无尽模式：应用进化等级对攻击速度的影响
            if game_mode == "endless":
                level = max(1, min(5, evolution_level))
                base_cooldown /= EVO_ATTACK_SPEED_MULTS[level - 1]
            
            fire_cooldown = base_cooldown
            
            if (
                keys[pygame.K_SPACE]
                and now - last_shot > fire_cooldown
                and len(bullets) < bullet_cap
            ):
                # 计算伤害：基础伤害 * 进化倍数
                dmg = BASE_BULLET_DAMAGE
                if game_mode == "endless":
                    level = max(1, min(5, evolution_level))
                    dmg *= EVO_DAMAGE_MULTS[level - 1]
                
                new_bs = create_player_bullets(player, buffs, BASE_BULLET_SPEED, dmg, BASE_BULLET_SIZE)
                
                # 应用穿透加成
                pierce_bonus = 0
                if game_mode == "endless":
                    level = max(1, min(5, evolution_level))
                    pierce_bonus = EVO_PIERCE_BONUS[level - 1]
                
                if pierce_bonus > 0:
                    for b in new_bs:
                        b.pierce = max(0, getattr(b, "pierce", 0) + pierce_bonus + BASE_PIERCE)
                
                # 无尽进化3阶起：每一形态额外+1发散弹（3阶+1、4阶+2、5阶+3）
                if game_mode == "endless" and evolution_level >= 3:
                    from core.entities import Bullet as _B
                    base_angle = math.radians(-90)  # 向上
                    extra = max(0, min(3, evolution_level - 2))  # 1..3
                    # 预设角度分布（度数）
                    angle_sets = {
                        1: [-10],
                        2: [-12, 12],
                        3: [-16, 0, 16],
                    }
                    for deg in angle_sets.get(extra, []):
                        ang = base_angle + math.radians(deg)
                        vx, vy = math.cos(ang), math.sin(ang)
                        new_bullet = _B(
                            player.rect.centerx, 
                            player.rect.top - 8, 
                            width=8, 
                            height=16, 
                            speed=BASE_BULLET_SPEED, 
                            vx=vx, 
                            vy=vy, 
                            damage=dmg, 
                            pierce=pierce_bonus
                        )
                        new_bs.append(new_bullet)
                
                if len(bullets) + len(new_bs) <= bullet_cap:
                    bullets.extend(new_bs)
                    last_shot = now
                    assets.play_sound("player/shoot.wav", 0.5)

        # enemy spawner (waves + fallback)
        if state == "running":
            if game_mode == "endless" and endless_spawner is not None:
                # 无尽模式：使用多机型生成系统
                # 检查是否需要生成Boss
                if endless_spawner.should_spawn_boss(power_step):
                    boss, boss_controller = endless_spawner.spawn_boss(power_step)
                    # Boss HP 指数增强（按步数）
                    try:
                        scale = 1.25 ** max(0, power_step)
                        boss.hp = int(boss.hp * scale)
                        boss.max_hp = int(boss.max_hp * scale)
                    except Exception:
                        pass
                    enemies.append(boss)
                
                # 生成普通敌机（如果有Boss则不生成）
                if not endless_spawner.has_boss() and len(enemies) < enemy_cap:
                    # 常规刷怪（受 spawn_interval 限制）
                    new_enemy = endless_spawner.spawn_enemy(power_step, spawn_interval, enemy_cap)
                    if new_enemy is not None:
                        enemies.append(new_enemy)
                # 精英小队：不要依赖上面 new_enemy 是否生成成功，独立触发
                if not endless_spawner.has_boss():
                    now_e = time.time()
                    if now_e >= elite_next_time:
                        import random as _r, math as _m
                        squad = min(7, 3 + power_step // 2)
                        w = engine.screen.get_width()
                        base_y = -48
                        formation = _r.choice(["line", "v", "snake", "column", "arc", "stagger"])
                        # 根据可用空位裁剪小队规模
                        available = max(0, enemy_cap - len(enemies))
                        squad = max(0, min(squad, available))
                        if squad <= 0:
                            elite_next_time = now_e + 4.0
                        else:
                            spawned = 0
                        if formation == "line":
                            spacing = max(48, w // (squad + 1))
                            for i in range(squad):
                                x = spacing * (i + 1)
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x
                                    e2.rect.y = base_y - i * 12
                                    e2.speed *= 1.10
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "v":
                            center = w // 2
                            dx = max(36, w // 14)
                            for i in range(squad):
                                offset = (i - (squad - 1) / 2.0)
                                x = center + int(offset * dx)
                                y = base_y - int(abs(offset) * 20)
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = max(24, min(w - 24, x))
                                    e2.rect.y = y
                                    e2.speed *= 1.12
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "snake":
                            amp = max(40, w // 10)
                            phase = _r.random() * _m.pi * 2
                            for i in range(squad):
                                t = i / max(1, (squad - 1))
                                x = int(w * (0.15 + 0.7 * t))
                                y = base_y - int(_m.sin(phase + t * _m.pi * 1.5) * amp * 0.2 * (1 + t))
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x
                                    e2.rect.y = y
                                    e2.speed *= 1.08
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "column":  # 纵列
                            x = w // 2
                            for i in range(squad):
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x + (i - squad // 2) * 18
                                    e2.rect.y = base_y - i * 24
                                    e2.speed *= 1.12
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "arc":
                            # 半圆弧阵：以屏幕中心为圆心，从 -60° 到 +60° 均匀布点
                            cx, cy = w // 2, base_y - 20
                            for i in range(squad):
                                t = -_m.pi/3 + (2*_m.pi/3) * (i / max(1, squad - 1))
                                r = max(80, w // 5)
                                x = int(cx + _m.cos(t) * r)
                                y = int(cy + _m.sin(t) * r * 0.5)
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = max(24, min(w - 24, x))
                                    e2.rect.y = y
                                    e2.speed *= 1.10
                                    enemies.append(e2)
                                    spawned += 1
                        else:  # stagger 交错阵（棋盘式）
                            cols = max(2, min(3, squad // 2))
                            rows = (squad + cols - 1) // cols
                            spacing_x = w // (cols + 1)
                            for r in range(rows):
                                for c in range(cols):
                                    idx = r * cols + c
                                    if idx >= squad:
                                        break
                                    x = spacing_x * (c + 1) + (r % 2) * 24
                                    y = base_y - r * 20
                                    e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                    if e2 is not None:
                                        e2.rect.x = x
                                        e2.rect.y = y
                                        e2.speed *= 1.09
                                        enemies.append(e2)
                                        spawned += 1
                        elite_next_time = now_e + max(3.5, 9.0 - power_step * 0.5)
                
                # 更新Boss（如果有）
                if endless_spawner.has_boss():
                    boss_controller = endless_spawner.get_boss_controller()
                    if boss_controller is not None:
                        boss_bullets = boss_controller.update(dt, engine.screen.get_width())
                        enemy_bullets.extend(boss_bullets)
                # 步点召唤Boss逻辑与无尽相同（已在上方实现）；此处仅生成普通敌机
                if not endless_spawner.has_boss() and len(enemies) < enemy_cap:
                    new_enemy = endless_spawner.spawn_enemy(power_step, spawn_interval, enemy_cap)
                    if new_enemy is not None:
                        enemies.append(new_enemy)
                # 精英小队（提高密度，含队形）
                if not endless_spawner.has_boss():
                    now_e = time.time()
                    if now_e >= elite_next_time:
                        import random as _r, math as _m
                        squad = min(5, 3 + power_step // 3)
                        w = engine.screen.get_width()
                        base_y = -48
                        formation = _r.choice(["line", "v", "snake", "column"])
                        available = max(0, enemy_cap - len(enemies))
                        squad = max(0, min(squad, available))
                        if squad <= 0:
                            elite_next_time = now_e + 4.0
                        else:
                            spawned = 0
                        if formation == "line":
                            spacing = max(48, w // (squad + 1))
                            for i in range(squad):
                                x = spacing * (i + 1)
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x
                                    e2.rect.y = base_y - i * 12
                                    e2.speed *= 1.08
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "v":
                            center = w // 2
                            dx = max(36, w // 14)
                            for i in range(squad):
                                offset = (i - (squad - 1) / 2.0)
                                x = center + int(offset * dx)
                                y = base_y - int(abs(offset) * 20)
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = max(24, min(w - 24, x))
                                    e2.rect.y = y
                                    enemies.append(e2)
                                    spawned += 1
                        elif formation == "snake":
                            amp = max(40, w // 10)
                            phase = _r.random() * _m.pi * 2
                            for i in range(squad):
                                t = i / max(1, (squad - 1))
                                x = int(w * (0.15 + 0.7 * t))
                                y = base_y - int(_m.sin(phase + t * _m.pi * 1.5) * amp * 0.2 * (1 + t))
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x
                                    e2.rect.y = y
                                    e2.speed *= 1.05
                                    enemies.append(e2)
                                    spawned += 1
                        else:  # column 纵列
                            x = w // 2
                            for i in range(squad):
                                e2 = endless_spawner.spawn_enemy(power_step, 0.0, enemy_cap)
                                if e2 is not None:
                                    e2.rect.x = x + (i - squad // 2) * 18
                                    e2.rect.y = base_y - i * 24
                                    e2.speed *= 1.12
                                    enemies.append(e2)
                                    spawned += 1
                        if spawned > 0:
                            elite_banner_text = f"精英小队 {formation.upper()} x{spawned}"
                            elite_banner_until = now_e + 2.0
                            try:
                                assets.play_sound("ui/menu_move.wav", 0.4)
                            except Exception:
                                pass
                        elite_next_time = now_e + max(4.0, 10.0 - power_step * 0.5)
                if endless_spawner.has_boss():
                    boss_controller = endless_spawner.get_boss_controller()
                    if boss_controller is not None:
                        boss_bullets = boss_controller.update(dt, engine.screen.get_width())
                        enemy_bullets.extend(boss_bullets)
            else:
                # 限时模式：使用原有生成逻辑
                t_elapsed = time.time() - start_time
                # schedule waves
                if 'waves' in locals():
                    for idx, wv in enumerate(waves):
                        if not spawned_flags[idx] and t_elapsed >= float(wv.get("t", 0)):
                            cnt = int(wv.get("count", 1))
                            spd = float(wv.get("speed", params["enemy_speed"]))
                            for _ in range(min(cnt, max(0, enemy_cap - len(enemies)))):
                                w = engine.screen.get_width()
                                x = random.randint(40, max(40, w - 40))
                                # 限时模式也使用随机机型，但不包含Boss
                                e = create_random_enemy_at(x, -40, 0)
                                e.speed = spd  # 保持原关卡配置速度
                                enemies.append(e)
                            spawned_flags[idx] = True
                # fallback trickle spawning（按难度每批生成多个）
                if now - last_spawn > spawn_interval and len(enemies) < enemy_cap // 2:
                    w_width = engine.screen.get_width()
                    can_spawn = max(0, (enemy_cap // 2) - len(enemies))
                    batch = min(params.get("trickle_batch", 1), can_spawn)
                    for _ in range(batch):
                        x = random.randint(40, max(40, w_width - 40))
                        e = create_random_enemy_at(x, -40, 0)
                        e.speed = params["enemy_speed"]
                        enemies.append(e)
                    last_spawn = now

        # update
        if state == "running":
            for b in bullets:
                b.update(dt)
            # 更新敌机AI（Boss由BossController单独更新，不参与AI更新）
            normal_enemies = [e for e in enemies if not (hasattr(e, "enemy_type_enum") and e.enemy_type_enum == EnemyType.BOSS)]
            update_enemy_ai(normal_enemies, dt, engine.screen.get_width())
            # props fade
            now_time = time.time()
            props = [p for p in props if now_time - p.spawn < p.ttl]
            # enemy bullets update
            for eb in enemy_bullets:
                eb.update(dt)

        # collision
        if state == "running":
            to_remove_b: set[int] = set()
            to_remove_e: set[int] = set()
            to_remove_eb: set[int] = set()
            now_hit = time.time()
            for i, b in enumerate(bullets):
                remove_bullet = False
                for j, e in enumerate(enemies):
                    if j in to_remove_e:
                        continue
                    if rect_collide(b.rect, e.rect):
                        damage = getattr(b, "damage", BASE_BULLET_DAMAGE)
                        e.hp -= damage
                        enemy_dead = e.hp <= 0
                        if enemy_dead:
                            to_remove_e.add(j)
                            explosions.append(Explosion(e.rect.centerx, e.rect.centery, explosion_frames))
                            if now_hit - combo_last_hit <= combo_window:
                                combo += 1
                            else:
                                combo = 1
                            combo_last_hit = now_hit
                            # 触发连击视觉反馈（在敌机位置显示）
                            if combo >= 2:
                                visual_effects.trigger_combo_feedback(combo, (e.rect.centerx, e.rect.centery))
                            # 使用敌机的score_value（无尽模式中不同机型得分不同）
                            base_score = getattr(e, "score_value", 10)
                            gain = base_score * max(1, combo // 5)
                            if buff_active_local("x2"):
                                gain *= 2
                            score += gain
                            # 掉落：限时/无尽掉道具；无尽Boss掉"进化币"
                            if game_mode == "endless":
                                # 无尽：常规掉落（与多人模式一致，使用normal难度）
                                drop_rate = props_sys.DROP_RATE.get("normal", 0.30)
                                if hasattr(e, "enemy_type_enum") and e.enemy_type_enum:
                                    spec = get_enemy_type_spec(e.enemy_type_enum)
                                    drop_rate *= spec.drop_rate_multiplier
                                if random.random() < drop_rate:
                                    kind = choose_prop_kind("normal")
                                    if kind:
                                        props.append(Prop(kind, e.rect.centerx, e.rect.centery))
                                # 另外：Boss额外掉进化币（未最终进化且判定为Boss）
                                is_boss_flag = (hasattr(e, "enemy_type_enum") and e.enemy_type_enum == EnemyType.BOSS) or (endless_spawner is not None and e == getattr(endless_spawner, "boss_enemy", None))
                                if is_boss_flag and evolution_level < 5:
                                    coins.append(Coin(e.rect.centerx, e.rect.centery, 3))
                            else:
                                # 限时模式：根据机型调整掉落率（与多人模式一致）
                                drop_rate = props_sys.DROP_RATE.get(difficulty, props_sys.DROP_RATE.get("normal", 0.3))
                                if hasattr(e, "enemy_type_enum") and e.enemy_type_enum:
                                    spec = get_enemy_type_spec(e.enemy_type_enum)
                                    drop_rate *= spec.drop_rate_multiplier
                                if random.random() < drop_rate:
                                    kind = choose_prop_kind(difficulty)
                                    if kind:
                                        props.append(Prop(kind, e.rect.centerx, e.rect.centery))
                            assets.play_sound("fx/bomb.wav", 0.6)
                            # 无尽：通知生成器敌机被击杀；若Boss被击杀则进入下一步并刷新背景/结算
                            if game_mode == "endless" and endless_spawner is not None:
                                is_boss = hasattr(e, "enemy_type_enum") and e.enemy_type_enum == EnemyType.BOSS
                                endless_spawner.on_enemy_killed(e)
                                if is_boss:
                                    if game_mode == "endless":
                                        # 记录步时并根据用时调整下一步敌速增幅
                                        last_step_duration = time.time() - last_step_time
                                        enemy_speed_step_mult = 1.06 if last_step_duration > 35.0 else 1.08
                                        power_step += 1
                                        # 敌方增强（按新曲线）
                                        params["enemy_speed"] *= enemy_speed_step_mult
                                        enemy_cap = min(140, params["enemy_cap"] + 6)
                                        params["enemy_cap"] = enemy_cap
                                        params["fire_interval"] = max(0.7, params["fire_interval"] * 0.92)
                                        # 敌出现速度（生成间隔）再加快一些
                                        spawn_interval = max(0.7, spawn_interval * 0.85)
                                        if power_step % 3 == 0:
                                            params["burst_max"] = min(4, params.get("burst_max", 1) + 1)
                                        # 玩家保底：每两步给予一次短暂 haste
                                        if power_step % 2 == 0:
                                            add_buff(buffs, "haste", 4.0)
                                        # 不再按步数强制设置进化阶（改为进化币机制）
                                        # 刷新场景（背景切换）
                                        _trigger_bg_switch_immediately()
                                    # 重置步进计时，下一轮重新计时20s
                                    last_step_time = time.time()
                                    step_boss_summoned = False
                        if getattr(b, "pierce", 0) > 0:
                            b.pierce -= 1
                            b._fy = float(b.rect.y)
                        else:
                            remove_bullet = True
                            break
                if remove_bullet:
                    to_remove_b.add(i)

            # enemy hit to player
            for j, e in enumerate(enemies):
                if j in to_remove_e:
                    continue
                if rect_collide(player.rect, e.rect):
                    # 相撞不再销毁敌机/Boss，按一次受击结算并加上冷却节流
                    now_ct = time.time()
                    if not buff_active_local("shield") and (now_ct - last_contact_damage_time >= CONTACT_DAMAGE_COOLDOWN):
                        last_contact_damage_time = now_ct
                        player.hp -= 20
                        visual_effects.trigger_hit_flash()  # 触发受击闪烁
                        if player.hp <= 0:
                            # 复活判定
                            if rebirth_count > 0:
                                rebirth_count -= 1
                                player.hp = params["player_hp"]
                                evolve_effect_until = time.time() + 1.0
                            else:
                                state = "game_over"
                                break
                    elif buff_active_local("shield"):
                        # 有护盾则仅提示，无伤害与不移除敌机
                        assets.play_sound("prop/pickup.wav", 0.5)

            # update explosions
            for ex in explosions:
                ex.update()
            explosions = [ex for ex in explosions if not ex.done]
            
            # 更新视觉特效
            visual_effects.update()

            # enemy bullet hit to player
            for k, eb in enumerate(enemy_bullets):
                if rect_collide(player.rect, eb.rect):
                    to_remove_eb.add(k)
                    if buff_active_local("shield"):
                        continue
                    eb_damage = {"easy": 10, "normal": 12, "hard": 15}.get(difficulty, 12)
                    player.hp -= eb_damage
                    visual_effects.trigger_hit_flash()  # 触发受击闪烁
                    if player.hp <= 0:
                        if rebirth_count > 0:
                            rebirth_count -= 1
                            player.hp = params["player_hp"]
                            evolve_effect_until = time.time() + 1.0
                        else:
                            state = "game_over"
                            break

            # pick props / coins
                for p in list(props):
                    if rect_collide(player.rect, p.rect):
                        spec = PROP_SPECS.get(p.kind, {})
                        if spec.get("type") == "instant":
                            if p.kind == "heal":
                                player.hp = min(player.hp + 30, params["player_hp"])
                            elif p.kind == "clearscreen":
                                clear_screen()
                        else:
                            add_buff(buffs, p.kind, spec.get("duration", 8.0))
                        props.remove(p)
                        assets.play_sound("prop/pickup.wav", 0.6)
            # 处理金币拾取：无尽->进化币
            for c in list(coins):
                if rect_collide(player.rect, c.rect):
                    if game_mode == "endless":
                        evo_coin_count += c.value
                        # 达到3个就进化一次并清零（可多余进位）
                        while evo_coin_count >= 3 and evolution_level < 5:
                            evo_coin_count -= 3
                            evolution_level += 1
                            # 进化奖励：回满生命，并显示进化特效
                            player.hp = params["player_hp"]
                            evolve_effect_until = time.time() + 1.0
                            # 达到最终形态赠送一次复活
                            if evolution_level >= 5 and rebirth_count < 1:
                                rebirth_count = 1
                    coins.remove(c)
                    assets.play_sound("prop/pickup.wav", 0.6)

            # remove collided
            if state == "running":
                bullets = [b for idx, b in enumerate(bullets) if idx not in to_remove_b]
                enemies = [e for idx, e in enumerate(enemies) if idx not in to_remove_e]
                enemy_bullets = [eb for idx, eb in enumerate(enemy_bullets) if idx not in to_remove_eb]

        # off-screen cleanup
        bullets = [b for b in bullets if b.rect.bottom >= -50]
        enemy_bullets = [eb for eb in enemy_bullets if -60 <= eb.rect.bottom <= engine.screen.get_height() + 60 and -60 <= eb.rect.right and eb.rect.left <= engine.screen.get_width() + 60]
        h = engine.screen.get_height()
        enemies = [e for e in enemies if e.rect.top <= h + 50]

        # draw
        if state in ("running", "paused", "game_over"):
            # 背景
            if game_mode == "endless" and endless_bg_list:
                # 先更新淡入状态；如完成则立即切换当前索引，避免出现旧底图与新底图交替的单帧闪烁
                if bg_fading and len(endless_bg_list) >= 2:
                    fade_dur = 1.0
                    t = (time.time() - bg_fade_start) / fade_dur
                    if t >= 1.0:
                        bg_cur_idx = bg_next_idx
                        bg_fading = False
                        bg_next_switch_time = time.time() + bg_switch_interval
                        bg_fade_surface = None
                # 绘制当前底图
                base_bg = endless_bg_list[bg_cur_idx]
                engine.screen.blit(base_bg, (0, 0))
                # 正在淡入则叠加下一张（已预创建并复用，避免每帧 copy 导致闪屏）
                if bg_fading and bg_fade_surface is not None:
                    fade_dur = 1.0
                    t = max(0.0, min(1.0, (time.time() - bg_fade_start) / fade_dur))
                    alpha = int(t * 255)
                    bg_fade_surface.set_alpha(alpha)
                    engine.screen.blit(bg_fade_surface, (0, 0))
                engine.screen.blit(dim_overlay, (0, 0))
            else:
                if bg_battle is not None:
                    engine.screen.blit(bg_battle, (0, 0))
                    engine.screen.blit(dim_overlay, (0, 0))
            if buff_active_local("shield"):
                radius = max(player.rect.width, player.rect.height) // 2 + 18
                shield_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(shield_surface, (140, 210, 255, 90), (radius, radius), radius, 3)
                engine.screen.blit(
                    shield_surface,
                    (player.rect.centerx - radius, player.rect.centery - radius),
                )
            
            # 绘制玩家（应用受击闪烁效果）；无尽进化替换贴图
            cur_player_img = ship_img
            if game_mode == "endless":
                idx = min(4, max(0, evolution_level - 1))
                if 0 <= idx < len(evo_ship_imgs) and evo_ship_imgs[idx] is not None:
                    cur_player_img = evo_ship_imgs[idx]
            if cur_player_img is not None:
                # 尝试应用闪烁效果
                flashed_surface = visual_effects.apply_hit_flash_to_surface(cur_player_img)
                if flashed_surface is not None:
                    engine.screen.blit(flashed_surface, player.rect)
                else:
                    engine.screen.blit(cur_player_img, player.rect)
            else:
                # 如果没有图片，使用默认绘制
                player_surface = pygame.Surface((player.rect.width, player.rect.height), pygame.SRCALPHA)
                player.draw(player_surface)
                flashed_surface = visual_effects.apply_hit_flash_to_surface(player_surface)
                if flashed_surface is not None:
                    engine.screen.blit(flashed_surface, player.rect)
                else:
                    engine.screen.blit(player_surface, player.rect)
            
            # 玩家子弹（使用图片素材）
            for b in bullets:
                use_plus = buff_active_local("power")
                img = bullet_img_plus if use_plus and bullet_img_plus is not None else bullet_img
                if img is not None:
                    dst = img.get_rect(center=b.rect.center)
                    engine.screen.blit(img, dst)
                else:
                    pygame.draw.rect(engine.screen, b.color, b.rect)
            # 敌机子弹（使用图片素材）
            for eb in enemy_bullets:
                if enemy_bullet_img is not None:
                    dst = enemy_bullet_img.get_rect(center=eb.rect.center)
                    engine.screen.blit(enemy_bullet_img, dst)
                else:
                    eb.draw(engine.screen)
            # 敌机（无尽模式使用与多人模式完全相同的渲染方式：多机型图片系统）
            if game_mode == "endless":
                for e in enemies:
                    # 与多人模式完全一致的逻辑：使用多机型图片
                    w = max(8, int(e.rect.width))
                    h = max(8, int(e.rect.height))
                    rect = pygame.Rect(int(e.rect.x), int(e.rect.y), w, h)
                    surf = None
                    # 优先使用敌机创建时已设置的图片（避免闪烁）
                    if hasattr(e, "image") and e.image is not None:
                        # 如果图片尺寸不匹配，需要缩放
                        if e.image.get_width() != w or e.image.get_height() != h:
                            key = (w, h, id(e.image))
                            surf = _enemy_img_cache.get(key)
                            if surf is None:
                                try:
                                    surf = pygame.transform.smoothscale(e.image, (w, h))
                                except Exception:
                                    surf = None
                                if surf:
                                    _enemy_img_cache[key] = surf
                        else:
                            surf = e.image
                    # 如果没有图片，根据敌机类型使用对应的多机型图片
                    elif hasattr(e, "enemy_type_enum") and e.enemy_type_enum:
                        enemy_type = e.enemy_type_enum
                        if enemy_type in enemy_images and enemy_images[enemy_type]:
                            # 使用对应机型的图片，缩放至目标尺寸
                            base_surf = random.choice(enemy_images[enemy_type])
                            key = (w, h, enemy_type.name)
                            surf = _enemy_img_cache.get(key)
                            if surf is None:
                                try:
                                    surf = pygame.transform.smoothscale(base_surf, (w, h))
                                except Exception:
                                    surf = None
                                if surf:
                                    _enemy_img_cache[key] = surf
                    
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
                    # HP条（与多人模式完全一致）
                    hp = getattr(e, "hp", 0)
                    hp_max = getattr(e, "max_hp", hp or 1)
                    if hp is not None and hp_max:
                        ratio = max(0.0, min(1.0, hp / max(1, hp_max)))
                        pygame.draw.rect(engine.screen, (60, 60, 60), pygame.Rect(rect.x, rect.y - 6, rect.width, 3))
                        pygame.draw.rect(engine.screen, (255, 120, 120), pygame.Rect(rect.x, rect.y - 6, int(rect.width * ratio), 3))
            else:
                for e in enemies:
                    if hasattr(e, "image") and e.image is not None:
                        engine.screen.blit(e.image, e.rect)
                    elif enemy_img is not None:
                        engine.screen.blit(enemy_img, e.rect)
                    else:
                        e.draw(engine.screen)
            # draw explosions
            for ex in explosions:
                ex.draw(engine.screen)
            # 道具（使用图片素材）
            for p in props:
                img = PROP_IMAGES.get(p.kind)
                if img is not None:
                    engine.screen.blit(img, p.rect)
                else:
                    pygame.draw.rect(engine.screen, p.color, p.rect, border_radius=6)
            # draw coins（无尽模式使用与多人模式相同的渲染方式）
            if game_mode == "endless":
                for c in coins:
                    # 多人模式使用 (28, 28) 的 rect，图片是 (26, 26)
                    rect = pygame.Rect(c.rect.centerx - 14, c.rect.centery - 14, 28, 28)
                    if coin_img is not None:
                        dst = coin_img.get_rect(center=rect.center)
                        engine.screen.blit(coin_img, dst)
                    else:
                        pygame.draw.circle(engine.screen, (255, 220, 80), rect.center, rect.width // 2)
            else:
                for c in coins:
                    Coin.draw(c, engine.screen, coin_img)

            # HUD
            fps = engine.clock.get_fps()
            elapsed = int(time.time() - start_time)
            remain = max(0, int(time_limit - (time.time() - start_time)))
            mult = "x2" if buff_active_local("x2") else "x1"
            cur_wave = 0
            if 'waves' in locals():
                cur_wave = sum(1 for f in spawned_flags if f)
            if game_mode == "endless":
                time_txt = f"无尽 Elapsed:{elapsed}s Step:{power_step}"
            else:
                time_txt = f"Time:{remain}s"
            # 无尽模式显示波次和Boss信息
            if game_mode == "endless" and endless_spawner is not None:
                wave_info = f" Wave:{endless_spawner.current_wave + 1}"
                if endless_spawner.has_boss():
                    boss_hp_pct = int((endless_spawner.boss_enemy.hp / endless_spawner.boss_enemy.max_hp) * 100)
                    wave_info += f" BOSS:{boss_hp_pct}%"
                time_txt += wave_info
            extra = ""
            hud = f"HP:{player.hp}  Score:{score}{extra}  {time_txt}  Diff:{difficulty}  FPS:{fps:.0f}  [P]暂停"
            render_hud(engine.screen, font_small, [hud], buffs, len(enemies), len(enemy_bullets), len(props))

            # line 2+: buffs with countdown, wrapped
            buff_labels = active_buff_labels()
            y_cursor = 32
            # 精英小队提示已移除（不再渲染提示条）
            if buff_labels:
                wrapped = wrap_items(buff_labels, per_line=4)
                for idx, line_txt in enumerate(wrapped):
                    prefix = "持续效果: " if idx == 0 else "           "
                    buff_surf = font_small.render(prefix + line_txt, True, (220, 220, 220))
                    engine.screen.blit(buff_surf, (12, y_cursor))
                    y_cursor += 20
            else:
                buff_surf = font_small.render("持续效果: 无", True, (180, 180, 180))
                engine.screen.blit(buff_surf, (12, y_cursor))
                y_cursor += 20

            # extra stats line (enemies and drops)
            stats_txt = f"统计: 敌机 {len(enemies)}  敌弹 {len(enemy_bullets)}  掉落 {len(props)}"
            stats_surf = font_small.render(stats_txt, True, (205, 205, 205))
            engine.screen.blit(stats_surf, (12, y_cursor))

            # 进化特效：程序化环形脉冲，贴合玩家机体中心，持续1s
            if evolve_effect_until > time.time():
                try:
                    t = max(0.0, min(1.0, 1.0 - (evolve_effect_until - time.time())))
                    center = (player.rect.centerx, player.rect.centery)
                    r1 = int(18 + 22 * t)
                    r2 = int(10 + 28 * t)
                    alpha1 = int(180 * (1.0 - t))
                    alpha2 = int(140 * (1.0 - t))
                    s1 = pygame.Surface((r1 * 2 + 4, r1 * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(s1, (120, 230, 255, alpha1), (r1 + 2, r1 + 2), r1, 3)
                    s2 = pygame.Surface((r2 * 2 + 4, r2 * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(s2, (200, 255, 200, alpha2), (r2 + 2, r2 + 2), r2, 2)
                    engine.screen.blit(s1, (center[0] - r1 - 2, center[1] - r1 - 2))
                    engine.screen.blit(s2, (center[0] - r2 - 2, center[1] - r2 - 2))
                except Exception:
                    pass
            # 第四行：金币/进化币记录（避免遮挡HUD第一行）
            y_cursor += 20
            if coin_img is not None:
                if game_mode == "endless":
                    icon_rect = coin_img.get_rect(topleft=(12, y_cursor-2))
                    engine.screen.blit(coin_img, icon_rect)
                    if evolution_level >= 5:
                        txt = font_small.render("已最终进化", True, (230, 230, 255))
                    else:
                        txt = font_small.render(f"x{evo_coin_count}/3 进化币", True, (235, 235, 180))
                    engine.screen.blit(txt, (icon_rect.right + 6, icon_rect.top + 2))
                    # 复活次数显示（最终形态奖励）
                    if rebirth_img is not None and rebirth_count > 0:
                        # 与进化币对齐：图标更大，向下微调 2px，文本对齐基线
                        rb_rect = rebirth_img.get_rect(topleft=(icon_rect.right + 120, y_cursor))
                        engine.screen.blit(rebirth_img, rb_rect)
                        rb_txt = font_small.render(f"x{rebirth_count}", True, (220, 255, 220))
                        engine.screen.blit(rb_txt, (rb_rect.right + 8, rb_rect.top + 6))

            # 碰撞盒调试渲染（仅自定义模式）
            if difficulty == "custom" and settings_store.get_setting("show_hitbox", False):
                pygame.draw.rect(engine.screen, (0, 255, 0), player.rect, 1)
                for e in enemies:
                    pygame.draw.rect(engine.screen, (255, 0, 0), e.rect, 1)
                for b in bullets:
                    pygame.draw.rect(engine.screen, (255, 255, 0), b.rect, 1)
                for eb in enemy_bullets:
                    pygame.draw.rect(engine.screen, (255, 120, 120), eb.rect, 1)
                for p in props:
                    pygame.draw.rect(engine.screen, (120, 255, 140), p.rect, 1)
            
            # 渲染连击反馈（在最上层）
            visual_effects.render_combo_feedbacks(engine.screen, font_small)

            if state == "paused":
                # 使用新的暂停菜单渲染
                pause_menu.render(engine.screen, dim_overlay)

            if state == "game_over":
                over_txt = font_big.render("GAME OVER  [R] Return to Menu", True, (255, 120, 120))
                engine.screen.blit(over_txt, (engine.screen.get_width()//2 - over_txt.get_width()//2, 260))
                # save record once
                if not hasattr(run, "_saved_over"):
                    setattr(run, "_saved_over", True)
                    import datetime
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # fire-and-forget insert
                    try:
                        import asyncio
                        mode_str = f"single_{game_mode}"
                        asyncio.run(dao.insert_record("local", mode_str, ts, score, "dead"))
                    except RuntimeError:
                        # already in loop (unlikely in SP), skip
                        pass
                    assets.play_sound("ui/game_over.wav", 0.7)

        if state == "menu":
            # 背景
            if bg_battle is not None:
                engine.screen.blit(bg_battle, (0, 0))
                engine.screen.blit(dim_overlay, (0, 0))
            title = font_big.render("Plane Battle - Single Player", True, (180, 230, 255))
            engine.screen.blit(title, (engine.screen.get_width()//2 - title.get_width()//2, 160))
            if game_mode == "timed":
                tips1 = font_small.render("选择难度: [1] 简单  [2] 中等  [3] 困难  [4] 自定义", True, (220, 220, 220))
                engine.screen.blit(tips1, (engine.screen.get_width()//2 - tips1.get_width()//2, 240))
                tips2 = font_small.render("按 Enter 开始（限时），操作: WASD 移动, 空格 射击, ESC 退出  [H] 查看历史", True, (220, 220, 220))
            elif game_mode == "endless":
                tips2 = font_small.render("按 Enter 开始（无尽），每20s召唤Boss，击杀后进入下一轮", True, (220, 220, 220))
            engine.screen.blit(tips2, (engine.screen.get_width()//2 - tips2.get_width()//2, 270))
            if game_mode == "endless":
                cur_txt = "模式: 无尽"
            else:
                cur_txt = f"当前难度: {difficulty}    模式: 限时"
            cur = font_small.render(cur_txt, True, (200, 255, 200))
            engine.screen.blit(cur, (engine.screen.get_width()//2 - cur.get_width()//2, 300))

            # history overlay (toggle by H)
            if getattr(run, "_hist_open", False):
                records = getattr(run, "_hist_cache", [])
                box_w, box_h = 560, 240
                x = engine.screen.get_width()//2 - box_w//2
                y = 330
                pygame.draw.rect(engine.screen, (30, 40, 60), pygame.Rect(x, y, box_w, box_h))
                pygame.draw.rect(engine.screen, (120, 160, 200), pygame.Rect(x, y, box_w, box_h), 2)
                title2 = font_small.render("最近战绩 (H 关闭)", True, (220, 220, 220))
                engine.screen.blit(title2, (x + 10, y + 10))
                if records:
                    for i, r in enumerate(records):
                        line = f"{r['time']}  {r['mode']}  {r['score']}  {r['result']}"
                        engine.screen.blit(font_small.render(line, True, (210, 210, 210)), (x + 10, y + 36 + i * 22))
                else:
                    engine.screen.blit(font_small.render("暂无记录", True, (210, 210, 210)), (x + 10, y + 40))

        # time up -> game over and save（无尽不受时间限制）
        if state == "running" and game_mode != "endless" and (time.time() - start_time) >= time_limit:
            state = "game_over"
            try:
                import datetime, asyncio
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                mode_str = f"single_{game_mode}"
                asyncio.run(dao.insert_record("local", mode_str, ts, score, "timeup"))
            except RuntimeError:
                pass

        # enemy fire logic with cooldowns (aimed / cone / split, anti-burst)
        if state == "running":
            if len(enemy_bullets) < enemy_bullet_cap:
                # 距离自适应权重：近距离更偏扇形，中距瞄准，远距离保留分裂
                base_interval = params["fire_interval"]
                burst_max = params["burst_max"]
                burst_gap = params["burst_gap"]
                now_s = time.time()
                for e in enemies:
                    key = id(e)
                    st = enemy_fire_state.get(key)
                    if st is None:
                        st = {"next": now_s + random.uniform(base_interval*0.6, base_interval*1.2), "burst_left": 0}
                        enemy_fire_state[key] = st
                    if now_s < st["next"] or len(enemy_bullets) >= enemy_bullet_cap:
                        continue
                    # 取消对玩家的瞄准/追踪：只允许前向（向下）模式（扇形/分裂）
                    ex, ey = e.rect.centerx, e.rect.bottom
                    # 模式权重（无瞄准）
                    if difficulty == "easy":
                        w_cone, w_split = (0.75, 0.25)
                    elif difficulty == "normal":
                        w_cone, w_split = (0.60, 0.40)
                    else:
                        w_cone, w_split = (0.55, 0.45)
                    r = random.random()
                    if r < w_cone:
                        base_angle = math.radians(90)
                        for a in (-12, 0, 12):
                            ang = base_angle + math.radians(a)
                            vx, vy = math.cos(ang), math.sin(ang)
                            speed = 300.0 if difficulty == "easy" else 330.0 if difficulty == "normal" else 360.0
                            enemy_bullets.append(EnemyBullet(ex - 4, ey, vx, vy, speed=speed))
                    else:
                        delay = 0.7 if difficulty == "easy" else 0.65 if difficulty == "normal" else 0.6
                        enemy_bullets.append(EnemyBullet(ex - 4, ey, 0.0, 1.0, speed=200.0, split_at=delay))
                    # schedule next
                    if st["burst_left"] <= 0:
                        st["burst_left"] = random.randint(0, max(0, burst_max - 1))
                    if st["burst_left"] > 0:
                        st["burst_left"] -= 1
                        st["next"] = now_s + burst_gap
                    else:
                        st["next"] = now_s + base_interval + random.uniform(-0.25, 0.25)*base_interval
                # handle splitting
                new_bullets: list[EnemyBullet] = []
                for eb in enemy_bullets:
                    # 只有EnemyBullet有split_at和spawn属性，Boss生成的Bullet没有
                    if hasattr(eb, "split_at") and hasattr(eb, "spawn") and eb.split_at > 0 and now_s - eb.spawn >= eb.split_at:
                        # 固定角度分裂：沿原发射角度扇形扩散，避免追踪玩家
                        base = getattr(eb, "theta", math.atan2(eb.vy, eb.vx))
                        ex, ey = eb.rect.centerx, eb.rect.centery
                        for da in (-math.radians(8), 0, math.radians(8)):
                            vx, vy = math.cos(base + da), math.sin(base + da)
                            new_bullets.append(EnemyBullet(ex - 4, ey - 4, vx, vy, speed=400.0, color=(255,180,120)))
                        eb.split_at = 0.0
                enemy_bullets.extend(new_bullets)

        engine.end_frame()

    # 退出单人模式时，恢复菜单BGM
    if as_child:
        assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
    
    # 仅独立运行脚本时才彻底退出 pygame（从主菜单进入时不应关闭主窗口）
    if not as_child:
        engine.quit()
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    run(as_child=False)

