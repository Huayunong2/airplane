"""
视觉特效模块
提供受击闪烁、连击反馈等视觉特效功能
"""
import time
import math
import pygame
from typing import Optional, List, Tuple


class HitFlash:
    """受击闪烁效果"""
    
    def __init__(self, duration: float = 0.3, flash_count: int = 3):
        """
        Args:
            duration: 闪烁总持续时间（秒）
            flash_count: 闪烁次数
        """
        self.duration = duration
        self.flash_count = flash_count
        self.start_time: Optional[float] = None
        self.active = False
    
    def trigger(self) -> None:
        """触发闪烁效果"""
        self.start_time = time.time()
        self.active = True
    
    def update(self) -> None:
        """更新闪烁状态"""
        if not self.active or self.start_time is None:
            return
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            self.active = False
            self.start_time = None
    
    def get_alpha(self) -> int:
        """
        获取当前透明度（0-255）
        返回0表示完全透明（闪烁），255表示完全不透明
        """
        if not self.active or self.start_time is None:
            return 255
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            return 255
        
        # 正弦波闪烁：0-1之间振荡
        progress = elapsed / self.duration
        cycle = progress * self.flash_count * 2 * math.pi
        alpha_factor = (math.sin(cycle) + 1) / 2  # 0-1之间
        # 在0.2-1.0之间变化，让闪烁更明显
        alpha_factor = 0.2 + alpha_factor * 0.8
        return int(255 * alpha_factor)
    
    def get_tint_color(self) -> Optional[Tuple[int, int, int]]:
        """
        获取闪烁时的颜色（红色调）
        返回None表示不需要颜色调整
        """
        if not self.active or self.start_time is None:
            return None
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            return None
        
        # 闪烁时添加红色调
        alpha_factor = 1.0 - (self.get_alpha() / 255.0)
        tint_strength = int(100 * alpha_factor)
        return (255, 200 - tint_strength, 200 - tint_strength)


class ComboFeedback:
    """连击视觉反馈"""
    
    def __init__(self, duration: float = 1.5):
        """
        Args:
            duration: 显示持续时间（秒）
        """
        self.duration = duration
        self.combo_value: int = 0
        self.start_time: Optional[float] = None
        self.active = False
        self.position: Tuple[int, int] = (0, 0)
    
    def trigger(self, combo: int, position: Tuple[int, int]) -> None:
        """
        触发连击反馈
        
        Args:
            combo: 连击数
            position: 显示位置（屏幕坐标）
        """
        if combo < 2:  # 连击数小于2不显示
            return
        
        self.combo_value = combo
        self.position = position
        self.start_time = time.time()
        self.active = True
    
    def update(self) -> None:
        """更新反馈状态"""
        if not self.active or self.start_time is None:
            return
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            self.active = False
            self.start_time = None
    
    def get_alpha(self) -> int:
        """获取当前透明度（0-255）"""
        if not self.active or self.start_time is None:
            return 0
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            return 0
        
        # 淡入淡出效果
        if elapsed < 0.2:  # 前0.2秒淡入
            return int(255 * (elapsed / 0.2))
        elif elapsed > self.duration - 0.3:  # 最后0.3秒淡出
            fade_out = (self.duration - elapsed) / 0.3
            return int(255 * fade_out)
        else:
            return 255
    
    def get_scale(self) -> float:
        """获取当前缩放比例（用于弹跳效果）"""
        if not self.active or self.start_time is None:
            return 1.0
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            return 1.0
        
        # 弹跳效果：开始时放大，然后回弹
        if elapsed < 0.3:
            # 0-0.3秒：从1.5倍缩放到1.0倍
            progress = elapsed / 0.3
            return 1.5 - (progress * 0.5)
        else:
            # 轻微回弹
            bounce = math.sin((elapsed - 0.3) * 10) * 0.05
            return 1.0 + bounce
    
    def render(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """渲染连击反馈"""
        if not self.active or self.combo_value < 2:
            return
        
        alpha = self.get_alpha()
        if alpha <= 0:
            return
        
        scale = self.get_scale()
        
        # 根据连击数选择颜色和文字
        if self.combo_value < 5:
            color = (255, 255, 200)  # 黄色
            text = f"连击 x{self.combo_value}!"
        elif self.combo_value < 10:
            color = (255, 200, 100)  # 橙色
            text = f"连击 x{self.combo_value}!"
        elif self.combo_value < 20:
            color = (255, 150, 150)  # 红色
            text = f"连击 x{self.combo_value}!"
        else:
            color = (255, 100, 255)  # 紫色
            text = f"疯狂连击 x{self.combo_value}!"
        
        # 创建文字表面
        text_surf = font.render(text, True, color)
        
        # 应用缩放
        if scale != 1.0:
            new_size = (int(text_surf.get_width() * scale), int(text_surf.get_height() * scale))
            text_surf = pygame.transform.scale(text_surf, new_size)
        
        # 应用透明度
        if alpha < 255:
            text_surf.set_alpha(alpha)
        
        # 计算位置（居中显示）
        x = self.position[0] - text_surf.get_width() // 2
        y = self.position[1] - text_surf.get_height() // 2
        
        # 绘制阴影效果
        shadow_surf = font.render(text, True, (0, 0, 0))
        if scale != 1.0:
            shadow_surf = pygame.transform.scale(shadow_surf, new_size)
        shadow_surf.set_alpha(alpha // 3)
        screen.blit(shadow_surf, (x + 2, y + 2))
        
        # 绘制文字
        screen.blit(text_surf, (x, y))


class VisualEffectManager:
    """视觉特效管理器（统一管理所有特效）"""
    
    def __init__(self):
        self.hit_flash = HitFlash()
        self.combo_feedbacks: List[ComboFeedback] = []
        self.max_combo_feedbacks = 3  # 最多同时显示3个连击反馈
    
    def trigger_hit_flash(self) -> None:
        """触发受击闪烁"""
        self.hit_flash.trigger()
    
    def trigger_combo_feedback(self, combo: int, position: Tuple[int, int]) -> None:
        """触发连击反馈"""
        # 如果已有太多反馈，移除最旧的
        if len(self.combo_feedbacks) >= self.max_combo_feedbacks:
            self.combo_feedbacks.pop(0)
        
        feedback = ComboFeedback()
        feedback.trigger(combo, position)
        self.combo_feedbacks.append(feedback)
    
    def update(self) -> None:
        """更新所有特效"""
        self.hit_flash.update()
        for feedback in self.combo_feedbacks:
            feedback.update()
        # 移除已结束的反馈
        self.combo_feedbacks = [f for f in self.combo_feedbacks if f.active]
    
    def apply_hit_flash_to_surface(self, surface: pygame.Surface) -> Optional[pygame.Surface]:
        """
        将受击闪烁效果应用到表面
        返回处理后的表面（如果需要），如果不需要处理则返回None
        """
        if not self.hit_flash.active:
            return None
        
        alpha = self.hit_flash.get_alpha()
        tint_color = self.hit_flash.get_tint_color()
        
        if tint_color is not None or alpha < 255:
            # 创建带效果的副本
            result = surface.copy()
            
            if tint_color is not None:
                # 使用混合模式添加红色调
                overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                overlay.fill((*tint_color, 128))
                result.blit(overlay, (0, 0), special_flags=pygame.BLEND_MULT)
            
            if alpha < 255:
                result.set_alpha(alpha)
            
            return result
        
        return None
    
    def render_combo_feedbacks(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """渲染所有连击反馈"""
        for feedback in self.combo_feedbacks:
            feedback.render(screen, font)
    
    def reset(self) -> None:
        """重置所有特效状态"""
        self.hit_flash.active = False
        self.hit_flash.start_time = None
        self.combo_feedbacks.clear()

