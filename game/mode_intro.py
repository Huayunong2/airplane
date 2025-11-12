"""
游戏模式介绍模块
提供限时模式和无尽模式的详细介绍界面
"""
import pygame
import pygame.freetype as ft
from typing import List, Tuple, Optional
from game.enemy_types import EnemyType, get_enemy_type_spec


def choose_font(size: int):
    """选择字体"""
    if not pygame.get_init():
        pygame.init()
    ft.init()
    candidates = [
        "Microsoft YaHei", "微软雅黑", "SimHei", "黑体",
        "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans CN",
        "WenQuanYi Micro Hei",
    ]
    for name in candidates:
        try:
            return ft.SysFont(name, size)
        except Exception:
            continue
    return ft.SysFont(None, size)


class ModeIntro:
    """游戏模式介绍界面"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # 字体
        self.font_title = choose_font(36)
        self.font_section = choose_font(28)
        self.font_text = choose_font(20)
        self.font_small = choose_font(18)
        
        # 滚动相关
        self.scroll_y = 0
        self.max_scroll = 0
        self.scroll_speed = 30
        
        # 获取模式数据
        self.timed_mode_data = self._get_timed_mode_data()
        self.endless_mode_data = self._get_endless_mode_data()
        self.enemy_specs = self._get_enemy_specs_data()

    def _spec_to_dict(self, etype: EnemyType) -> dict:
        spec = get_enemy_type_spec(etype)
        mode_note = "仅无尽模式" if etype == EnemyType.BOSS else "限时/无尽"
        return {
            "机型": spec.name,
            "生命值(HP)": spec.hp,
            "基础速度": f"{spec.speed_base:.1f}",
            "尺寸(W×H)": f"{spec.size[0]}×{spec.size[1]}",
            "击毁得分": spec.score_value,
            "掉落倍率": f"x{spec.drop_rate_multiplier:.1f}",
            "刷新权重": f"{spec.spawn_weight:.1f}",
            "适用模式": mode_note,
        }

    def _get_enemy_specs_data(self) -> List[Tuple[str, dict]]:
        data: List[Tuple[str, dict]] = []
        # 顺序：小型 -> 中型 -> 重型 -> Boss
        order = [EnemyType.SMALL, EnemyType.MIDDLE, EnemyType.HEAVY, EnemyType.BOSS]
        for et in order:
            d = self._spec_to_dict(et)
            data.append((d["机型"], d))
        return data
    
    def _get_timed_mode_data(self) -> dict:
        """获取限时模式数据"""
        return {
            "name": "限时模式",
            "description": "在限定时间内尽可能获得高分，时间结束后结算。现已支持多机型与多贴图随机，开局与关卡刷新均为随机机型（不包含Boss）。",
            "features": [
                "• 有时间限制，需要在规定时间内获得最高分数",
                "• 敌机会以随机机型出现（小型/中型/重型），并从各自多张贴图中随机显示",
                "• 不包含Boss（Boss仅在无尽模式出现）",
                "• 支持三种难度选择：简单、普通、困难",
                "• 不同难度下敌人参数和掉落率不同",
                "• 适合想要挑战固定难度和时间的玩家",
            ],
            "difficulties": {
                "easy": {
                    "name": "简单",
                    "params": {
                        "生成间隔": "3.0秒",
                        "敌机速度": "100.0",
                        "玩家生命": "120",
                        "敌机上限": "24",
                        "射击冷却": "3.0秒",
                        "连发次数": "0",
                        "掉落率": "35%",
                    }
                },
                "normal": {
                    "name": "普通",
                    "params": {
                        "生成间隔": "2.4秒",
                        "敌机速度": "135.0",
                        "玩家生命": "100",
                        "敌机上限": "28",
                        "射击冷却": "2.6秒",
                        "连发次数": "1",
                        "掉落率": "30%",
                    }
                },
                "hard": {
                    "name": "困难",
                    "params": {
                        "生成间隔": "1.8秒",
                        "敌机速度": "175.0",
                        "玩家生命": "90",
                        "敌机上限": "42",
                        "射击冷却": "1.6秒",
                        "连发次数": "2",
                        "掉落率": "27%",
                    }
                },
            }
        }
    
    def _get_endless_mode_data(self) -> dict:
        """获取无尽模式数据"""
        return {
            "name": "无尽模式",
            "description": "没有时间限制，敌人会随时间逐步增强，挑战你的极限生存能力。所有机型与贴图均为随机，Boss仅在本模式出现。背景采用平滑淡入切换，避免闪屏。",
            "features": [
                "• 无时间限制，可以持续挑战",
                "• 每20秒敌人会增强一次（难度提升）",
                "• 玩家也会获得增强，但速度较慢",
                "• 敌人以多机型、多贴图随机出现，增加战场变化",
                "• 背景会随机切换（平滑淡入，无闪屏），增加视觉变化",
                "• Boss 会在达成一定击杀后出现，仅本模式包含",
                "• 适合想要挑战极限和长期生存的玩家",
            ],
            "difficulty_curve": {
                "enemy_enhancement": {
                    "speed": "每步 +8%",
                    "cap": "每步 +4（上限120）",
                    "fire_interval": "每步 ×0.92（最低0.7秒）",
                    "burst_max": "每3步 +1（上限4）",
                },
                "player_enhancement": {
                    "haste_buff": "每2步获得4秒加速效果",
                    "note": "玩家增强速度较敌人慢，需要合理利用道具",
                },
                "background_switch": {
                    "interval": "每20秒随机切换背景",
                    "effect": "视觉变化，不影响游戏性",
                },
            },
            "initial_params": {
                "生成间隔": "2.4秒",
                "敌机速度": "135.0",
                "玩家生命": "100",
                "敌机上限": "28",
                "射击冷却": "2.6秒",
                "连发次数": "1",
            }
        }
    
    def handle_key(self, key: int) -> Optional[str]:
        """
        处理按键输入
        返回 'back' 表示返回，None 表示继续显示
        """
        if key == pygame.K_ESCAPE:
            return "back"
        elif key == pygame.K_UP or key == pygame.K_w:
            self.scroll_y = max(0, self.scroll_y - self.scroll_speed)
        elif key == pygame.K_DOWN or key == pygame.K_s:
            self.scroll_y = min(self.max_scroll, self.scroll_y + self.scroll_speed)
        elif key == pygame.K_PAGEUP:
            self.scroll_y = max(0, self.scroll_y - self.screen_height // 2)
        elif key == pygame.K_PAGEDOWN:
            self.scroll_y = min(self.max_scroll, self.scroll_y + self.screen_height // 2)
        elif key == pygame.K_HOME:
            self.scroll_y = 0
        elif key == pygame.K_END:
            self.scroll_y = self.max_scroll
        return None
    
    def handle_mouse_wheel(self, dy: int) -> None:
        """处理鼠标滚轮"""
        self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - dy * 20))
    
    def _render_text_wrapped(
        self, 
        surface: pygame.Surface, 
        font: ft.Font, 
        text: str, 
        x: int, 
        y: int, 
        max_width: int, 
        color: Tuple[int, int, int] = (255, 255, 255)
    ) -> int:
        """
        渲染换行文本
        返回下一行的y坐标
        """
        words = text.split()
        lines: List[str] = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            text_rect = font.get_rect(test_line)
            if text_rect.width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        for line in lines:
            text_surf, _ = font.render(line, color)
            surface.blit(text_surf, (x, y))
            text_rect = font.get_rect(line)
            y += text_rect.height + 4
        
        return y
    
    def _render_section(
        self, 
        surface: pygame.Surface, 
        title: str, 
        content: List[str], 
        start_y: int, 
        indent: int = 0
    ) -> int:
        """渲染一个章节，返回结束y坐标"""
        y = start_y
        
        # 标题
        title_surf, _ = self.font_section.render(title, (40, 40, 40))
        surface.blit(title_surf, (indent, y))
        y += title_surf.get_height() + 15
        
        # 内容
        for line in content:
            if line.startswith("•"):
                color = (30, 30, 30)
            else:
                color = (20, 20, 20)
            y = self._render_text_wrapped(
                surface, 
                self.font_text, 
                line, 
                indent + 20, 
                y, 
                self.screen_width - indent - 40, 
                color
            )
            y += 8
        
        return y
    
    def _render_table(
        self, 
        surface: pygame.Surface, 
        data: dict, 
        start_y: int, 
        indent: int = 0
    ) -> int:
        """渲染参数表格，返回结束y坐标"""
        y = start_y
        cell_padding = 8
        col_width = (self.screen_width - indent - 40) // 2
        
        # 表头
        header_surf, _ = self.font_text.render("参数", (50, 50, 50))
        value_surf, _ = self.font_text.render("数值", (50, 50, 50))
        surface.blit(header_surf, (indent + 20, y))
        surface.blit(value_surf, (indent + 20 + col_width, y))
        header_rect = self.font_text.get_rect("参数")
        y += header_rect.height + cell_padding
        
        # 分隔线
        pygame.draw.line(
            surface, 
            (100, 100, 100), 
            (indent + 20, y - 4), 
            (indent + 20 + col_width * 2, y - 4)
        )
        y += cell_padding
        
        # 数据行
        for key, value in data.items():
            key_surf, _ = self.font_text.render(str(key), (30, 30, 30))
            value_surf, _ = self.font_text.render(str(value), (30, 30, 30))
            surface.blit(key_surf, (indent + 20, y))
            surface.blit(value_surf, (indent + 20 + col_width, y))
            key_rect = self.font_text.get_rect(str(key))
            y += key_rect.height + cell_padding
        
        return y
    
    def render(self, screen: pygame.Surface, dim_overlay: Optional[pygame.Surface] = None) -> None:
        """渲染介绍界面"""
        # 绘制暗色遮罩
        if dim_overlay:
            screen.blit(dim_overlay, (0, 0))
        
        # 创建内容表面（用于滚动）
        content_height = self._calculate_content_height()
        content_surface = pygame.Surface((self.screen_width, content_height), pygame.SRCALPHA)
        
        y = 20
        
        # 主标题
        title_surf, _ = self.font_title.render("游戏模式介绍", (50, 50, 50))
        content_surface.blit(title_surf, (self.screen_width // 2 - title_surf.get_width() // 2, y))
        y += title_surf.get_height() + 30
        
        # 限时模式
        y = self._render_mode_section(content_surface, self.timed_mode_data, y)
        y += 30
        
        # 无尽模式
        y = self._render_mode_section(content_surface, self.endless_mode_data, y)
        y += 30

        # 机型与参数（来自当前配置）
        title_specs, _ = self.font_section.render("机型与参数（实时配置）", (30, 30, 30))
        content_surface.blit(title_specs, (40, y))
        y += title_specs.get_height() + 10
        for name, data in self.enemy_specs:
            subsection_title, _ = self.font_text.render(f"{name}", (40, 40, 40))
            content_surface.blit(subsection_title, (60, y))
            y += subsection_title.get_height() + 8
            y = self._render_table(content_surface, data, y, 60)
            y += 10
        
        # 提示信息
        hint_text = "↑↓/PageUp/PageDown 滚动 | Home/End 跳转 | ESC 返回"
        hint_surf, _ = self.font_small.render(hint_text, (80, 80, 80))
        hint_rect = self.font_small.get_rect(hint_text)
        content_surface.blit(hint_surf, (self.screen_width // 2 - hint_rect.width // 2, y))
        
        # 更新最大滚动距离
        self.max_scroll = max(0, content_height - self.screen_height)
        self.scroll_y = min(self.scroll_y, self.max_scroll)
        
        # 绘制可见区域
        visible_rect = pygame.Rect(0, self.scroll_y, self.screen_width, self.screen_height)
        screen.blit(content_surface, (0, 0), visible_rect)
    
    def _calculate_content_height(self) -> int:
        """计算内容总高度"""
        y = 20
        y += 50  # 标题
        y += 30
        
        # 限时模式
        y += self._get_mode_section_height(self.timed_mode_data)
        y += 30
        
        # 无尽模式
        y += self._get_mode_section_height(self.endless_mode_data)
        y += 30

        # 机型与参数（标题 + 4个机型的小表格）
        y += 50  # 标题行
        for _ in range(4):
            y += 26  # 小标题
            # 行数按字段数估计（与 _spec_to_dict 一致）
            y += 8   # 分隔
            y += 8   # 表头
            y += 8 * 0  # 无固定额外行
            y += 8   # 分隔线
            y += 8 * 0
            y += 30 * 8  # 8 行参数
            y += 10  # 间距
        
        y += 30  # 提示
        
        return y + 50
    
    def _get_mode_section_height(self, mode_data: dict) -> int:
        """计算模式章节高度"""
        height = 0
        height += 50  # 模式名称
        height += 30  # 描述
        height += len(mode_data["features"]) * 30  # 特性列表
        
        if "difficulties" in mode_data:
            # 限时模式：难度表格
            for diff_data in mode_data["difficulties"].values():
                height += 50  # 难度名称
                height += 30  # 表格标题
                height += len(diff_data["params"]) * 30  # 参数行
                height += 20  # 间距
        elif "difficulty_curve" in mode_data:
            # 无尽模式：难度曲线
            height += 50  # 初始参数
            height += 30
            height += len(mode_data["initial_params"]) * 30
            height += 30
            height += 50  # 敌人增强
            height += 30
            height += len(mode_data["difficulty_curve"]["enemy_enhancement"]) * 30
            height += 30
            height += 50  # 玩家增强
            height += 30
            height += len(mode_data["difficulty_curve"]["player_enhancement"]) * 30
            height += 30
            height += 50  # 背景切换
            height += 30
            height += len(mode_data["difficulty_curve"]["background_switch"]) * 30
        
        return height
    
    def _render_mode_section(self, surface: pygame.Surface, mode_data: dict, start_y: int) -> int:
        """渲染模式章节，返回结束y坐标"""
        y = start_y
        
        # 模式名称
        name_surf, _ = self.font_section.render(mode_data["name"], (30, 30, 30))
        surface.blit(name_surf, (40, y))
        y += name_surf.get_height() + 20
        
        # 描述
        y = self._render_text_wrapped(
            surface, 
            self.font_text, 
            mode_data["description"], 
            60, 
            y, 
            self.screen_width - 100, 
            (20, 20, 20)
        )
        y += 15
        
        # 特性列表
        for feature in mode_data["features"]:
            y = self._render_text_wrapped(
                surface, 
                self.font_text, 
                feature, 
                60, 
                y, 
                self.screen_width - 100, 
                (25, 25, 25)
            )
            y += 5
        
        y += 20
        
        # 限时模式：难度参数
        if "difficulties" in mode_data:
            for diff_key, diff_data in mode_data["difficulties"].items():
                diff_name_surf, _ = self.font_section.render(
                    f"{diff_data['name']}难度", 
                    (30, 30, 30)
                )
                surface.blit(diff_name_surf, (60, y))
                diff_rect = self.font_section.get_rect(f"{diff_data['name']}难度")
                y += diff_rect.height + 15
                
                y = self._render_table(surface, diff_data["params"], y, 60)
                y += 20
        
        # 无尽模式：难度曲线
        elif "difficulty_curve" in mode_data:
            # 初始参数
            init_title_surf, _ = self.font_section.render("初始参数", (30, 30, 30))
            surface.blit(init_title_surf, (60, y))
            init_rect = self.font_section.get_rect("初始参数")
            y += init_rect.height + 15
            y = self._render_table(surface, mode_data["initial_params"], y, 60)
            y += 30
            
            # 敌人增强
            enemy_title_surf, _ = self.font_section.render("敌人增强（每20秒）", (30, 30, 30))
            surface.blit(enemy_title_surf, (60, y))
            enemy_rect = self.font_section.get_rect("敌人增强（每20秒）")
            y += enemy_rect.height + 15
            y = self._render_table(
                surface, 
                mode_data["difficulty_curve"]["enemy_enhancement"], 
                y, 
                60
            )
            y += 30
            
            # 玩家增强
            player_title_surf, _ = self.font_section.render("玩家增强", (30, 30, 30))
            surface.blit(player_title_surf, (60, y))
            player_rect = self.font_section.get_rect("玩家增强")
            y += player_rect.height + 15
            y = self._render_table(
                surface, 
                mode_data["difficulty_curve"]["player_enhancement"], 
                y, 
                60
            )
            y += 30
            
            # 背景切换
            bg_title_surf, _ = self.font_section.render("背景切换", (30, 30, 30))
            surface.blit(bg_title_surf, (60, y))
            bg_rect = self.font_section.get_rect("背景切换")
            y += bg_rect.height + 15
            y = self._render_table(
                surface, 
                mode_data["difficulty_curve"]["background_switch"], 
                y, 
                60
            )
        
        return y

