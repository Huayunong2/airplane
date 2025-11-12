from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pygame

from core.collision import rect_collide
from core.entities import Bullet, Enemy, Player
from game.boss_system import BossController
from game.endless_spawner import EndlessSpawner
from game.enemy_ai import update_enemy_ai
from game.enemy_types import EnemyType, get_enemy_type_spec, load_enemy_images
from game.props_system import (
    PROP_SPECS,
    DROP_RATE,
    Prop,
    add_buff,
    buff_active,
    choose_prop_kind,
    cleanup_buffs,
)
from game.shooting import compute_fire_cooldown, create_player_bullets


@dataclass
class ClientInput:
    move_x: float = 0.0
    move_y: float = 0.0
    fire: bool = False
    timestamp: float = 0.0


@dataclass
class Coin:
    x: int
    y: int
    value: int
    spawn: float = field(default_factory=time.time)
    ttl: float = 12.0

    def __post_init__(self) -> None:
        self.rect = pygame.Rect(self.x - 14, self.y - 14, 28, 28)


class EnemyBullet:
    def __init__(
        self,
        x: int,
        y: int,
        vx: float,
        vy: float,
        speed: float = 360.0,
        color: Tuple[int, int, int] = (255, 120, 120),
        split_at: float = 0.0,
    ) -> None:
        self.rect = pygame.Rect(x, y, 8, 16)
        self.vx = vx
        self.vy = vy
        self.speed = speed
        self.color = color
        self.spawn = time.time()
        self.split_at = split_at

    def update(self, dt: float) -> None:
        self.rect.x += int(self.vx * self.speed * dt)
        self.rect.y += int(self.vy * self.speed * dt)


BASE_FIRE_COOLDOWN = 0.18
BASE_BULLET_SPEED = 560.0
BASE_BULLET_DAMAGE = 30.0
BASE_BULLET_SIZE = (8, 16)
BASE_PIERCE = 0

CONTACT_DAMAGE_COOLDOWN = 0.6
PLAYER_SPEED = 320.0
PLAYER_MAX_HP = 100

PLAYER_SPAWN_PADDING = 60

EVO_ATTACK_SPEED_MULTS = [1.0, 1.10, 1.20, 1.35, 1.50]
EVO_DAMAGE_MULTS = [1.0, 1.10, 1.20, 1.35, 1.50]
EVO_PIERCE_BONUS = [0, 0, 1, 1, 2]


@dataclass
class PlayerState:
    player_id: str
    entity: Player
    hp: int = PLAYER_MAX_HP
    max_hp: int = PLAYER_MAX_HP
    buffs: Dict[str, float] = field(default_factory=dict)
    score: int = 0
    combo: int = 0
    combo_last_hit: float = 0.0
    evolution_level: int = 1
    evo_coin_count: int = 0
    revives: int = 0
    last_contact_damage_time: float = 0.0
    last_fire_time: float = 0.0
    bullet_cap: int = 120
    player_attack_speed_mult: float = 1.0
    currency: int = 0
    evolve_effect_until: float = 0.0
    revive_granted: bool = False

    def reset_combo(self) -> None:
        self.combo = 0
        self.combo_last_hit = 0.0


class EndlessWorld:
    """
    服务端权威的无尽模式世界状态。
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.enemy_images = load_enemy_images()
        self.spawner = EndlessSpawner(width, self.enemy_images)
        self.players: Dict[str, PlayerState] = {}
        self.inputs: Dict[str, ClientInput] = {}

        self.enemies: List[Enemy] = []
        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[EnemyBullet | Bullet] = []
        self.props: List[Prop] = []
        self.coins: List[Coin] = []
        self.enemy_fire_state: Dict[int, Dict[str, float]] = {}

        now = time.time()
        self.start_time = None  # 游戏开始时间（等待所有玩家准备完毕）
        self.last_step_time = now
        self.power_step = 0
        self.enemy_speed_step_mult = 1.08
        self.last_step_duration = 0.0

        self.spawn_interval = 2.4
        self.last_spawn = now
        self.enemy_cap = 28
        self.enemy_bullet_cap = 160
        self.burst_max = 1
        self.burst_gap = 0.16
        self.fire_interval = 2.6
        self.elite_next_time = now + 6.0
        self.step_boss_summoned = False
        self.endless_step_interval = 20.0  # 每20秒一个步点（与单人模式一致）

        self.boss_controller: Optional[BossController] = None
        self.boss_spawned_this_frame = False
        self.prop_picked_this_frame = False
        self.bg_index = 0
        self.enemy_uid_counter = 0
        self.boss_spawn_event_id = 0

    # ------------------------------------------------------------------ Player
    def add_player(self, player_id: str) -> PlayerState:
        spawn_x = max(PLAYER_SPAWN_PADDING, min(self.width - PLAYER_SPAWN_PADDING, self.width // 2))
        spawn_y = self.height - PLAYER_SPAWN_PADDING
        entity = Player(spawn_x, spawn_y)
        entity.speed = PLAYER_SPEED
        ps = PlayerState(player_id=player_id, entity=entity)
        # 显式设置HP为满血，确保玩家初始状态正确
        ps.hp = PLAYER_MAX_HP
        ps.max_hp = PLAYER_MAX_HP
        self.players[player_id] = ps
        self.inputs[player_id] = ClientInput(timestamp=time.time())
        return ps

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        self.inputs.pop(player_id, None)

    def handle_input(self, player_id: str, inp: ClientInput) -> None:
        if player_id not in self.players:
            self.add_player(player_id)
        self.inputs[player_id] = inp

    def export_player_state(self, player_id: str) -> Optional[Dict[str, Any]]:
        state = self.players.get(player_id)
        if state is None:
            return None
        return {
            "hp": state.hp,
            "max_hp": state.max_hp,
            "score": state.score,
            "evo_level": state.evolution_level,
            "evo_coins": state.evo_coin_count,
            "revives": state.revives,
            "revive_granted": state.revive_granted,
            "buffs": dict(state.buffs),
            "combo": state.combo,
            "combo_last_hit": state.combo_last_hit,
            "currency": state.currency,
            "player_attack_speed_mult": state.player_attack_speed_mult,
            "bullet_cap": state.bullet_cap,
            "last_contact_damage_time": state.last_contact_damage_time,
            "last_fire_time": state.last_fire_time,
            "evolve_effect_until": state.evolve_effect_until,
            "pos": (state.entity.rect.x, state.entity.rect.y),
        }

    def import_player_state(self, player_id: str, snapshot: Dict[str, Any]) -> None:
        state = self.players.get(player_id)
        if state is None or snapshot is None:
            return
        state.max_hp = int(snapshot.get("max_hp", state.max_hp))
        state.hp = int(snapshot.get("hp", state.hp))
        if state.max_hp <= 0:
            state.max_hp = PLAYER_MAX_HP
        state.hp = max(0, min(state.max_hp, state.hp))
        state.score = int(snapshot.get("score", state.score))
        state.evolution_level = int(snapshot.get("evo_level", state.evolution_level))
        state.evolution_level = max(1, min(5, state.evolution_level))
        state.evo_coin_count = int(snapshot.get("evo_coins", state.evo_coin_count))
        state.revives = int(snapshot.get("revives", state.revives))
        state.revive_granted = bool(snapshot.get("revive_granted", state.revive_granted))
        buffs = snapshot.get("buffs")
        if isinstance(buffs, dict):
            state.buffs = {k: float(v) for k, v in buffs.items()}
        state.combo = int(snapshot.get("combo", state.combo))
        state.combo_last_hit = float(snapshot.get("combo_last_hit", state.combo_last_hit or 0.0))
        state.currency = int(snapshot.get("currency", state.currency))
        state.player_attack_speed_mult = float(snapshot.get("player_attack_speed_mult", state.player_attack_speed_mult))
        state.bullet_cap = int(snapshot.get("bullet_cap", state.bullet_cap))
        state.last_contact_damage_time = float(snapshot.get("last_contact_damage_time", state.last_contact_damage_time or 0.0))
        state.last_fire_time = float(snapshot.get("last_fire_time", state.last_fire_time or 0.0))
        state.evolve_effect_until = float(snapshot.get("evolve_effect_until", state.evolve_effect_until or 0.0))
        pos = snapshot.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                state.entity.rect.x = int(pos[0])
                state.entity.rect.y = int(pos[1])
            except Exception:
                pass
        self.inputs[player_id] = ClientInput(timestamp=time.time())

    # ------------------------------------------------------------------ Step
    def step(self, dt: float) -> None:
        now = time.time()
        # 如果游戏还没开始（等待玩家准备），不执行游戏逻辑
        if self.start_time is None:
            return
        
        cleanup_targets: Dict[str, List[int]] = {"player_bullets": [], "enemies": [], "enemy_bullets": []}

        # Update players (movement, buffs, fire)
        for player_id, state in list(self.players.items()):
            cleanup_buffs(state.buffs)
            inp = self.inputs.get(player_id, ClientInput())
            # 如果玩家死亡，无法移动和开火
            if state.hp > 0:
                self._update_player_movement(state, inp, dt)
                if inp.fire:
                    self._player_try_fire(state, now)

        # Spawn enemies & boss
        self._update_spawning(now)

        # Update enemies (movement + AI)
        normal_enemies = [e for e in self.enemies if not (hasattr(e, "enemy_type_enum") and e.enemy_type_enum == EnemyType.BOSS)]
        update_enemy_ai(normal_enemies, dt, self.width)

        # Update bullets
        for b in self.player_bullets:
            b.update(dt)
        for eb in self.enemy_bullets:
            eb.update(dt)

        # Boss controller
        if self.spawner.has_boss():
            controller = self.spawner.get_boss_controller()
            if controller is not None:
                boss_bullets = controller.update(dt, self.width)
                self.enemy_bullets.extend(boss_bullets)

        # Enemy fire logic
        if len(self.enemy_bullets) < self.enemy_bullet_cap:
            self._enemy_fire(now)

        # Handle collisions
        self._handle_bullet_enemy_collisions(now)
        self._handle_player_enemy_collisions(now)
        self._handle_player_enemy_bullet_collisions()
        self._handle_pickups()

        # Cleanup off-screen
        self.player_bullets = [b for b in self.player_bullets if b.rect.bottom >= -50]
        self.enemy_bullets = [
            eb
            for eb in self.enemy_bullets
            if -80 <= eb.rect.bottom <= self.height + 80 and -80 <= eb.rect.right and eb.rect.left <= self.width + 80
        ]
        self.enemies = [e for e in self.enemies if e.rect.top <= self.height + 80]
        self.coins = [c for c in self.coins if time.time() - c.spawn <= c.ttl]

    # ------------------------------------------------------------------ Helpers
    def _update_player_movement(self, state: PlayerState, inp: ClientInput, dt: float) -> None:
        entity = state.entity
        dx = max(-1.0, min(1.0, inp.move_x))
        dy = max(-1.0, min(1.0, inp.move_y))
        entity.rect.x += int(dx * entity.speed * dt)
        entity.rect.y += int(dy * entity.speed * dt)

        if entity.rect.left < 0:
            entity.rect.left = 0
        if entity.rect.right > self.width:
            entity.rect.right = self.width
        if entity.rect.top < 0:
            entity.rect.top = 0
        if entity.rect.bottom > self.height:
            entity.rect.bottom = self.height

    def _player_try_fire(self, state: PlayerState, now: float) -> None:
        level = max(1, min(5, state.evolution_level))
        base_cooldown = compute_fire_cooldown(BASE_FIRE_COOLDOWN, state.buffs)
        base_cooldown /= EVO_ATTACK_SPEED_MULTS[level - 1]
        base_cooldown /= state.player_attack_speed_mult
        if now - state.last_fire_time < base_cooldown:
            return

        dmg = BASE_BULLET_DAMAGE * EVO_DAMAGE_MULTS[level - 1]
        bullets = create_player_bullets(state.entity, state.buffs, BASE_BULLET_SPEED, dmg, BASE_BULLET_SIZE)
        pierce_bonus = EVO_PIERCE_BONUS[level - 1]
        for b in bullets:
            b.pierce = max(0, b.pierce + pierce_bonus + BASE_PIERCE)

        if level >= 3:
            extra = max(0, min(3, level - 2))
            angle_sets = {1: [-10], 2: [-12, 12], 3: [-16, 0, 16]}
            for deg in angle_sets.get(extra, []):
                ang = math.radians(-90 + deg)
                vx, vy = math.cos(ang), math.sin(ang)
                new_bullet = Bullet(
                    state.entity.rect.centerx,
                    state.entity.rect.top - 8,
                    width=8,
                    height=16,
                    speed=BASE_BULLET_SPEED,
                    vx=vx,
                    vy=vy,
                    damage=dmg,
                    pierce=pierce_bonus,
                )
                bullets.append(new_bullet)

        if len(self.player_bullets) + len(bullets) <= state.bullet_cap:
            self.player_bullets.extend(bullets)
            state.last_fire_time = now

    def _update_spawning(self, now: float) -> None:
        # Boss生成规则：与单人无尽模式一致，基于步点（每20秒）而非击杀数
        # 达到步点：若未召唤Boss且当前没有Boss，则立即召唤Boss
        if (now - self.last_step_time >= self.endless_step_interval) and not self.spawner.has_boss() and not self.step_boss_summoned:
            boss, controller = self.spawner.spawn_boss(self.power_step)
            try:
                scale = 1.25 ** max(0, self.power_step)
                boss.hp = int(boss.hp * scale)
                boss.max_hp = int(boss.max_hp * scale)
            except Exception:
                pass
            self._register_enemy(boss)
            self.boss_controller = controller
            self.step_boss_summoned = True
            # Boss出场音效（通过snapshot中的标志通知客户端播放）
            self.boss_spawned_this_frame = True
            self.boss_spawn_event_id += 1

        if not self.spawner.has_boss() and len(self.enemies) < self.enemy_cap:
            enemy = self.spawner.spawn_enemy(self.power_step, self.spawn_interval, self.enemy_cap)
            if enemy is not None:
                self._register_enemy(enemy)

        if not self.spawner.has_boss():
            self._maybe_spawn_elite(now)

    def _register_enemy(self, enemy: Enemy) -> None:
        if not hasattr(enemy, "net_uid"):
            enemy.net_uid = self.enemy_uid_counter
            self.enemy_uid_counter += 1
        if not hasattr(enemy, "sprite_variant"):
            setattr(enemy, "sprite_variant", None)
        self.enemies.append(enemy)

    def _maybe_spawn_elite(self, now: float) -> None:
        if now < self.elite_next_time:
            return
        squad = min(7, 3 + self.power_step // 2)
        available = max(0, self.enemy_cap - len(self.enemies))
        squad = max(0, min(squad, available))
        if squad <= 0:
            self.elite_next_time = now + 4.0
            return

        formations = ["line", "v", "snake", "column", "arc", "stagger"]
        formation = random.choice(formations)
        spawned = 0
        base_y = -48

        def add_enemy(customize: Optional[Tuple[int, int]] = None, speed_mult: float = 1.0) -> None:
            nonlocal spawned
            enemy = self.spawner.spawn_enemy(self.power_step, 0.0, self.enemy_cap)
            if enemy is None:
                return
            if customize is not None:
                enemy.rect.x, enemy.rect.y = customize
            enemy.speed *= speed_mult
            self._register_enemy(enemy)
            spawned += 1

        if formation == "line":
            spacing = max(48, self.width // (squad + 1))
            for i in range(squad):
                x = spacing * (i + 1)
                add_enemy((x, base_y - i * 12), speed_mult=1.10)
        elif formation == "v":
            center = self.width // 2
            dx = max(36, self.width // 14)
            for i in range(squad):
                offset = i - (squad - 1) / 2.0
                x = center + int(offset * dx)
                y = base_y - int(abs(offset) * 20)
                x = max(24, min(self.width - 24, x))
                add_enemy((x, y), speed_mult=1.12)
        elif formation == "snake":
            amp = max(40, self.width // 10)
            phase = random.random() * math.pi * 2
            for i in range(squad):
                t = i / max(1, (squad - 1))
                x = int(self.width * (0.15 + 0.7 * t))
                y = base_y - int(math.sin(phase + t * math.pi * 1.5) * amp * 0.2 * (1 + t))
                add_enemy((x, y), speed_mult=1.08)
        elif formation == "column":
            xbase = self.width // 2
            for i in range(squad):
                x = xbase + (i - squad // 2) * 18
                y = base_y - i * 24
                add_enemy((x, y), speed_mult=1.12)
        elif formation == "arc":
            cx, cy = self.width // 2, base_y - 20
            for i in range(squad):
                t = -math.pi / 3 + (2 * math.pi / 3) * (i / max(1, squad - 1))
                r = max(80, self.width // 5)
                x = int(cx + math.cos(t) * r)
                y = int(cy + math.sin(t) * r * 0.5)
                x = max(24, min(self.width - 24, x))
                add_enemy((x, y), speed_mult=1.10)
        else:  # stagger
            cols = max(2, min(3, squad // 2))
            rows = (squad + cols - 1) // cols
            spacing_x = self.width // (cols + 1)
            for r in range(rows):
                for c in range(cols):
                    idx = r * cols + c
                    if idx >= squad:
                        break
                    x = spacing_x * (c + 1) + (r % 2) * 24
                    y = base_y - r * 20
                    add_enemy((x, y), speed_mult=1.09)

        self.elite_next_time = now + max(3.5, 9.0 - self.power_step * 0.5)

    def _enemy_fire(self, now: float) -> None:
        base_interval = self.fire_interval
        burst_max = self.burst_max
        burst_gap = self.burst_gap
        for e in self.enemies:
            key = id(e)
            st = self.enemy_fire_state.get(key)
            if st is None:
                st = {"next": now + random.uniform(base_interval * 0.6, base_interval * 1.2), "burst_left": 0}
                self.enemy_fire_state[key] = st
            if now < st["next"] or len(self.enemy_bullets) >= self.enemy_bullet_cap:
                continue

            ex, ey = e.rect.centerx, e.rect.bottom
            r = random.random()
            if r < 0.6:
                base_angle = math.radians(90)
                for a in (-12, 0, 12):
                    ang = base_angle + math.radians(a)
                    vx, vy = math.cos(ang), math.sin(ang)
                    speed = 330.0
                    self.enemy_bullets.append(EnemyBullet(ex - 4, ey, vx, vy, speed=speed))
            else:
                delay = 0.65
                self.enemy_bullets.append(EnemyBullet(ex - 4, ey, 0.0, 1.0, speed=220.0, split_at=delay))

            if st["burst_left"] <= 0:
                st["burst_left"] = random.randint(0, max(0, burst_max - 1))
            if st["burst_left"] > 0:
                st["burst_left"] -= 1
                st["next"] = now + burst_gap
            else:
                st["next"] = now + base_interval + random.uniform(-0.25, 0.25) * base_interval

        new_bullets: List[EnemyBullet] = []
        for eb in self.enemy_bullets:
            if isinstance(eb, EnemyBullet) and eb.split_at > 0 and now - eb.spawn >= eb.split_at:
                base_theta = math.atan2(eb.vy, eb.vx)
                ex, ey = eb.rect.centerx, eb.rect.centery
                for da in (-math.radians(8), 0, math.radians(8)):
                    vx, vy = math.cos(base_theta + da), math.sin(base_theta + da)
                    new_bullets.append(EnemyBullet(ex - 4, ey - 4, vx, vy, speed=400.0, color=(255, 180, 120)))
                eb.split_at = 0.0
        self.enemy_bullets.extend(new_bullets)

    def _handle_bullet_enemy_collisions(self, now: float) -> None:
        to_remove_b: set[int] = set()
        to_remove_e: set[int] = set()
        for bi, b in enumerate(self.player_bullets):
            remove_bullet = False
            for ei, e in enumerate(self.enemies):
                if ei in to_remove_e:
                    continue
                if rect_collide(b.rect, e.rect):
                    damage = getattr(b, "damage", BASE_BULLET_DAMAGE)
                    e.hp -= damage
                    if e.hp <= 0:
                        to_remove_e.add(ei)
                        self._on_enemy_killed(e)
                    pierce = getattr(b, "pierce", 0)
                    if pierce <= 0:
                        remove_bullet = True
                    else:
                        b.pierce = pierce - 1
                        b._fy = float(b.rect.y)
            if remove_bullet:
                to_remove_b.add(bi)

        self.player_bullets = [b for idx, b in enumerate(self.player_bullets) if idx not in to_remove_b]
        self.enemies = [e for idx, e in enumerate(self.enemies) if idx not in to_remove_e]

    def _handle_player_enemy_collisions(self, now: float) -> None:
        for ei, e in enumerate(self.enemies):
            for state in self.players.values():
                if rect_collide(state.entity.rect, e.rect):
                    if buff_active(state.buffs, "shield"):
                        continue
                    if now - state.last_contact_damage_time < CONTACT_DAMAGE_COOLDOWN:
                        continue
                    state.last_contact_damage_time = now
                    state.hp -= 20
                    if state.hp <= 0:
                        self._handle_player_death(state)

    def _handle_player_enemy_bullet_collisions(self) -> None:
        to_remove: set[int] = set()
        for idx, eb in enumerate(self.enemy_bullets):
            for state in self.players.values():
                if rect_collide(state.entity.rect, eb.rect):
                    to_remove.add(idx)
                    if buff_active(state.buffs, "shield"):
                        continue
                    state.hp -= 12
                    if state.hp <= 0:
                        self._handle_player_death(state)
        self.enemy_bullets = [eb for idx, eb in enumerate(self.enemy_bullets) if idx not in to_remove]

    def _handle_player_death(self, state: PlayerState) -> None:
        if state.revives > 0:
            state.revives -= 1
            state.hp = state.max_hp
            state.evolve_effect_until = time.time() + 1.0
        else:
            state.hp = 0

    def _handle_pickups(self) -> None:
        for state in self.players.values():
            # props (endless mode)
            for p in list(self.props):
                if rect_collide(state.entity.rect, p.rect):
                    spec = PROP_SPECS.get(p.kind, {})
                    if spec.get("type") == "instant":
                        if p.kind == "heal":
                            state.hp = min(state.hp + 30, state.max_hp)
                        elif p.kind == "clearscreen":
                            self._clear_screen()
                    else:
                        add_buff(state.buffs, p.kind, spec.get("duration", 8.0))
                    self.props.remove(p)
                    # 拾取道具音效（通过snapshot中的标志通知客户端播放）
                    self.prop_picked_this_frame = True
            # coins (evolution)
            for c in list(self.coins):
                if rect_collide(state.entity.rect, c.rect):
                    state.evo_coin_count += c.value
                    while state.evo_coin_count >= 3 and state.evolution_level < 5:
                        state.evo_coin_count -= 3
                        state.evolution_level += 1
                        state.hp = state.max_hp
                        state.evolve_effect_until = time.time() + 1.0
                        if state.evolution_level >= 5 and state.revives < 1:
                            state.revives = 1
                    self.coins.remove(c)

        now = time.time()
        self.props = [p for p in self.props if now - p.spawn < p.ttl]

    def _clear_screen(self) -> None:
        for e in list(self.enemies):
            self._on_enemy_killed(e, force_drop=False)
        self.enemies.clear()
        self.enemy_bullets.clear()

    def _on_enemy_killed(self, enemy: Enemy, force_drop: bool = True) -> None:
        is_boss = hasattr(enemy, "enemy_type_enum") and enemy.enemy_type_enum == EnemyType.BOSS

        # score & combo distribute evenly
        for state in self.players.values():
            now = time.time()
            if now - state.combo_last_hit <= 2.0:
                state.combo += 1
            else:
                state.combo = 1
            state.combo_last_hit = now
            base_score = getattr(enemy, "score_value", 10)
            gain = base_score * max(1, state.combo // 5)
            if buff_active(state.buffs, "x2"):
                gain *= 2
            state.score += gain

        if force_drop:
            drop_rate = DROP_RATE.get("normal", 0.30)
            if hasattr(enemy, "enemy_type_enum") and enemy.enemy_type_enum:
                spec = get_enemy_type_spec(enemy.enemy_type_enum)
                drop_rate *= spec.drop_rate_multiplier
            if random.random() < drop_rate:
                kind = choose_prop_kind("normal")
                if kind:
                    self.props.append(Prop(kind, enemy.rect.centerx, enemy.rect.centery))

        if is_boss:
            # Boss死亡：两辆战机自动获得一个进化币（不掉落）
            for state in self.players.values():
                if state.evolution_level < 5:
                    state.evo_coin_count += 1
                    # 如果达到3个，自动进化
                    while state.evo_coin_count >= 3 and state.evolution_level < 5:
                        state.evo_coin_count -= 3
                        state.evolution_level += 1
                        state.hp = state.max_hp
                        state.evolve_effect_until = time.time() + 1.0
                        if state.evolution_level >= 5 and state.revives < 1:
                            state.revives = 1
            # Boss被击杀后进入下一步并重置步点时间（与单人模式一致）
            self._advance_step()
            self.last_step_time = time.time()
            self.step_boss_summoned = False

        self.spawner.on_enemy_killed(enemy)

    def _advance_step(self) -> None:
        now = time.time()
        self.last_step_duration = now - self.last_step_time
        self.last_step_time = now
        self.enemy_speed_step_mult = 1.06 if self.last_step_duration > 35.0 else 1.08
        self.power_step += 1
        self.enemyspeed = self.enemy_speed_step_mult
        self.enemy_cap = min(140, self.enemy_cap + 6)
        self.fire_interval = max(0.7, self.fire_interval * 0.92)
        self.spawn_interval = max(0.7, self.spawn_interval * 0.85)
        if self.power_step % 3 == 0:
            self.burst_max = min(4, self.burst_max + 1)

        for state in self.players.values():
            if self.power_step % 2 == 0:
                add_buff(state.buffs, "haste", 4.0)

    # ------------------------------------------------------------------ Snapshot
    def snapshot(self) -> Dict:
        players_payload = {}
        for pid, state in self.players.items():
            players_payload[pid] = {
                "x": state.entity.rect.x,
                "y": state.entity.rect.y,
                "hp": state.hp,
                "hp_max": state.max_hp,
                "score": state.score,
                "evo_level": state.evolution_level,
                "evo_coins": state.evo_coin_count,
                "revives": state.revives,
                "buffs": {k: max(0, int(v - time.time())) for k, v in state.buffs.items() if v > time.time()},
            }

        enemies_payload = [
            {
                "x": e.rect.x,
                "y": e.rect.y,
                "w": e.rect.width,
                "h": e.rect.height,
                "id": getattr(e, "net_uid", id(e)),
                "type": getattr(e, "enemy_type_enum", None).name if getattr(e, "enemy_type_enum", None) else "default",
                "hp": getattr(e, "hp", 0),
                "hp_max": getattr(e, "max_hp", 0),
                "variant": getattr(e, "sprite_variant", None),
            }
            for e in self.enemies
        ]

        bullets_payload = [
            {"x": b.rect.x, "y": b.rect.y, "w": b.rect.width, "h": b.rect.height}
            for b in self.player_bullets
        ]
        enemy_bullets_payload = [
            {"x": b.rect.x, "y": b.rect.y, "w": b.rect.width, "h": b.rect.height}
            for b in self.enemy_bullets
        ]

        props_payload = [{"x": p.rect.x, "y": p.rect.y, "kind": p.kind} for p in self.props]
        coins_payload = [{"x": c.rect.x, "y": c.rect.y, "value": c.value} for c in self.coins]

        boss_spawned = self.boss_spawned_this_frame
        self.boss_spawned_this_frame = False  # 重置标志

        prop_picked = self.prop_picked_this_frame
        self.prop_picked_this_frame = False  # 重置标志

        # 更新背景索引（每20秒切换一次，与步点同步）
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.bg_index = int(elapsed / 20.0) % 4  # 4个背景循环
        bg_index = self.bg_index

        return {
            "players": players_payload,
            "enemies": enemies_payload,
            "player_bullets": bullets_payload,
            "enemy_bullets": enemy_bullets_payload,
            "props": props_payload,
            "coins": coins_payload,
            "power_step": self.power_step,
            "bg_index": bg_index,  # 背景索引（同步）
            "boss_spawned": boss_spawned,  # Boss出场标志
            "prop_picked": prop_picked,  # 道具拾取标志
            "spawn_interval": self.spawn_interval,
            "enemy_cap": self.enemy_cap,
            "start_time": self.start_time if self.start_time is not None else 0.0,
            "boss_spawn_event_id": self.boss_spawn_event_id,
            "tick": int(time.time() * 1000),
        }


