from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
import pygame


Color = Tuple[int, int, int]


@dataclass
class BaseEntity:
    rect: pygame.Rect
    color: Color
    speed: float
    hp: int

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect)


class Player(BaseEntity):
    def __init__(self, x: int, y: int) -> None:
        super().__init__(pygame.Rect(x, y, 40, 40), (80, 200, 255), 320.0, 100)

    def handle_input(self, keys: pygame.key.ScancodeWrapper, dt: float) -> None:
        dx = dy = 0.0
        if keys[pygame.K_w]:
            dy -= self.speed * dt
        if keys[pygame.K_s]:
            dy += self.speed * dt
        if keys[pygame.K_a]:
            dx -= self.speed * dt
        if keys[pygame.K_d]:
            dx += self.speed * dt
        self.rect.x += int(dx)
        self.rect.y += int(dy)


class Enemy(BaseEntity):
    def __init__(self, x: int, y: int, enemy_type: Optional[str] = None) -> None:
        """
        初始化敌机
        :param x: X坐标
        :param y: Y坐标
        :param enemy_type: 机型类型（"small", "middle", "heavy", "boss"），None表示默认机型
        """
        # 默认值（用于限时模式等非无尽模式）
        super().__init__(pygame.Rect(x, y, 36, 36), (255, 100, 100), 120.0, 30)
        self.enemy_type = enemy_type  # 机型类型
        self.enemy_type_enum = None  # EnemyType枚举（由外部设置）
        self.image = None  # 机型图片（由外部设置）
        self.max_hp = self.hp  # 最大生命值（用于Boss血条显示等）
        self.score_value = 20  # 击毁得分

    def update(self, dt: float) -> None:
        self.rect.y += int(self.speed * dt)


class Bullet(BaseEntity):
    def __init__(
        self,
        x: int,
        y: int,
        width: int = 8,
        height: int = 16,
        color: Color = (255, 255, 100),
        speed: float = 500.0,
        vx: float = 0.0,
        vy: float = -1.0,
        damage: float = 30.0,
        pierce: int = 0,
    ) -> None:
        super().__init__(pygame.Rect(x, y, width, height), color, speed, 1)
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.pierce = pierce
        self._fx = float(x)
        self._fy = float(y)

    def update(self, dt: float) -> None:
        self._fx += self.vx * self.speed * dt
        self._fy += self.vy * self.speed * dt
        self.rect.x = int(self._fx)
        self.rect.y = int(self._fy)

