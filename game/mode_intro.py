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
            "description": "在限定时间内尽可能获得高分，时间结束后进行统一结算。关卡会在固定时间轴上刷新敌机波次，所有机型与贴图均与无尽模式保持一致（除 Boss 外），适合短时间冲分或测试武器表现。",
            "features": [
                "• 固定 180 秒作战时间，倒计时归零后立即结算当局得分与评价。",
                "• 敌机会以随机机型出现（小型 / 中型 / 重型），并从机库中抽取贴图，保证视觉多样性。",
                "• 不生成 Boss，专注于常规敌机与刷分节奏（Boss 只在无尽模式出现）。",
                "• 支持简单 / 普通 / 困难三种难度；开局参数、敌机速度、掉落率均随难度调整。",
                "• 支持本地双人合作：两名玩家共享倒计时，但各自保留独立进化与复活次数。",
                "• 结算界面会记录最高分与击毁数，可用于撰写性能分析或教学案例。",
                "• 适合想要快速体验、对比不同配置或进行计分练习的玩家。",
            ],
            "extra_sections": [
                {
                    "title": "推荐流程",
                    "lines": [
                        "• 开局 30 秒内优先确保生存：主目标是收集 3 枚进化币并保持满血，为后续波次奠定火力。",
                        "• 中段（120~60 秒）集中清理中型 / 重型敌机，多利用散射、穿透等道具快速刷分。",
                        "• 最后 45 秒建议适度冒险：连击倍率会显著影响最终得分，可保留清屏道具在关键时刻使用。"
                    ],
                },
                {
                    "title": "计分与奖励",
                    "lines": [
                        "• 击毁敌机基础分 × 难度系数 × 连击倍率；多人模式下会额外乘以生存玩家收益系数。",
                        "• 掉落的“x2”道具可以在 12 秒内翻倍所有得分，对冲刺阶段尤为关键。",
                        "• 结算页面会显示击毁数、道具拾取率、受伤次数，可直接引用到论文或报告中。"
                    ],
                },
                {
                    "title": "高分技巧",
                    "lines": [
                        "• 合理控制清屏道具：在敌机刷新密集区使用，可快速拉高连击数量。",
                        "• 站位尽量保持在屏幕中央上方，既能提前击落敌机，又能缩短拾取进化币的距离。",
                        "• 若与队友联机，可约定分区清理，避免双方火力重叠导致道具浪费。"
                    ],
                },
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
            "description": "没有时间限制，敌人会随时间逐步增强，真正考验生存与资源调度能力。所有机型与贴图均为随机，Boss 仅在本模式出现，服务器统一广播背景与事件，适合分析长时战斗与网络同步策略。",
            "features": [
                "• 无时间限制，可以持续挑战，战斗数据可直接用于性能与网络实验。",
                "• 每 20 秒进入一个新步进，敌机会获得速度、血量、射击间隔等多项强化。",
                "• 玩家强化节奏较慢，需要依赖道具与进化币补齐输出，强调战场资源调度。",
                "• Boss 仅在本模式出现，服务器分配唯一事件 ID，确保音效与判定跨客户端一致。",
                "• 背景随机切换采用淡入淡出，避免闪屏；贴图变换只在初次生成时决定，保证一致性。",
                "• 支持多人合作，任一玩家掉线会立即剔除其机体并刷新玩家数，剩余玩家继续等待补位。",
            ],
            "extra_sections": [
                {
                    "title": "进化与道具策略",
                    "lines": [
                        "• 每累计 3 枚进化币即可提升一次进化等级，共 5 阶；进化不仅增大机体，还会提升火力与散射角度。",
                        "• 掉落表会随步进自动调整，后期更容易产出护盾、散射、清屏等保命道具；拾取时机直接影响生存链。",
                        "• 建议保持护盾充能并优先拾取穿透 / 散射，处理高血量敌机时效率更高。"
                    ],
                },
                {
                    "title": "Boss 机制",
                    "lines": [
                        "• Boss 血量会随当前步进按 1.25^step 递增，且拥有独立 AI 控制，支持追踪与范围攻击。",
                        "• 服务器在生成 Boss 时会刷新 `boss_spawn_event_id`，客户端据此播放一次性音效并渲染专属贴图。",
                        "• 击败 Boss 后会额外掉落进化币与高阶道具，是后期维持战力的重要来源。"
                    ],
                },
                {
                    "title": "多人协力建议",
                    "lines": [
                        "• 双人协作时建议一名玩家偏上路清理刷新口，另一名玩家游走回收道具，维持火力覆盖。",
                        "• 若有队友退出，服务器会立即更新玩家列表并重置倒计时，剩余玩家可继续等待新伙伴加入。",
                        "• 暂停（ESC/P）在客户端本地冻结输入，并发送零输入帧给服务器，确保恢复后不发生位移跳变。"
                    ],
                },
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
        if mode_data.get("extra_sections"):
            for section in mode_data["extra_sections"]:
                lines = section.get("lines", []) if isinstance(section, dict) else []
                height += 40  # 标题 + 间距
                height += max(1, len(lines)) * 28
        
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

        # 附加小节（可选）
        extra_sections = mode_data.get("extra_sections") or []
        for section in extra_sections:
            title = section.get("title", "")
            lines = section.get("lines", [])
            if not title and not lines:
                continue
            y = self._render_section(surface, title or "补充说明", lines, y, 60)
            y += 10
        
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

