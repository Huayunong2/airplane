"""
无尽模式敌机生成器
支持多机型概率生成和Boss系统
"""
import random
import time
from typing import List, Optional, Tuple
from core.entities import Enemy
from game.enemy_types import (
    EnemyType, 
    choose_enemy_type, 
    get_enemy_type_spec, 
    scale_enemy_spec_for_power_step,
    load_enemy_images
)
from game.boss_system import create_boss, BossController


class EndlessSpawner:
    """无尽模式生成器"""
    
    def __init__(self, screen_width: int, enemy_images: dict):
        self.screen_width = screen_width
        self.enemy_images = enemy_images
        self.last_spawn = time.time()
        self.boss_controller: Optional[BossController] = None
        self.boss_enemy: Optional[Enemy] = None
        self.wave_kill_count = 0  # 当前波次击杀数
        self.wave_target_kills = 15  # 每波需要击杀数（会随power_step增加）
        self.current_wave = 0
    
    def spawn_enemy(self, power_step: int, spawn_interval: float, enemy_cap: int) -> Optional[Enemy]:
        """
        生成一个普通敌机（根据机型概率）
        :param power_step: 当前增强步数
        :param spawn_interval: 生成间隔
        :param enemy_cap: 敌机上限
        :return: 生成的敌机，如果无法生成则返回None
        """
        now = time.time()
        if now - self.last_spawn < spawn_interval:
            return None
        
        # 如果有Boss，不生成普通敌机
        if self.boss_enemy is not None and self.boss_enemy.hp > 0:
            return None
        
        # 选择机型
        etype = choose_enemy_type(power_step)
        spec = get_enemy_type_spec(etype)
        enhanced_spec = scale_enemy_spec_for_power_step(spec, power_step)
        
        # 生成敌机
        x = random.randint(40, max(40, self.screen_width - 40))
        enemy = Enemy(x, -40, etype.value)
        enemy.enemy_type_enum = etype
        enemy.hp = enhanced_spec.hp
        enemy.max_hp = enhanced_spec.hp
        enemy.speed = enhanced_spec.speed_base
        enemy.rect.width = enhanced_spec.size[0]
        enemy.rect.height = enhanced_spec.size[1]
        enemy.score_value = enhanced_spec.score_value
        
        # 加载图片
        if etype in self.enemy_images and self.enemy_images[etype]:
            sprites = self.enemy_images[etype]
            if sprites:
                variant_idx = random.randrange(len(sprites))
                enemy.sprite_variant = variant_idx
                enemy.image = sprites[variant_idx]
        else:
            # 根据机型设置默认颜色
            if etype == EnemyType.SMALL:
                enemy.color = (255, 150, 150)
            elif etype == EnemyType.MIDDLE:
                enemy.color = (255, 100, 100)
            elif etype == EnemyType.HEAVY:
                enemy.color = (200, 50, 50)
        
        self.last_spawn = now
        return enemy
    
    def should_spawn_boss(self, power_step: int) -> bool:
        """
        判断是否应该生成Boss
        :param power_step: 当前增强步数
        :return: 是否生成Boss
        """
        # 如果已经有Boss且存活，不生成新Boss
        if self.boss_enemy is not None and self.boss_enemy.hp > 0:
            return False
        
        # 每波击杀数达到目标时生成Boss
        # 目标击杀数随power_step增加
        target = self.wave_target_kills + (power_step // 5)
        return self.wave_kill_count >= target
    
    def spawn_boss(self, power_step: int) -> Tuple[Enemy, BossController]:
        """
        生成Boss
        :param power_step: 当前增强步数
        :return: (boss_enemy, boss_controller)
        """
        x = self.screen_width // 2 - 60  # Boss宽度120，居中
        y = 80
        boss, controller = create_boss(x, y, power_step, self.enemy_images)
        self.boss_enemy = boss
        self.boss_controller = controller
        return boss, controller
    
    def on_enemy_killed(self, enemy: Enemy) -> None:
        """敌机被击杀时调用"""
        # 如果是Boss，重置波次
        if enemy == self.boss_enemy:
            self.wave_kill_count = 0
            self.current_wave += 1
            self.wave_target_kills = 15 + (self.current_wave * 2)  # 每波增加2个目标
            self.boss_enemy = None
            self.boss_controller = None
        else:
            # 普通敌机，增加击杀数
            self.wave_kill_count += 1
    
    def has_boss(self) -> bool:
        """检查是否有存活的Boss"""
        return self.boss_enemy is not None and self.boss_enemy.hp > 0
    
    def get_boss_controller(self) -> Optional[BossController]:
        """获取Boss控制器"""
        return self.boss_controller

