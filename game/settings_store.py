import json
import os
from typing import Any, Dict


STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "configs", "settings_store.json")

overrides: Dict[str, Any] = {
    # keys optional: spawn_interval, enemy_cap, fire_interval, burst_max
}

# 运行时设置（默认值，可被持久化覆盖）
runtime_settings: Dict[str, Any] = {
    # 键位方案：wasd / arrows
    "key_scheme": "wasd",
    # 是否静音
    "muted": False,
    # HUD 辅助：显示碰撞盒
    "show_hitbox": False,
    # 全屏（保存到 config.json 时使用）
    "fullscreen": False,
    # 掉落权重覆盖：{"easy":[["heal",40],...], "normal":...}, None 表示沿用默认
    "drop_table": None,
    # 全局掉落触发概率覆盖：{"easy":0.35,"normal":0.30,...}
    "drop_rate": None,
}


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)


def _save_store() -> None:
    try:
        _ensure_dir()
        payload = {
            "overrides": _normalize(overrides),
            "runtime": _normalize(runtime_settings),
        }
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        return


def _load_store() -> None:
    if not os.path.exists(STORE_PATH):
        return
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    loaded_overrides = data.get("overrides")
    if isinstance(loaded_overrides, dict):
        overrides.update({k: v for k, v in loaded_overrides.items() if v is not None})
    loaded_runtime = data.get("runtime")
    if isinstance(loaded_runtime, dict):
        for key, value in loaded_runtime.items():
            if key not in runtime_settings:
                continue
            if key == "drop_rate" and isinstance(value, dict):
                runtime_settings[key] = {k: float(v) for k, v in value.items()}
            elif key == "drop_table" and isinstance(value, dict):
                normalized = {}
                for diff, pairs in value.items():
                    if isinstance(pairs, list):
                        normalized[diff] = [[pair[0], pair[1]] for pair in pairs if isinstance(pair, (list, tuple)) and len(pair) == 2]
                runtime_settings[key] = normalized if normalized else None
            else:
                runtime_settings[key] = value


def set_overrides(new_values: dict) -> None:
    global overrides
    overrides = {k: v for k, v in new_values.items() if v is not None}
    _save_store()


def get_overrides() -> dict:
    return _deep_copy(overrides)


def set_setting(key: str, value):
    normalized = _normalize(value)
    if key == "drop_rate" and isinstance(normalized, dict):
        normalized = {k: float(v) for k, v in normalized.items()}
    runtime_settings[key] = normalized
    _save_store()


def get_setting(key: str, default=None):
    return runtime_settings.get(key, default if default is not None else None)


def get_all_settings() -> dict:
    return _deep_copy(runtime_settings)


_load_store()