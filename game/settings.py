import sys
import os
import pygame

if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.engine import Engine
from utils.logger import get_logger
from utils import assets
from . import settings_store
from data.dao import dao
import json
from utils.config import load_config


logger = get_logger("settings")


def choose_font(size: int):
    if not pygame.get_init():
        pygame.init()
    pygame.font.init()
    return pygame.font.SysFont("Microsoft YaHei", size) or pygame.font.SysFont(None, size)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def run(as_child: bool = True) -> None:
    engine = Engine()
    font_big = choose_font(32)
    font = choose_font(20)
    font_header = choose_font(24)
    font_note = choose_font(16)
    # 长按加速（首次延迟300ms，每40ms步进一次）
    try:
        pygame.key.set_repeat(300, 40)
    except Exception:
        pass

    cfg = {
        "spawn_interval": 2.2,
        "enemy_cap": 34,
        "fire_interval": 2.2,
        "burst_max": 1,
    }
    cfg.update(settings_store.get_overrides())
    st = settings_store.get_all_settings()

    drop_rate_defaults = {"easy": 0.35, "normal": 0.30, "hard": 0.27, "custom": 0.30}
    drop_rate = drop_rate_defaults.copy()
    stored_rate = st.get("drop_rate") or {}
    for k, v in stored_rate.items():
        try:
            drop_rate[k] = float(v)
        except Exception:
            continue
    weight_defaults = [("heal", 32), ("x2", 26), ("spread", 24), ("haste", 26), ("power", 26), ("piercing", 22), ("shield", 16), ("clearscreen", 8)]
    weight_order = [name for name, _ in weight_defaults]
    stored_table = st.get("drop_table") or {}
    base_weights = stored_table.get("custom", weight_defaults)
    weight_map = {name: int(weight) for name, weight in base_weights}
    for name, default in weight_defaults:
        weight_map.setdefault(name, default)

    groups = [
        ("基础与显示设置", [
            {"name": "显示碰撞盒", "key": "show_hitbox", "type": "bool", "note": "仅自定义模式生效，用于调试碰撞体积", "only_custom": True},
            {"name": "全屏", "key": "fullscreen", "type": "bool", "note": "保存后重新进入主菜单生效"},
        ]),
        ("音频设置", [
            {"name": "静音", "key": "muted", "type": "bool", "note": "即时生效，可随时切换"},
        ]),
        ("操作与控制设置", [
            {"name": "键位方案(WASD/方向键)", "key": "key_scheme", "type": "enum", "note": "影响玩家移动按键"},
        ]),
        ("战斗与玩法设置(自定义测试用)", [
            {"name": "生成间隔(s)", "key": "spawn_interval", "type": "float", "lo": 0.5, "hi": 5.0, "step": 0.1, "only_custom": True, "note": "自定义模式下敌机刷新的基础间隔"},
            {"name": "敌机上限", "key": "enemy_cap", "type": "int", "lo": 10, "hi": 80, "step": 2, "only_custom": True},
            {"name": "敌机射击冷却(s)", "key": "fire_interval", "type": "float", "lo": 0.5, "hi": 5.0, "step": 0.1, "only_custom": True},
            {"name": "敌机连发次数", "key": "burst_max", "type": "int", "lo": 0, "hi": 5, "step": 1, "only_custom": True},
            {"name": "掉落-全局概率(normal)", "key": "drop_rate", "type": "drop_rate", "lo": 0.0, "hi": 1.0, "step": 0.01, "only_custom": True, "note": "仅自定义模式生效，会自动推导各难度"},
            {"name": "掉落权重-heal", "key": "w_heal", "type": "drop_weight", "code": "heal", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-x2", "key": "w_x2", "type": "drop_weight", "code": "x2", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-spread", "key": "w_spread", "type": "drop_weight", "code": "spread", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-haste", "key": "w_haste", "type": "drop_weight", "code": "haste", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-power", "key": "w_power", "type": "drop_weight", "code": "power", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-piercing", "key": "w_piercing", "type": "drop_weight", "code": "piercing", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-shield", "key": "w_shield", "type": "drop_weight", "code": "shield", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
            {"name": "掉落权重-clearscreen", "key": "w_clearscreen", "type": "drop_weight", "code": "clearscreen", "lo": 0, "hi": 80, "step": 1, "only_custom": True},
        ]),
        ("系统操作", [
            {"name": "清空本地历史记录", "key": "clear_history", "type": "action"},
            {"name": "保存并返回", "key": "save", "type": "action"},
        ]),
    ]

    rows = []
    selectable_indices = []
    for group_title, items in groups:
        rows.append({"kind": "header", "title": group_title})
        for item in items:
            row = {"kind": "item"}
            row.update(item)
            rows.append(row)
            selectable_indices.append(len(rows) - 1)

    idx = 0
    scroll_offset = 0.0

    running = True
    while running:
        engine.begin_frame()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEWHEEL:
                scroll_offset -= event.y * 60
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    if selectable_indices:
                        idx = (idx - 1) % len(selectable_indices)
                        assets.play_sound("ui/menu_move.wav", 0.5)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    if selectable_indices:
                        idx = (idx + 1) % len(selectable_indices)
                        assets.play_sound("ui/menu_move.wav", 0.5)
                elif event.key == pygame.K_PAGEUP:
                    scroll_offset -= engine.screen.get_height() // 2
                elif event.key == pygame.K_PAGEDOWN:
                    scroll_offset += engine.screen.get_height() // 2
                elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                    if not selectable_indices:
                        continue
                    row = rows[selectable_indices[idx]]
                    if row.get("type") == "action":
                        continue
                    right = event.key in (pygame.K_RIGHT, pygame.K_d)
                    key = row["key"]
                    r_type = row["type"]
                    if r_type == "enum":
                        if key == "key_scheme":
                            cur = settings_store.get_setting("key_scheme", "wasd")
                            settings_store.set_setting("key_scheme", "arrows" if cur == "wasd" else "wasd")
                    elif r_type == "bool":
                        cur = settings_store.get_setting(key, False)
                        new_val = not cur
                        settings_store.set_setting(key, new_val)
                        if key == "muted":
                            assets.set_audio_config(muted=new_val)
                    elif r_type in ("float", "int"):
                        delta = row["step"] if right else -row["step"]
                        if r_type == "float":
                            cfg[key] = clamp(round(cfg[key] + delta, 2), row["lo"], row["hi"])
                        else:
                            cfg[key] = int(clamp(cfg[key] + delta, row["lo"], row["hi"]))
                    elif r_type == "drop_rate":
                        delta = row["step"] if right else -row["step"]
                        val = clamp(round(drop_rate.get("normal", 0.30) + delta, 2), row["lo"], row["hi"])
                        drop_rate["normal"] = val
                        drop_rate["easy"] = clamp(val + 0.05, 0.0, 1.0)
                        drop_rate["hard"] = clamp(val - 0.03, 0.0, 1.0)
                        drop_rate["custom"] = val
                        settings_store.set_setting("drop_rate", drop_rate)
                    elif r_type == "drop_weight":
                        delta = row["step"] if right else -row["step"]
                        code = row["code"]
                        val = clamp(weight_map.get(code, 0) + delta, row["lo"], row["hi"])
                        weight_map[code] = int(val)
                        drop_table_store = {diff: [[name, weight_map[name]] for name in weight_order] for diff in ("easy", "normal", "hard", "custom")}
                        settings_store.set_setting("drop_table", drop_table_store)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if not selectable_indices:
                        continue
                    row = rows[selectable_indices[idx]]
                    if row.get("type") != "action":
                        continue
                    if row["key"] == "save":
                        settings_store.set_overrides(cfg)
                        assets.play_sound("bgm/click.ogg", 0.6)
                        try:
                            conf = load_config()
                            conf.setdefault("window", {})
                            conf["window"]["fullscreen"] = bool(settings_store.get_setting("fullscreen", False))
                            os.makedirs("data/configs", exist_ok=True)
                            with open("data/configs/config.json", "w", encoding="utf-8") as f:
                                json.dump(conf, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        running = False
                    elif row["key"] == "clear_history":
                        try:
                            import asyncio
                            asyncio.run(dao.clear_records())
                            assets.play_sound("bgm/click.ogg", 0.6)
                        except RuntimeError:
                            pass

        title = font_big.render("设置 - 难度自定义", True, (180, 230, 255))
        engine.screen.blit(title, (engine.screen.get_width() // 2 - title.get_width() // 2, 120))

        base_y = 190
        visible_h = engine.screen.get_height() - (base_y + 140)
        row_positions = []
        y_cursor = 0
        for row in rows:
            if row["kind"] == "header":
                height = 34
            else:
                height = 38
                if row.get("note"):
                    height += 20
            row_positions.append((y_cursor, height))
            y_cursor += height
        total_h = y_cursor
        max_scroll = max(0, total_h - visible_h)
        if scroll_offset < 0:
            scroll_offset = 0
        if scroll_offset > max_scroll:
            scroll_offset = max_scroll
        if selectable_indices:
            sel_row_idx = selectable_indices[idx]
            sel_top, sel_height = row_positions[sel_row_idx]
            if sel_top - scroll_offset < 0:
                scroll_offset = max(0, sel_top)
            elif sel_top + sel_height - scroll_offset > visible_h:
                scroll_offset = min(max_scroll, sel_top + sel_height - visible_h)

        selected_row_idx = selectable_indices[idx] if selectable_indices else -1
        for i, row in enumerate(rows):
            top, height = row_positions[i]
            y = base_y + top - scroll_offset
            if y + height < base_y - 10 or y > base_y + visible_h + 10:
                continue
            if row["kind"] == "header":
                surf = font_header.render(row["title"], True, (180, 220, 255))
                engine.screen.blit(surf, (engine.screen.get_width() // 2 - 220, y))
                pygame.draw.line(engine.screen, (80, 90, 110), (engine.screen.get_width() // 2 - 220, y + height - 8), (engine.screen.get_width() // 2 + 220, y + height - 8), 1)
            else:
                is_selected = (i == selected_row_idx)
                color = (255, 255, 180) if is_selected else (210, 220, 230)
                key = row["key"]
                r_type = row["type"]
                if r_type == "action":
                    text = f"[ {row['name']} ]"
                elif r_type == "bool":
                    value = "开" if settings_store.get_setting(key, False) else "关"
                    text = f"{row['name']}: {value}"
                elif r_type == "enum":
                    if key == "key_scheme":
                        value = settings_store.get_setting("key_scheme", "wasd").upper()
                    else:
                        value = str(settings_store.get_setting(key))
                    text = f"{row['name']}: {value}"
                elif r_type == "float":
                    text = f"{row['name']}: {cfg[key]:.2f}"
                elif r_type == "int":
                    text = f"{row['name']}: {cfg[key]}"
                elif r_type == "drop_rate":
                    text = f"{row['name']}: {drop_rate.get('normal', 0.30):.2f}"
                elif r_type == "drop_weight":
                    value = weight_map.get(row["code"], 0)
                    text = f"{row['name']}: {value}"
                else:
                    text = row['name']
                surf = font.render(text, True, color)
                engine.screen.blit(surf, (engine.screen.get_width() // 2 - 220, y))
                if row.get("note"):
                    note = row["note"]
                    note_surf = font_note.render(note, True, (150, 160, 185))
                    engine.screen.blit(note_surf, (engine.screen.get_width() // 2 - 200, y + 26))

        if max_scroll > 0:
            sb_x = engine.screen.get_width() - 28
            sb_y = base_y
            sb_w = 6
            sb_h = max(30, int(visible_h * (visible_h / (total_h + 1e-6))))
            sb_pos = int((visible_h - sb_h) * (scroll_offset / max_scroll)) if max_scroll else 0
            pygame.draw.rect(engine.screen, (80, 90, 110), pygame.Rect(sb_x, sb_y, sb_w, visible_h), 1)
            pygame.draw.rect(engine.screen, (140, 160, 200), pygame.Rect(sb_x + 1, sb_y + sb_pos, sb_w - 2, sb_h))

        hint = font.render("↑↓/滚轮 选择  ←→ 调整  PgUp/PgDn 翻页  Enter 执行  ESC 返回", True, (200, 200, 200))
        engine.screen.blit(hint, (engine.screen.get_width() // 2 - hint.get_width() // 2, engine.screen.get_height() - 60))

        engine.end_frame()

    if not as_child:
        engine.quit()
        pygame.quit()
    # 退出前关闭键盘连发
    try:
        pygame.key.set_repeat()
    except Exception:
        pass

