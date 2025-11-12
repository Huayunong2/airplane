"""
敌机机型系统
定义不同机型的特征、数值和刷新概率
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import random
import os
from utils import assets


class EnemyType(Enum):
    """敌机机型枚举"""
    SMALL = "small"      # 小型机
    MIDDLE = "middle"    # 中型机
    HEAVY = "heavy"      # 重型机
    BOSS = "boss"        # Boss机


@dataclass
class EnemyTypeSpec:
    """机型规格定义"""
    type: EnemyType
    name: str
    hp: int                    # 生命值
    speed_base: float          # 基础速度
    size: Tuple[int, int]      # 尺寸 (width, height)
    spawn_weight: float        # 刷新权重（越高越容易刷新）
    image_paths: List[str]     # 该机型的图片路径列表
    score_value: int           # 击毁得分
    drop_rate_multiplier: float = 1.0  # 掉落率倍数
    
    def get_random_image(self) -> Optional[str]:
        """随机获取该机型的一张图片"""
        if not self.image_paths:
            return None
        return random.choice(self.image_paths)


# 机型规格配置（基础值，会在无尽模式中根据power_step增强）
ENEMY_TYPE_SPECS = {
    EnemyType.SMALL: EnemyTypeSpec(
        type=EnemyType.SMALL,
        name="小型机",
        hp=20,
        speed_base=150.0,
        size=(32, 32),
        spawn_weight=50.0,  # 最高刷新率
        image_paths=[
            "enemy/small/small1.png",
            "enemy/small/small2.png",
            "enemy/small/small3.png",
            "enemy/small/small4.png",
            "enemy/small/small5.png",
            "enemy/small/small6.png",
        ],
        score_value=10,
        drop_rate_multiplier=0.8,  # 小型机掉落率稍低
    ),
    EnemyType.MIDDLE: EnemyTypeSpec(
        type=EnemyType.MIDDLE,
        name="中型机",
        hp=60,
        speed_base=120.0,
        size=(48, 48),
        spawn_weight=25.0,  # 中等刷新率
        image_paths=[
            "enemy/middle/middle1.png",
            "enemy/middle/middle2.png",
            "enemy/middle/middle3.png",
            "enemy/middle/middle4.png",
            "enemy/middle/middle5.png",
        ],
        score_value=30,
        drop_rate_multiplier=1.2,  # 中型机掉落率稍高
    ),
    EnemyType.HEAVY: EnemyTypeSpec(
        type=EnemyType.HEAVY,
        name="重型机",
        hp=150,
        speed_base=90.0,
        size=(64, 64),
        spawn_weight=10.0,  # 较低刷新率
        image_paths=["enemy/heavy/heavy1.png", "enemy/heavy/heavy2.png", "enemy/heavy/heavy3.png"],
        score_value=80,
        drop_rate_multiplier=1.5,  # 重型机掉落率更高
    ),
    EnemyType.BOSS: EnemyTypeSpec(
        type=EnemyType.BOSS,
        name="Boss机",
        hp=500,
        speed_base=60.0,
        size=(120, 120),
        spawn_weight=0.0,  # Boss不参与随机刷新
        image_paths=["enemy/boss/boss_placeholder.png", "enemy/boss/boss1.png"],
        score_value=500,
        drop_rate_multiplier=2.0,  # Boss掉落率最高
    ),
}


def choose_enemy_type(power_step: int = 0) -> EnemyType:
    """
    根据权重随机选择机型
    :param power_step: 当前增强步数，用于调整权重
    :return: 选中的机型
    """
    # 排除Boss（Boss由特殊逻辑生成）
    available_types = [t for t in EnemyType if t != EnemyType.BOSS]
    
    # 根据power_step调整权重（越往后，重型机权重相对提高）
    weights = []
    for etype in available_types:
        spec = ENEMY_TYPE_SPECS[etype]
        # 每10步，重型机权重+2，中型机权重+1，小型机权重不变
        weight_adjust = 0.0
        if etype == EnemyType.HEAVY:
            weight_adjust = (power_step // 10) * 2.0
        elif etype == EnemyType.MIDDLE:
            weight_adjust = (power_step // 10) * 1.0
        
        weights.append(spec.spawn_weight + weight_adjust)
    
    # 加权随机选择
    total_weight = sum(weights)
    if total_weight <= 0:
        return EnemyType.SMALL  # 默认返回小型机
    
    r = random.uniform(0, total_weight)
    cumulative = 0.0
    for i, etype in enumerate(available_types):
        cumulative += weights[i]
        if r <= cumulative:
            return etype
    
    return available_types[-1]  # 兜底返回最后一个


def get_enemy_type_spec(etype: EnemyType) -> EnemyTypeSpec:
    """获取机型规格"""
    return ENEMY_TYPE_SPECS[etype]


def load_enemy_images() -> dict:
    """
    预加载所有敌机图片
    返回 {EnemyType: [pygame.Surface, ...]}
    """
    loaded = {}
    for etype, spec in ENEMY_TYPE_SPECS.items():
        surfaces = []
        for img_path in spec.image_paths:
            surf = assets.load_image(img_path, size=spec.size)
            if surf is not None:
                surfaces.append(surf)
        loaded[etype] = surfaces
    return loaded


def scale_enemy_spec_for_power_step(spec: EnemyTypeSpec, power_step: int) -> EnemyTypeSpec:
    """
    根据power_step增强机型规格（用于无尽模式）
    :param spec: 基础规格
    :param power_step: 当前增强步数
    :return: 增强后的规格（新实例，不修改原规格）
    """
    # 每步增强系数
    hp_multiplier = 1.0 + (power_step * 0.05)  # 每步+5%生命
    speed_multiplier = 1.0 + (power_step * 0.08)  # 每步+8%速度（与全局增强一致）
    
    # 创建增强后的规格
    enhanced = EnemyTypeSpec(
        type=spec.type,
        name=spec.name,
        hp=int(spec.hp * hp_multiplier),
        speed_base=spec.speed_base * speed_multiplier,
        size=spec.size,
        spawn_weight=spec.spawn_weight,
        image_paths=spec.image_paths,
        score_value=int(spec.score_value * (1.0 + power_step * 0.1)),  # 得分也增加
        drop_rate_multiplier=spec.drop_rate_multiplier,
    )
    return enhanced

