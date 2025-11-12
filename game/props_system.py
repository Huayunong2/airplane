import time
import random
import pygame
from typing import Dict, List, Tuple, Optional


Color = Tuple[int, int, int]


PROP_SPECS: Dict[str, Dict] = {
    "heal": {"type": "instant", "color": (120, 255, 140)},
    "x2": {"type": "buff", "duration": 8.0, "color": (255, 215, 120)},
    "shield": {"type": "buff", "duration": 8.0, "color": (140, 210, 255)},
    "piercing": {"type": "buff", "duration": 8.0, "color": (255, 150, 150), "pierce": 2},
    "spread": {"type": "buff", "duration": 8.0, "color": (250, 130, 255)},
    "haste": {"type": "buff", "duration": 8.0, "color": (170, 240, 255)},
    "power": {"type": "buff", "duration": 8.0, "color": (255, 110, 90)},
    "clearscreen": {"type": "instant", "color": (255, 240, 160)},
}

DROP_TABLE_DEFAULT = {
    "easy": [("heal", 40), ("x2", 28), ("haste", 24), ("power", 24), ("spread", 22), ("piercing", 20), ("shield", 15), ("clearscreen", 6)],
    "normal": [("heal", 32), ("x2", 26), ("haste", 26), ("power", 26), ("spread", 24), ("piercing", 22), ("shield", 16), ("clearscreen", 8)],
    "hard": [("heal", 26), ("x2", 24), ("haste", 24), ("power", 24), ("spread", 22), ("piercing", 22), ("shield", 18), ("clearscreen", 10)],
    "custom": [("heal", 32), ("x2", 26), ("haste", 26), ("power", 26), ("spread", 24), ("piercing", 22), ("shield", 16), ("clearscreen", 8)],
}
DROP_TABLE = {k: v[:] for k, v in DROP_TABLE_DEFAULT.items()}
DROP_RATE_DEFAULT = {"easy": 0.35, "normal": 0.30, "hard": 0.27, "custom": 0.30}
DROP_RATE = DROP_RATE_DEFAULT.copy()

def set_drop_overrides(table_override: Optional[dict] = None, rate_override: Optional[dict] = None) -> None:
    """
    运行时覆盖掉落表与触发概率。
    传入 None 时会恢复默认值；传入 dict 时按提供数据覆盖。
    结构示例：
      table_override = {
        "easy": [("heal",40), ("x2",28), ...],
        "normal": [...],
        "hard": [...],
        "custom": [...]
      }
      rate_override = {"easy":0.35, "normal":0.30, "hard":0.27, "custom":0.30}
    """
    global DROP_TABLE, DROP_RATE
    if table_override is None:
        DROP_TABLE = {k: v[:] for k, v in DROP_TABLE_DEFAULT.items()}
    else:
        for k, v in table_override.items():
            if isinstance(v, list) and all(isinstance(t, (tuple, list)) and len(t) == 2 for t in v):
                DROP_TABLE[k] = [(str(name), float(weight)) for name, weight in v]  # type: ignore
    if rate_override is None:
        DROP_RATE = DROP_RATE_DEFAULT.copy()
    else:
        for k, v in rate_override.items():
            try:
                DROP_RATE[k] = float(v)
            except Exception:
                continue


def choose_prop_kind(diff: str) -> Optional[str]:
    table = DROP_TABLE.get(diff, DROP_TABLE["normal"])
    if not table:
        return None
    names = [n for n, _ in table]
    weights = [w for _, w in table]
    return random.choices(names, weights=weights, k=1)[0]


def buff_active(buffs: Dict[str, float], name: str) -> bool:
    return buffs.get(name, 0.0) > time.time()


def add_buff(buffs: Dict[str, float], name: str, duration: float) -> None:
    now = time.time()
    buffs[name] = max(buffs.get(name, 0.0), now) + duration


def cleanup_buffs(buffs: Dict[str, float]) -> None:
    now = time.time()
    expired = [k for k, exp in buffs.items() if exp <= now]
    for k in expired:
        buffs.pop(k, None)


class Prop:
    def __init__(self, kind: str, x: int, y: int, ttl: float = 12.0) -> None:
        self.kind = kind
        self.rect = pygame.Rect(x - 16, y - 16, 32, 32)
        self.spawn = time.time()
        self.ttl = ttl
        spec = PROP_SPECS.get(kind, {})
        self.color = spec.get("color", (220, 220, 220))


def active_buff_labels(buffs: Dict[str, float]) -> List[str]:
    now = time.time()
    label_map = {"shield": "护盾", "piercing": "穿透", "spread": "散射", "haste": "连射", "power": "强化", "x2": "双倍得分"}
    labels: List[str] = []
    for key, label in label_map.items():
        end_at = buffs.get(key)
        if end_at and end_at > now:
            remain = int(end_at - now)
            labels.append(f"{label} {remain}s")
    return labels


def wrap_items(items: List[str], per_line: int = 4) -> List[str]:
    if not items:
        return []
    return ["、".join(items[i:i + per_line]) for i in range(0, len(items), per_line)]

