import time
import random
from typing import List, Dict, Any
from core.entities import Enemy


def spawn_waves(
    LEVELS: Dict[str, Any],
    difficulty: str,
    params: Dict[str, Any],
    enemies: List[Enemy],
    start_time: float,
    spawned_flags: List[bool],
    screen_width: int,
) -> None:
    t_elapsed = time.time() - start_time
    waves = LEVELS.get("single", {}).get(difficulty, [])
    for idx, wv in enumerate(waves):
        if not spawned_flags[idx] and t_elapsed >= float(wv.get("t", 0)):
            cnt = int(wv.get("count", 1))
            spd = float(wv.get("speed", params["enemy_speed"]))
            for _ in range(cnt):
                x = random.randint(40, max(40, screen_width - 40))
                e = Enemy(x, -40)
                e.speed = spd
                enemies.append(e)
            spawned_flags[idx] = True


def spawn_trickle(params: Dict[str, Any], enemies: List[Enemy], enemy_cap: int, last_spawn: float, screen_width: int) -> float:
    now = time.time()
    if now - last_spawn > params["spawn_interval"] and len(enemies) < enemy_cap // 2:
        can_spawn = max(0, (enemy_cap // 2) - len(enemies))
        batch = min(params.get("trickle_batch", 1), can_spawn)
        for _ in range(batch):
            x = random.randint(40, max(40, screen_width - 40))
            e = Enemy(x, -40)
            e.speed = params["enemy_speed"]
            enemies.append(e)
        return now
    return last_spawn

