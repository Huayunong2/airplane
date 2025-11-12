"""
Boss系统
处理Boss的生成、弹道和特殊行为
"""
import math
import random
from typing import List, Tuple, Optional
import pygame
from core.entities import Bullet
from game.enemy_types import EnemyType, get_enemy_type_spec, scale_enemy_spec_for_power_step


class BossBulletPattern:
    """Boss弹道模式"""
    
    @staticmethod
    def straight_down(x: float, y: float, speed: float) -> List[Bullet]:
        """直线向下"""
        return [Bullet(x, y, 12, 20, (255, 100, 100), speed, 0.0, 1.0, 50.0)]
    
    @staticmethod
    def spread_three(x: float, y: float, speed: float) -> List[Bullet]:
        """三发扇形"""
        bullets = []
        angles = [-0.3, 0.0, 0.3]
        for angle in angles:
            vx = math.sin(angle) * speed
            vy = math.cos(angle) * speed
            bullets.append(Bullet(x, y, 12, 20, (255, 150, 100), speed, vx / speed, vy / speed, 50.0))
        return bullets
    
    @staticmethod
    def spread_five(x: float, y: float, speed: float) -> List[Bullet]:
        """五发扇形"""
        bullets = []
        angles = [-0.5, -0.25, 0.0, 0.25, 0.5]
        for angle in angles:
            vx = math.sin(angle) * speed
            vy = math.cos(angle) * speed
            bullets.append(Bullet(x, y, 12, 20, (255, 120, 100), speed, vx / speed, vy / speed, 50.0))
        return bullets
    
    @staticmethod
    def circle_pattern(x: float, y: float, speed: float, count: int = 8) -> List[Bullet]:
        """圆形弹幕"""
        bullets = []
        for i in range(count):
            angle = (2 * math.pi * i) / count
            vx = math.sin(angle)
            vy = math.cos(angle)
            bullets.append(Bullet(x, y, 10, 18, (255, 100, 150), speed, vx, vy, 40.0))
        return bullets
    
    @staticmethod
    def cross_pattern(x: float, y: float, speed: float) -> List[Bullet]:
        """十字弹幕"""
        bullets = []
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)]
        for dx, dy in directions:
            length = math.sqrt(dx*dx + dy*dy)
            vx = dx / length
            vy = dy / length
            bullets.append(Bullet(x, y, 10, 18, (255, 130, 130), speed, vx, vy, 45.0))
        return bullets


class BossController:
    """Boss控制器"""
    
    def __init__(self, boss_enemy, power_step: int = 0):
        self.boss = boss_enemy
        self.power_step = power_step
        self.fire_timer = 0.0
        self.pattern_index = 0
        self.patterns = [
            BossBulletPattern.straight_down,
            BossBulletPattern.spread_three,
            BossBulletPattern.spread_five,
            BossBulletPattern.circle_pattern,
            BossBulletPattern.cross_pattern,
        ]
        # 根据power_step调整射击间隔（越强射击越快）
        self.fire_interval = max(1.0, 2.5 - (power_step * 0.05))
        # 出场引导（从屏幕外缓慢下移到目标Y）
        self.intro = True
        self.intro_target_y = max(60, boss_enemy.rect.y)  # 目标Y（创建时会被设置为实际目标）
        self.intro_elapsed = 0.0
        self.intro_duration = 1.4
    
    def update(self, dt: float, screen_width: int) -> List[Bullet]:
        """
        更新Boss状态并生成子弹
        :param dt: 时间差
        :param screen_width: 屏幕宽度
        :return: 新生成的子弹列表
        """
        bullets = []

        # 出场过渡：从屏幕外慢慢显现
        if self.intro:
            self.intro_elapsed += dt
            t = min(1.0, self.intro_elapsed / self.intro_duration)
            # Ease-out 下移
            cur_y = int((1.0 - (1.0 - t) * (1.0 - t)) * (self.intro_target_y + 120)) - 120
            if cur_y >= self.intro_target_y:
                cur_y = self.intro_target_y
                self.intro = False
            self.boss.rect.y = cur_y
        
        # Boss在屏幕上方左右移动（使用独立的水平速度）
        if not hasattr(self.boss, "_h_speed"):
            self.boss._h_speed = 80.0  # 水平移动速度
        if self.boss.rect.x < 100:
            self.boss._h_speed = abs(self.boss._h_speed)
        elif self.boss.rect.x > screen_width - 100 - self.boss.rect.width:
            self.boss._h_speed = -abs(self.boss._h_speed)
        self.boss.rect.x += int(self.boss._h_speed * dt)
        
        # 射击逻辑
        self.fire_timer += dt
        if self.fire_timer >= self.fire_interval:
            self.fire_timer = 0.0
            
            # 根据power_step选择弹道模式
            # 前10步：简单模式
            # 10-30步：中等模式
            # 30+步：复杂模式
            if self.power_step < 10:
                pattern_func = self.patterns[self.pattern_index % 3]  # 前3种
            elif self.power_step < 30:
                pattern_func = self.patterns[self.pattern_index % 4]  # 前4种
            else:
                pattern_func = self.patterns[self.pattern_index % len(self.patterns)]  # 全部
            
            # 生成子弹
            center_x = self.boss.rect.centerx
            center_y = self.boss.rect.bottom
            bullet_speed = 300.0 + (self.power_step * 10.0)  # 子弹速度随power_step增强
            
            if pattern_func == BossBulletPattern.circle_pattern:
                new_bullets = pattern_func(center_x, center_y, bullet_speed, 8 + (self.power_step // 5))
            else:
                new_bullets = pattern_func(center_x, center_y, bullet_speed)
            
            bullets.extend(new_bullets)
            
            # 切换下一个模式
            self.pattern_index = (self.pattern_index + 1) % len(self.patterns)
        
        return bullets
    
    def is_alive(self) -> bool:
        """检查Boss是否存活"""
        return self.boss.hp > 0


def create_boss(x: int, y: int, power_step: int, enemy_images: dict) -> Tuple:
    """
    创建Boss敌机
    :param x: X坐标
    :param y: Y坐标
    :param power_step: 当前增强步数
    :param enemy_images: 预加载的敌机图片字典
    :return: (boss_enemy, boss_controller)
    """
    from core.entities import Enemy
    from game.enemy_types import EnemyType, get_enemy_type_spec, scale_enemy_spec_for_power_step
    import random
    
    # 获取Boss规格并增强
    base_spec = get_enemy_type_spec(EnemyType.BOSS)
    enhanced_spec = scale_enemy_spec_for_power_step(base_spec, power_step)
    
    # 创建Boss敌机
    # 先从屏幕外生成，稍后缓慢进入到 y
    boss = Enemy(x, -enhanced_spec.size[1] - 40, "boss")
    boss.enemy_type_enum = EnemyType.BOSS
    boss.hp = enhanced_spec.hp
    boss.max_hp = enhanced_spec.hp
    boss.speed = enhanced_spec.speed_base * 0.5  # Boss移动较慢
    boss.rect.width = enhanced_spec.size[0]
    boss.rect.height = enhanced_spec.size[1]
    boss.score_value = enhanced_spec.score_value
    
    # 加载Boss图片（如果有）
    if EnemyType.BOSS in enemy_images and enemy_images[EnemyType.BOSS]:
        sprites = enemy_images[EnemyType.BOSS]
        if sprites:
            variant_idx = random.randrange(len(sprites))
            boss.sprite_variant = variant_idx
            boss.image = sprites[variant_idx]
    else:
        # 使用占位符或默认颜色
        boss.color = (200, 50, 50)
    
    # 创建Boss控制器
    controller = BossController(boss, power_step)
    controller.intro_target_y = y
    
    return boss, controller

