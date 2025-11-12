import json
import os
from typing import Any, Dict


DEFAULT_CONFIG = {
    "window": {"width": 1280, "height": 720, "title": "Python Plane Battle"},
    "fps": 60,
    "network": {"ws_host": "127.0.0.1", "ws_port": 8765, "tick_ms": 20, "max_rooms": 10},
    "api": {"host": "0.0.0.0", "port": 8000, "version": "v1"},
    "security": {"timestamp_skew_ms": 3000},
    "data": {"sqlite_path": "data/game.db", "configs_dir": "data/configs"},
}


def load_config() -> Dict[str, Any]:
    config_path = os.environ.get("GAME_CONFIG", "data/configs/config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            file_conf = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        _deep_merge(merged, file_conf)
        return merged
    return DEFAULT_CONFIG.copy()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v

