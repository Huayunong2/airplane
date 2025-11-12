from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, Optional, Set

from utils.config import load_config
from net.world_endless import ClientInput, EndlessWorld


class Room:
    def __init__(self, room_id: str, name: str, password: str | None, max_players: int) -> None:
        self.room_id = room_id
        self.name = name
        self.password = password
        self.max_players = max_players
        self.clients: Set[Any] = set()
        self.lock = asyncio.Lock()

        cfg = load_config()
        width = int(cfg.get("window", {}).get("width", 1280))
        height = int(cfg.get("window", {}).get("height", 720))
        self.world = EndlessWorld(width, height)

        self.state: Dict[str, Any] = {}
        self.client_to_player_id: Dict[Any, str] = {}
        self.invite_code = room_id[:6].upper()
        self.waiting_for_second = True
        self.countdown_until: Optional[float] = None

    # ------------------------------------------------------------------ runtime
    def step(self, dt: float) -> None:
        now = time.time()

        # 确保所有已连接的客户端都在世界中注册
        for pid in list(self.client_to_player_id.values()):
            self.ensure_player(pid)

        player_count = len(self.world.players)

        if player_count == 0:
            self.waiting_for_second = True
            self.countdown_until = None
            self.state = self._compose_state("waiting", None)
            return

        if player_count == 1:
            self.waiting_for_second = True
            self.countdown_until = None
            self.state = self._compose_state("waiting", None)
            return

        if self.waiting_for_second:
            self.waiting_for_second = False
            self.countdown_until = now + 3.0

        if self.countdown_until is not None:
            remain = self.countdown_until - now
            if remain > 0:
                self.state = self._compose_state("countdown", max(0, int(remain) + 1))
                return
            self.countdown_until = None
            # 倒计时结束，开始游戏（设置开始时间）
            if self.world.start_time is None:
                self.world.start_time = now
                self.world.last_step_time = now
                # 通知所有客户端游戏开始
                for player_id in self.world.players.keys():
                    # 通过client_to_player_id找到对应的客户端并发送开始消息
                    pass

        self.world.step(dt)
        self.state = self._compose_state("running", None)

    def _compose_state(self, status: str, countdown: Optional[int]) -> Dict[str, Any]:
        payload = self.world.snapshot()
        payload["status"] = status
        payload["countdown"] = countdown
        payload["invite_code"] = self.invite_code
        payload["players_online"] = len(self.world.players)
        return payload

    # ------------------------------------------------------------------ players
    def ensure_player(self, player_id: str) -> None:
        if player_id not in self.world.players:
            self.world.add_player(player_id)

    def handle_input(self, player_id: str, payload: Dict[str, Any]) -> None:
        move_x = float(payload.get("mx", 0.0))
        move_y = float(payload.get("my", 0.0))
        fire = bool(payload.get("fire", False))
        ts = float(payload.get("ts", time.time()))
        self.ensure_player(player_id)
        self.world.handle_input(player_id, ClientInput(move_x=move_x, move_y=move_y, fire=fire, timestamp=ts))

    def bind_client(self, client: Any, player_id: Optional[str] = None) -> str:
        pid = player_id or uuid.uuid4().hex[:6]
        self.client_to_player_id[client] = pid
        self.ensure_player(pid)
        return pid

    def remove_client(self, client: Any) -> None:
        pid = self.client_to_player_id.pop(client, None)
        if pid:
            self.world.remove_player(pid)

    # ------------------------------------------------------------------ helpers
    def is_full(self) -> bool:
        return len(self.clients) >= self.max_players

