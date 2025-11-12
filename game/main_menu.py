import sys
import os
import pygame
import pygame.freetype as ft
from typing import Optional

if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.engine import Engine
from utils.logger import get_logger
from utils import assets
from utils.config import load_config
from game import settings_store


logger = get_logger("main_menu")


def choose_font(size: int):
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


def _input_room_code(engine: Engine, bg_menu, dim_overlay, font_big, font_small, font_hint) -> Optional[str]:
    """
    房间号输入界面
    返回输入的房间号（6位），如果取消则返回None
    """
    room_code = ""
    cursor_visible = True
    cursor_timer = 0.0
    error_msg = ""
    
    def blit_text_with_shadow(surface, text_surf, pos):
        shadow = text_surf.copy()
        shadow.fill((0,0,0,0), None, pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, (pos[0]+2, pos[1]+2))
        surface.blit(text_surf, pos)
    
    inputting = True
    orig_repeat = pygame.key.get_repeat()
    repeat_enabled = False
    try:
        pygame.key.set_repeat(300, 45)
        repeat_enabled = True
    except Exception:
        repeat_enabled = False
    try:
        while inputting:
            engine.begin_frame()
            dt = engine.clock.get_time() / 1000.0
            cursor_timer += dt
            if cursor_timer >= 0.5:
                cursor_visible = not cursor_visible
                cursor_timer = 0.0
            
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return None
                    elif ev.key == pygame.K_RETURN:
                        # 验证房间号格式（6位字母数字）
                        room_code_clean = room_code.strip().upper()
                        if len(room_code_clean) == 6 and room_code_clean.isalnum():
                            return room_code_clean
                        else:
                            error_msg = "房间号必须是6位字母或数字"
                    elif ev.key == pygame.K_BACKSPACE:
                        room_code = room_code[:-1]
                        error_msg = ""
                    else:
                        # 只接受字母和数字
                        if ev.unicode and ev.unicode.isalnum() and len(room_code) < 6:
                            room_code += ev.unicode.upper()
                            error_msg = ""
            
            # 绘制背景
            if bg_menu is not None:
                engine.screen.blit(bg_menu, (0, 0))
            engine.screen.blit(dim_overlay, (0, 0))
            
            # 标题 - 兼容两种字体类型
            try:
                # pygame.freetype 字体对象
                title, _ = font_big.render("输入房间号", (255, 240, 200))
            except (TypeError, AttributeError):
                # pygame.font.Font 对象
                title = font_big.render("输入房间号", True, (255, 240, 200))
            blit_text_with_shadow(engine.screen, title, (engine.screen.get_width()//2 - title.get_width()//2, 200))
            
            # 输入框背景
            input_box_width = 400
            input_box_height = 60
            input_box_x = engine.screen.get_width()//2 - input_box_width//2
            input_box_y = 300
            input_box = pygame.Rect(input_box_x, input_box_y, input_box_width, input_box_height)
            pygame.draw.rect(engine.screen, (40, 50, 60), input_box, border_radius=8)
            pygame.draw.rect(engine.screen, (100, 150, 200), input_box, width=2, border_radius=8)
            
            # 输入文本
            display_text = room_code
            if cursor_visible:
                display_text += "_"
            try:
                text_surf, _ = font_big.render(display_text, (255, 255, 255))
            except (TypeError, AttributeError):
                text_surf = font_big.render(display_text, True, (255, 255, 255))
            text_x = input_box_x + 20
            text_y = input_box_y + (input_box_height - text_surf.get_height()) // 2
            engine.screen.blit(text_surf, (text_x, text_y))
            
            # 提示信息
            try:
                hint1, _ = font_small.render("请输入6位房间号（字母或数字）", (200, 220, 240))
            except (TypeError, AttributeError):
                hint1 = font_small.render("请输入6位房间号（字母或数字）", True, (200, 220, 240))
            blit_text_with_shadow(engine.screen, hint1, (engine.screen.get_width()//2 - hint1.get_width()//2, input_box_y + input_box_height + 20))
            
            try:
                hint2, _ = font_hint.render("Enter 确认, ESC 取消", (180, 200, 220))
            except (TypeError, AttributeError):
                hint2 = font_hint.render("Enter 确认, ESC 取消", True, (180, 200, 220))
            blit_text_with_shadow(engine.screen, hint2, (engine.screen.get_width()//2 - hint2.get_width()//2, input_box_y + input_box_height + 60))
            
            # 错误信息
            if error_msg:
                try:
                    error_surf, _ = font_small.render(error_msg, (255, 120, 120))
                except (TypeError, AttributeError):
                    error_surf = font_small.render(error_msg, True, (255, 120, 120))
                blit_text_with_shadow(engine.screen, error_surf, (engine.screen.get_width()//2 - error_surf.get_width()//2, input_box_y + input_box_height + 100))
            
            engine.end_frame()
    finally:
        if repeat_enabled:
            try:
                if orig_repeat and orig_repeat[0] > 0 and orig_repeat[1] > 0:
                    pygame.key.set_repeat(orig_repeat[0], orig_repeat[1])
                else:
                    pygame.key.set_repeat()
            except Exception:
                pass

    return None


def _input_server_settings(engine: Engine, bg_menu, dim_overlay, font_big, font_small, font_hint, cfg) -> Optional[tuple[str, int]]:
    """
    输入或修改联机服务器地址与端口。
    留空表示使用默认配置中的值。
    """
    host_default = cfg["network"]["ws_host"]
    port_default = int(cfg["network"]["ws_port"])
    host_override = settings_store.get_setting("net_host", "")
    port_override = settings_store.get_setting("net_port", 0)
    if isinstance(host_override, str):
        host = host_override
    else:
        host = str(host_override or "")
    try:
        port_value = int(port_override)
    except (TypeError, ValueError):
        port_value = 0
    port = str(port_value) if port_value else ""

    cursor_visible = True
    cursor_timer = 0.0
    field_index = 0  # 0 = host, 1 = port
    error_msg = ""
    allowed_host_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_[]:"

    def blit_text_with_shadow(surface, text_surf, pos):
        shadow = text_surf.copy()
        shadow.fill((0, 0, 0, 0), None, pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, (pos[0] + 2, pos[1] + 2))
        surface.blit(text_surf, pos)

    inputting = True
    orig_repeat = pygame.key.get_repeat()
    repeat_enabled = False
    try:
        pygame.key.set_repeat(300, 45)
        repeat_enabled = True
    except Exception:
        repeat_enabled = False
    try:
        while inputting:
            engine.begin_frame()
            dt = engine.clock.get_time() / 1000.0
            cursor_timer += dt
            if cursor_timer >= 0.5:
                cursor_visible = not cursor_visible
                cursor_timer = 0.0

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return None
                    elif ev.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                        field_index = (field_index + 1) % 2
                    elif ev.key == pygame.K_RETURN:
                        host_clean = host.strip()
                        port_clean = port.strip()
                        if port_clean:
                            try:
                                port_int = int(port_clean)
                            except ValueError:
                                error_msg = "端口必须是数字"
                                continue
                            if not (1 <= port_int <= 65535):
                                error_msg = "端口需在1-65535之间"
                                continue
                        else:
                            port_int = 0
                        settings_store.set_setting("net_host", host_clean)
                        settings_store.set_setting("net_port", port_int)
                        return host_clean, port_int
                    elif ev.key == pygame.K_BACKSPACE:
                        if field_index == 0:
                            host = host[:-1]
                        else:
                            port = port[:-1]
                    else:
                        ch = ev.unicode
                        if not ch:
                            continue
                        if field_index == 0:
                            if ch in allowed_host_chars and len(host) < 64:
                                host += ch
                        else:
                            if ch.isdigit() and len(port) < 5:
                                port += ch

            # 绘制背景
            if bg_menu is not None:
                engine.screen.blit(bg_menu, (0, 0))
            engine.screen.blit(dim_overlay, (0, 0))

            # 标题
            try:
                title, _ = font_big.render("联机服务器设置", (255, 240, 200))
            except (TypeError, AttributeError):
                title = font_big.render("联机服务器设置", True, (255, 240, 200))
            blit_text_with_shadow(engine.screen, title, (engine.screen.get_width() // 2 - title.get_width() // 2, 170))

            # 默认提示
            default_text = f"默认：{host_default}:{port_default}"
            try:
                default_surf, _ = font_hint.render(default_text, (200, 210, 220))
            except (TypeError, AttributeError):
                default_surf = font_hint.render(default_text, True, (200, 210, 220))
            blit_text_with_shadow(engine.screen, default_surf, (engine.screen.get_width() // 2 - default_surf.get_width() // 2, 220))

            # 输入框
            input_box_w = 520
            input_box_h = 56
            start_y = 270
            box_host = pygame.Rect(engine.screen.get_width() // 2 - input_box_w // 2, start_y, input_box_w, input_box_h)
            box_port = pygame.Rect(engine.screen.get_width() // 2 - input_box_w // 2, start_y + 90, input_box_w, input_box_h)

            def draw_box(rect, active):
                color_border = (120, 180, 240) if active else (90, 120, 160)
                pygame.draw.rect(engine.screen, (40, 50, 60), rect, border_radius=8)
                pygame.draw.rect(engine.screen, color_border, rect, width=2, border_radius=8)

            draw_box(box_host, field_index == 0)
            draw_box(box_port, field_index == 1)

            # 标签
            labels = [
                ("服务器地址（留空 = 默认）", box_host.y - 32),
                ("端口（留空 = 默认）", box_port.y - 32),
            ]
            for text, pos_y in labels:
                try:
                    surf, _ = font_small.render(text, (210, 220, 235))
                except (TypeError, AttributeError):
                    surf = font_small.render(text, True, (210, 220, 235))
                blit_text_with_shadow(engine.screen, surf, (box_host.x, pos_y))

            # 文本输入显示
            host_display = host + ("_" if field_index == 0 and cursor_visible else "")
            if not host_display and field_index != 0:
                host_display = ""
            port_display = port + ("_" if field_index == 1 and cursor_visible else "")

            try:
                host_surf, _ = font_big.render(host_display or "", (255, 255, 255))
            except (TypeError, AttributeError):
                host_surf = font_big.render(host_display or "", True, (255, 255, 255))
            try:
                port_surf, _ = font_big.render(port_display or "", (255, 255, 255))
            except (TypeError, AttributeError):
                port_surf = font_big.render(port_display or "", True, (255, 255, 255))

            engine.screen.blit(host_surf, (box_host.x + 16, box_host.y + (box_host.height - host_surf.get_height()) // 2))
            engine.screen.blit(port_surf, (box_port.x + 16, box_port.y + (box_port.height - port_surf.get_height()) // 2))

            # 按键提示
            hint_text = "Enter 保存，ESC 取消，Tab/↑↓ 切换"
            try:
                hint_surf, _ = font_hint.render(hint_text, (200, 210, 220))
            except (TypeError, AttributeError):
                hint_surf = font_hint.render(hint_text, True, (200, 210, 220))
            blit_text_with_shadow(engine.screen, hint_surf, (engine.screen.get_width() // 2 - hint_surf.get_width() // 2, box_port.y + box_port.height + 40))

            # 错误提示
            if error_msg:
                try:
                    err_surf, _ = font_small.render(error_msg, (255, 120, 120))
                except (TypeError, AttributeError):
                    err_surf = font_small.render(error_msg, True, (255, 120, 120))
                blit_text_with_shadow(engine.screen, err_surf, (engine.screen.get_width() // 2 - err_surf.get_width() // 2, box_port.y + box_port.height + 70))

            engine.end_frame()
    finally:
        if repeat_enabled:
            try:
                if orig_repeat and orig_repeat[0] > 0 and orig_repeat[1] > 0:
                    pygame.key.set_repeat(orig_repeat[0], orig_repeat[1])
                else:
                    pygame.key.set_repeat()
            except Exception:
                pass

    return None


def run() -> None:
    engine = Engine()
    font_title = choose_font(56)  # 更大的标题字体
    font_big = choose_font(40)
    font_small = choose_font(24)  # 稍大的菜单字体
    font_hint = choose_font(18)  # 提示文字字体

    cfg = load_config()
    muted_flag = bool(settings_store.get_setting("muted", False))
    assets.set_audio_config(muted=muted_flag)

    # 背景图（自适应窗口尺寸）
    bg_size = (engine.screen.get_width(), engine.screen.get_height())
    bg_menu = assets.load_image("backgrounds/backgroundmenu.jpg", size=bg_size)
    # 半透明遮罩，增强文字对比度
    dim_overlay = pygame.Surface(bg_size, pygame.SRCALPHA)
    dim_overlay.fill((0, 0, 0, 70))  # 0~255，数值越大越暗

    def blit_text_with_shadow(surface: pygame.Surface, text_surf: pygame.Surface, pos: tuple[int, int]) -> None:
        # 阴影先绘制（略偏移 + 深色）
        shadow = text_surf.copy()
        shadow.fill((0, 0, 0, 0), None, pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, (pos[0] + 2, pos[1] + 2))
        surface.blit(text_surf, pos)

    items = ["单人模式", "多人联机", "设置", "退出"]
    selected = 0
    # sounds (optional)
    move_sfx = assets.load_sound("ui/menu_move.wav", 0.5)
    select_sfx = assets.load_sound("bgm/click.ogg", 0.6)
    assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)

    running = True
    while running:
        engine.begin_frame()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(items)
                    assets.play_sound("ui/menu_move.wav", 0.5)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(items)
                    assets.play_sound("ui/menu_move.wav", 0.5)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    selected_item = items[selected]
                    assets.play_sound("bgm/click.ogg", 0.6)
                    if selected_item == "单人模式":
                        # 子菜单：选择限时/无尽/介绍
                        sub_items = ["限时模式（可选难度）", "无尽模式（逐步增强）", "模式介绍", "返回"]
                        sub_sel = 0
                        choosing = True
                        while choosing:
                            engine.begin_frame()
                            for ev in pygame.event.get():
                                if ev.type == pygame.QUIT:
                                    choosing = False
                                    running = False
                                elif ev.type == pygame.KEYDOWN:
                                    if ev.key in (pygame.K_ESCAPE,):
                                        choosing = False
                                    elif ev.key in (pygame.K_UP, pygame.K_w):
                                        sub_sel = (sub_sel - 1) % len(sub_items)
                                        assets.play_sound("ui/menu_move.wav", 0.5)
                                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                                        sub_sel = (sub_sel + 1) % len(sub_items)
                                        assets.play_sound("ui/menu_move.wav", 0.5)
                                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                                        assets.play_sound("bgm/click.ogg", 0.6)
                                        if sub_items[sub_sel].startswith("限时模式"):
                                            from game.single_player import run as run_sp
                                            run_sp(as_child=True, game_mode="timed")
                                            # 返回后恢复菜单BGM
                                            assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                                        elif sub_items[sub_sel].startswith("无尽模式"):
                                            from game.single_player import run as run_sp
                                            run_sp(as_child=True, game_mode="endless")
                                            # 返回后恢复菜单BGM
                                            assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                                        elif sub_items[sub_sel] == "模式介绍":
                                            from game.mode_intro import ModeIntro
                                            intro = ModeIntro(engine.screen.get_width(), engine.screen.get_height())
                                            # 启用按键重复，支持长按滚动
                                            pygame.key.set_repeat(300, 40)
                                            showing_intro = True
                                            try:
                                                while showing_intro:
                                                    engine.begin_frame()
                                                    for intro_ev in pygame.event.get():
                                                        if intro_ev.type == pygame.QUIT:
                                                            showing_intro = False
                                                            choosing = False
                                                            running = False
                                                        elif intro_ev.type == pygame.KEYDOWN:
                                                            action = intro.handle_key(intro_ev.key)
                                                            if action == "back":
                                                                showing_intro = False
                                                        elif intro_ev.type == pygame.MOUSEWHEEL:
                                                            intro.handle_mouse_wheel(intro_ev.y)
                                                    # 绘制介绍界面
                                                    if bg_menu is not None:
                                                        engine.screen.blit(bg_menu, (0, 0))
                                                    intro.render(engine.screen, dim_overlay)
                                                    engine.end_frame()
                                            finally:
                                                # 恢复按键重复设置（禁用）
                                                pygame.key.set_repeat()
                                        else:
                                            choosing = False
                            # 绘制子菜单
                            if bg_menu is not None:
                                engine.screen.blit(bg_menu, (0, 0))
                            engine.screen.blit(dim_overlay, (0, 0))
                            sub_title, _ = font_big.render("选择单人模式", (255, 240, 200))
                            def blit_text_with_shadow(surface, text_surf, pos):
                                shadow = text_surf.copy()
                                shadow.fill((0,0,0,0), None, pygame.BLEND_RGBA_MULT)
                                surface.blit(shadow, (pos[0]+2, pos[1]+2))
                                surface.blit(text_surf, pos)
                            blit_text_with_shadow(engine.screen, sub_title, (engine.screen.get_width()//2 - sub_title.get_width()//2, 140))
                            base_y2 = 230
                            for i, t in enumerate(sub_items):
                                c = (255, 255, 200) if i == sub_sel else (225, 235, 245)
                                surf, _ = font_small.render(("> " if i == sub_sel else "  ") + t, c)
                                blit_text_with_shadow(engine.screen, surf, (engine.screen.get_width()//2 - 220, base_y2 + i * 40))
                            hint2, _ = font_small.render("↑↓ 选择, Enter 确认, ESC 返回", (230,230,230))
                            blit_text_with_shadow(engine.screen, hint2, (engine.screen.get_width()//2 - hint2.get_width()//2, base_y2 + 200))
                            engine.end_frame()
                    elif selected_item == "多人联机":
                        # 子菜单：创建房间或加入房间
                        sub_items = ["创建房间", "加入房间", "服务器设置", "返回"]
                        sub_sel = 0
                        choosing = True
                        while choosing:
                            engine.begin_frame()
                            for ev in pygame.event.get():
                                if ev.type == pygame.QUIT:
                                    choosing = False
                                    running = False
                                elif ev.type == pygame.KEYDOWN:
                                    if ev.key in (pygame.K_ESCAPE,):
                                        choosing = False
                                    elif ev.key in (pygame.K_UP, pygame.K_w):
                                        sub_sel = (sub_sel - 1) % len(sub_items)
                                        assets.play_sound("ui/menu_move.wav", 0.5)
                                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                                        sub_sel = (sub_sel + 1) % len(sub_items)
                                        assets.play_sound("ui/menu_move.wav", 0.5)
                                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                                        assets.play_sound("bgm/click.ogg", 0.6)
                                        if sub_items[sub_sel] == "创建房间":
                                            # 创建新房间
                                            from game.online_coop import run as run_online
                                            run_online(as_child=True, engine=engine, create_new=True)
                                            assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                                        elif sub_items[sub_sel] == "加入房间":
                                            # 输入房间号界面
                                            invite_code = _input_room_code(engine, bg_menu, dim_overlay, font_big, font_small, font_hint)
                                            if invite_code:
                                                from game.online_coop import run as run_online
                                                run_online(as_child=True, engine=engine, invite_code=invite_code, create_new=False)
                                                assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                                        elif sub_items[sub_sel] == "服务器设置":
                                            _input_server_settings(engine, bg_menu, dim_overlay, font_big, font_small, font_hint, cfg)
                                            assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                                        else:
                                            choosing = False
                            # 绘制子菜单
                            if bg_menu is not None:
                                engine.screen.blit(bg_menu, (0, 0))
                            engine.screen.blit(dim_overlay, (0, 0))
                            title2, _ = font_big.render("多人联机", (255, 240, 200))
                            def blit_text_with_shadow(surface, text_surf, pos):
                                shadow = text_surf.copy()
                                shadow.fill((0,0,0,0), None, pygame.BLEND_RGBA_MULT)
                                surface.blit(shadow, (pos[0]+2, pos[1]+2))
                                surface.blit(text_surf, pos)
                            blit_text_with_shadow(engine.screen, title2, (engine.screen.get_width()//2 - title2.get_width()//2, 140))
                            base_y2 = 230
                            host_override = settings_store.get_setting("net_host", "") or cfg["network"]["ws_host"]
                            port_override = settings_store.get_setting("net_port", 0)
                            try:
                                port_override_int = int(port_override)
                            except (TypeError, ValueError):
                                port_override_int = 0
                            port_display = port_override_int if port_override_int else cfg["network"]["ws_port"]
                            for i, t in enumerate(sub_items):
                                display_label = t
                                if t == "服务器设置":
                                    display_label = f"{t} （当前 {host_override}:{port_display}）"
                                c = (255, 255, 200) if i == sub_sel else (225, 235, 245)
                                surf, _ = font_small.render(("> " if i == sub_sel else "  ") + display_label, c)
                                blit_text_with_shadow(engine.screen, surf, (engine.screen.get_width()//2 - 220, base_y2 + i * 40))
                            hint_text = "↑↓ 选择, Enter 确认, ESC 返回"
                            hint_surf, _ = font_hint.render(hint_text, (230, 230, 230))
                            blit_text_with_shadow(engine.screen, hint_surf, (engine.screen.get_width()//2 - hint_surf.get_width()//2, base_y2 + len(sub_items) * 40 + 20))
                            engine.end_frame()
                    elif selected_item == "设置":
                        from game.settings import run as run_settings
                        run_settings(as_child=True)
                        # 返回后恢复菜单BGM
                        assets.play_bgm("bgm/menu.ogg", 0.35, loop=True)
                    elif selected_item == "退出":
                        running = False
            #（多人联机子菜单已移动到 Enter 分支内部）
        if not running:
            engine.end_frame()
            break

        # 绘制背景
        if bg_menu is not None:
            engine.screen.blit(bg_menu, (0, 0))
        # 覆盖一层暗色，以增强可读性
        engine.screen.blit(dim_overlay, (0, 0))

        # 绘制标题 - 飞机大战
        title_text = "飞机大战"
        title_surf, _ = font_title.render(title_text, (255, 240, 200))
        title_x = engine.screen.get_width() // 2 - title_surf.get_width() // 2
        title_y = 100
        blit_text_with_shadow(engine.screen, title_surf, (title_x, title_y))
        
        # 绘制副标题装饰线
        line_width = title_surf.get_width() + 60
        line_x = engine.screen.get_width() // 2 - line_width // 2
        line_y = title_y + title_surf.get_height() + 10
        pygame.draw.line(engine.screen, (200, 220, 240), (line_x, line_y), (line_x + line_width, line_y), 2)

        # 绘制菜单项 - 左对齐，更美观的布局
        menu_start_x = engine.screen.get_width() // 2 - 200
        base_y = title_y + title_surf.get_height() + 60
        
        for i, text in enumerate(items):
            sel = (i == selected)
            # 选中项使用更亮的颜色和箭头
            if sel:
                color = (255, 255, 150)
                prefix = "> "
                # 选中项背景高亮
                highlight_rect = pygame.Rect(menu_start_x - 20, base_y + i * 50 - 5, 400, 40)
                highlight_surf = pygame.Surface((400, 40), pygame.SRCALPHA)
                highlight_surf.fill((255, 255, 200, 30))
                engine.screen.blit(highlight_surf, highlight_rect)
            else:
                color = (200, 220, 240)
                prefix = "  "
            
            surf, _ = font_small.render(prefix + text, color)
            blit_text_with_shadow(engine.screen, surf, (menu_start_x, base_y + i * 50))

        # 绘制提示信息
        hint_text = "↑↓ 选择  |  Enter 确认  |  ESC 退出"
        hint, _ = font_hint.render(hint_text, (180, 200, 220))
        hint_y = base_y + len(items) * 50 + 40
        blit_text_with_shadow(engine.screen, hint, (engine.screen.get_width() // 2 - hint.get_width() // 2, hint_y))

        engine.end_frame()

    engine.quit()
    pygame.quit()


if __name__ == "__main__":
    run()

