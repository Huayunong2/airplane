"""
暂停菜单模块
提供游戏暂停时的菜单功能
"""
import pygame
from typing import Callable, Optional, List, Tuple
from utils import assets


def choose_font(size: int):
    """选择字体"""
    if not pygame.get_init():
        pygame.init()
    pygame.font.init()
    return pygame.font.SysFont("Microsoft YaHei", size) or pygame.font.SysFont(None, size)


class PauseMenu:
    """暂停菜单"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font_big = choose_font(36)
        self.font = choose_font(24)
        self.font_small = choose_font(18)
        
        # 菜单选项
        self.menu_items = [
            {"key": "resume", "text": "继续游戏", "enabled": True},
            {"key": "restart", "text": "重新开始", "enabled": True},
            {"key": "settings", "text": "设置", "enabled": True},
            {"key": "main_menu", "text": "返回主菜单", "enabled": True},
        ]
        
        self.selected_index = 0
        self.visible = False
    
    def show(self) -> None:
        """显示暂停菜单"""
        self.visible = True
        self.selected_index = 0
    
    def hide(self) -> None:
        """隐藏暂停菜单"""
        self.visible = False
    
    def handle_key(self, key: int) -> Optional[str]:
        """
        处理按键输入
        
        Args:
            key: pygame按键常量
            
        Returns:
            选中的菜单项key，如果未选择则返回None
        """
        if not self.visible:
            return None
        
        if key == pygame.K_ESCAPE:
            # ESC返回游戏
            return "resume"
        elif key in (pygame.K_UP, pygame.K_w):
            self.selected_index = (self.selected_index - 1) % len(self.menu_items)
            assets.play_sound("ui/menu_move.wav", 0.5)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected_index = (self.selected_index + 1) % len(self.menu_items)
            assets.play_sound("ui/menu_move.wav", 0.5)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            item = self.menu_items[self.selected_index]
            if item["enabled"]:
                assets.play_sound("bgm/click.ogg", 0.6)
                return item["key"]
        
        return None
    
    def render(self, screen: pygame.Surface, dim_overlay: Optional[pygame.Surface] = None) -> None:
        """
        渲染暂停菜单
        
        Args:
            screen: 目标表面
            dim_overlay: 可选的暗化遮罩（如果为None则自动创建）
        """
        if not self.visible:
            return
        
        # 绘制暗化遮罩
        if dim_overlay is None:
            dim_overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            dim_overlay.fill((0, 0, 0, 180))  # 半透明黑色
        screen.blit(dim_overlay, (0, 0))
        
        # 标题
        title = self.font_big.render("游戏暂停", True, (255, 255, 255))
        title_x = self.screen_width // 2 - title.get_width() // 2
        title_y = self.screen_height // 2 - 150
        screen.blit(title, (title_x, title_y))
        
        # 菜单项
        start_y = self.screen_height // 2 - 50
        item_height = 50
        item_spacing = 10
        
        for i, item in enumerate(self.menu_items):
            y = start_y + i * (item_height + item_spacing)
            is_selected = (i == self.selected_index)
            
            # 选中高亮背景
            if is_selected:
                highlight_rect = pygame.Rect(
                    self.screen_width // 2 - 150,
                    y - 5,
                    300,
                    item_height
                )
                pygame.draw.rect(screen, (60, 80, 120, 200), highlight_rect)
                pygame.draw.rect(screen, (100, 140, 200), highlight_rect, 2)
            
            # 文字颜色
            if item["enabled"]:
                color = (255, 255, 200) if is_selected else (220, 220, 220)
            else:
                color = (120, 120, 120)
            
            # 渲染文字
            text_surf = self.font.render(item["text"], True, color)
            text_x = self.screen_width // 2 - text_surf.get_width() // 2
            screen.blit(text_surf, (text_x, y))
        
        # 提示文字
        hint = self.font_small.render("↑↓ 选择  Enter 确认  ESC 继续", True, (180, 180, 180))
        hint_x = self.screen_width // 2 - hint.get_width() // 2
        hint_y = self.screen_height - 80
        screen.blit(hint, (hint_x, hint_y))


def run_pause_menu(
    screen: pygame.Surface,
    dim_overlay: Optional[pygame.Surface] = None,
    on_resume: Optional[Callable[[], None]] = None,
    on_restart: Optional[Callable[[], None]] = None,
    on_settings: Optional[Callable[[], None]] = None,
    on_main_menu: Optional[Callable[[], None]] = None,
) -> str:
    """
    运行暂停菜单（阻塞式）
    
    Args:
        screen: 目标表面
        dim_overlay: 可选的暗化遮罩
        on_resume: 继续游戏回调
        on_restart: 重新开始回调
        on_settings: 设置回调
        on_main_menu: 返回主菜单回调
        
    Returns:
        选择的动作："resume" | "restart" | "settings" | "main_menu"
    """
    menu = PauseMenu(screen.get_width(), screen.get_height())
    menu.show()
    
    clock = pygame.time.Clock()
    running = True
    result = "resume"
    
    while running:
        clock.tick(60)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                result = "main_menu"
                running = False
            elif event.type == pygame.KEYDOWN:
                action = menu.handle_key(event.key)
                if action:
                    result = action
                    if action == "resume" and on_resume:
                        on_resume()
                    elif action == "restart" and on_restart:
                        on_restart()
                    elif action == "settings" and on_settings:
                        on_settings()
                    elif action == "main_menu" and on_main_menu:
                        on_main_menu()
                    running = False
        
        menu.render(screen, dim_overlay)
        pygame.display.flip()
    
    return result

