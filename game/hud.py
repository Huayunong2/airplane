import time
import pygame
from typing import List
from game.props_system import active_buff_labels, wrap_items, buff_active


def render_hud(screen: pygame.Surface, font_small: pygame.font.Font, lines_top: List[str], buffs: dict, enemies_count: int, enemy_bullets_count: int, drops_count: int) -> None:
    y = 8
    for i, line in enumerate(lines_top):
        surf = font_small.render(line, True, (230, 230, 230) if i == 0 else (220, 220, 220))
        screen.blit(surf, (12, y))
        y += 24 if i == 0 else 20
    labels = active_buff_labels(buffs)
    if labels:
        for idx, txt in enumerate(wrap_items(labels, per_line=4)):
            prefix = "持续效果: " if idx == 0 else "           "
            buff_surf = font_small.render(prefix + txt, True, (220, 220, 220))
            screen.blit(buff_surf, (12, y))
            y += 20
    else:
        buff_surf = font_small.render("持续效果: 无", True, (180, 180, 180))
        screen.blit(buff_surf, (12, y))
        y += 20
    stats_txt = f"统计: 敌机 {enemies_count}  敌弹 {enemy_bullets_count}  掉落 {drops_count}"
    stats_surf = font_small.render(stats_txt, True, (205, 205, 205))
    screen.blit(stats_surf, (12, y))

