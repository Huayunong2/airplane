import math
import time
from typing import List, Tuple
from core.entities import Bullet, Player
from game.props_system import buff_active


def compute_fire_cooldown(base_cooldown: float, buffs: dict) -> float:
    return base_cooldown * (0.6 if buff_active(buffs, "haste") else 1.0)


def create_player_bullets(player: Player, buffs: dict, base_speed: float, base_damage: float, base_size: Tuple[int, int]) -> List[Bullet]:
    angles = [0.0]
    if buff_active(buffs, "spread"):
        angles = [-0.35, -0.18, 0.0, 0.18, 0.35]
    width, height = base_size
    damage = base_damage
    color = (255, 255, 120)
    if buff_active(buffs, "power"):
        width = 12
        height = 22
        damage *= 1.5
        color = (255, 160, 120)
    pierce = 2 if buff_active(buffs, "piercing") else 0

    bullets: List[Bullet] = []
    for ang in angles:
        vx = math.sin(ang)
        vy = -math.cos(ang)
        mag = math.hypot(vx, vy) or 1.0
        vx /= mag
        vy /= mag
        bullets.append(
            Bullet(
                player.rect.centerx - width // 2,
                player.rect.top - height,
                width=width,
                height=height,
                color=color,
                speed=base_speed,
                vx=vx,
                vy=vy,
                damage=damage,
                pierce=pierce,
            )
        )
    return bullets

