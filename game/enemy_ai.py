import time
import random
import math
import pygame
from typing import List
from core.entities import Enemy


def update_enemy_ai(enemies: List[Enemy], dt: float, screen_width: int) -> None:
    now_t = time.time()
    for e in enemies:
        if not hasattr(e, "_ai"):
            e._ai = {
                "next_switch": now_t + random.uniform(1.2, 2.6),
                "mode": "drift",
                "vx": random.uniform(-90, 90),  # px/s
                "phase": random.uniform(0, math.pi * 2),
                "zig_dir": random.choice([-1, 1]),
            }
        ai = e._ai
        if now_t >= ai["next_switch"]:
            ai["next_switch"] = now_t + random.uniform(1.2, 2.6)
            ai["mode"] = random.choices(["drift", "zigzag", "dash"], weights=[0.5, 0.35, 0.15])[0]
            ai["vx"] = random.uniform(-90, 90)
            ai["phase"] = random.uniform(0, math.pi * 2)
            ai["zig_dir"] = random.choice([-1, 1])

        dx = 0.0
        if ai["mode"] == "drift":
            ai["phase"] += dt * 2.0
            dx = ai["vx"] * dt + 8.0 * math.sin(ai["phase"])
        elif ai["mode"] == "zigzag":
            ai["phase"] += dt * 3.2
            dx = 60.0 * math.sin(ai["phase"]) * ai["zig_dir"] * dt * 3.0
        else:  # dash
            dx = (ai["vx"] * 1.6) * dt

        e.rect.x += int(dx)
        if e.rect.left < 0:
            e.rect.left = 0
        if e.rect.right > screen_width:
            e.rect.right = screen_width
        e.update(dt)

