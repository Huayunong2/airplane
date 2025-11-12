import asyncio
import json
import time
import uuid
import secrets
import string
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Any, Optional
from utils.config import load_config
from utils.logger import get_logger
from net.crypto import encode_with_timestamp
from net.protocol import make_envelope
from net.room import Room


logger = get_logger("net.server")
CONFIG = load_config()
WS_HOST = CONFIG["network"]["ws_host"]
WS_PORT = CONFIG["network"]["ws_port"]
TICK_MS = CONFIG["network"]["tick_ms"]
MAX_ROOMS = CONFIG["network"]["max_rooms"]


class Server:
    def __init__(self) -> None:
        self.rooms: Dict[str, Room] = {}
        self.rooms_by_invite: Dict[str, Room] = {}

    def _generate_invite_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if code not in self.rooms_by_invite:
                return code

    def _register_room(self, room: Room, invite_code: Optional[str] = None) -> Room:
        code = invite_code or self._generate_invite_code()
        room.invite_code = code
        self.rooms[room.room_id] = room
        self.rooms_by_invite[code] = room
        return room

    def _remove_room(self, room: Room) -> None:
        self.rooms.pop(room.room_id, None)
        if room.invite_code in self.rooms_by_invite:
            self.rooms_by_invite.pop(room.invite_code, None)

    def _maybe_cleanup_room(self, room: Room) -> None:
        if not room.clients and not room.world.players:
            self._remove_room(room)

    async def tick_broadcast(self) -> None:
        while True:
            await asyncio.sleep(TICK_MS / 1000.0)
            for room in list(self.rooms.values()):
                # step world
                try:
                    room.step(TICK_MS / 1000.0)
                except Exception:
                    pass
                await self._broadcast_room_state(room)

    async def _broadcast_room_state(self, room: Room) -> None:
        if not room.clients:
            self._maybe_cleanup_room(room)
            return
        payload = room.state
        token, ts = encode_with_timestamp(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        env = make_envelope("state", {"token": token}, ts)
        msg = env.to_json()
        stale: list[WebSocketServerProtocol] = []
        for c in list(room.clients):
            try:
                await c.send(msg)
            except Exception as e:
                # 客户端断开或异常，标记为失效，稍后移除，避免服务器崩溃
                logger.debug("drop dead client: %s", e)
                stale.append(c)
        if stale:
            async with room.lock:
                for c in stale:
                    room.clients.discard(c)
                    room.remove_client(c)
            self._maybe_cleanup_room(room)

    async def handler(self, ws: WebSocketServerProtocol, path: str = "") -> None:
        # 从查询参数中获取房间号（invite_code）
        invite_code = None
        create_new = False
        if path:
            # 解析查询参数，例如: /?invite_code=ABC123 或 /?create=true
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(path)
            params = parse_qs(parsed.query)
            if "invite_code" in params:
                invite_code = params["invite_code"][0].upper() if params["invite_code"] else None
            if "create" in params:
                create_new = params["create"][0].lower() == "true"
        
        # 根据房间号查找或创建房间（先从路径参数获取）
        room = await self._find_or_create_room(invite_code, create_new)
        if room is None:
            if invite_code and not create_new:
                await ws.close(code=4001, reason="room not found")
            else:
                await ws.close(code=4002, reason="room unavailable")
            return
        
        async with room.lock:
            if room.is_full():
                await ws.close(code=4000, reason="room full")
                return
            room.clients.add(ws)
            player_id = room.bind_client(ws)
        
        # 发送欢迎消息
        try:
            token, ts = encode_with_timestamp(b"welcome")
            welcome_payload = {"token": token, "room": room.room_id, "player_id": player_id, "invite_code": room.invite_code}
            await ws.send(make_envelope("welcome", welcome_payload, ts).to_json())
        except Exception:
            pass
        
        # 处理消息循环
        try:
            async for raw in ws:
                try:
                    obj = json.loads(raw)
                    # 如果是 join 消息，更新房间号（允许动态加入）
                    if obj.get("t") == "join":
                        d = obj.get("d", {})
                        new_invite_code = d.get("invite_code")
                        if new_invite_code:
                            new_invite_code = new_invite_code.upper()
                            # 如果当前房间号不匹配，尝试切换到新房间
                            if new_invite_code != room.invite_code:
                                new_room = await self._find_or_create_room(new_invite_code, d.get("create", False))
                                if new_room and not new_room.is_full():
                                    old_room = room
                                    async with room.lock:
                                        room.clients.discard(ws)
                                        room.remove_client(ws)
                                    self._maybe_cleanup_room(old_room)
                                    async with new_room.lock:
                                        new_room.clients.add(ws)
                                        player_id = new_room.bind_client(ws)
                                    room = new_room
                                    # 发送新的欢迎消息
                                    try:
                                        token, ts = encode_with_timestamp(b"welcome")
                                        welcome_payload = {"token": token, "room": room.room_id, "player_id": player_id, "invite_code": room.invite_code}
                                        await ws.send(make_envelope("welcome", welcome_payload, ts).to_json())
                                    except Exception:
                                        pass
                        continue
                except Exception:
                    pass
                # 处理其他消息
                await self._on_message(room, ws, raw)
        except websockets.exceptions.ConnectionClosed:
            # 正常关闭连接，不需要记录错误
            pass
        except Exception as e:
            logger.error("ws error: %s", e)
        finally:
            async with room.lock:
                room.clients.discard(ws)
                room.remove_client(ws)
            self._maybe_cleanup_room(room)

    async def _on_message(self, room: Room, ws: WebSocketServerProtocol, raw: str) -> None:
        try:
            obj = json.loads(raw)
            t = obj.get("t")
            d = obj.get("d", {})
            if t == "input":
                pid_client = room.client_to_player_id.get(ws)
                payload = d.get("state", {})
                if pid_client is None:
                    pid_client = room.bind_client(ws, d.get("player_id"))
                room.handle_input(pid_client, payload)
            elif t == "chat":
                msg = d.get("text", "")
                token, ts = encode_with_timestamp(msg.encode("utf-8"))
                env = make_envelope("chat", {"token": token}, ts).to_json()
                await asyncio.gather(*[c.send(env) for c in list(room.clients)])
        except Exception as e:
            logger.error("on_message error: %s", e)

    async def _find_or_create_room(self, invite_code: Optional[str] = None, create_new: bool = False) -> Optional[Room]:
        """
        查找或创建房间：
        - create_new=True 时总是创建新的房间，生成未使用的房间码。
        - create_new=False 时，只有提供有效的房间码才允许加入。
        """
        code = invite_code.upper() if invite_code else None

        # 尝试加入指定房间
        if code and not create_new:
            return self.rooms_by_invite.get(code)

        # 其余情况（明确创建 or 未提供房间号）统一走创建流程
        # 尝试清理空房间，为新房间腾出空间
        for existing in list(self.rooms.values()):
            self._maybe_cleanup_room(existing)
        if len(self.rooms) >= MAX_ROOMS:
            idle_rooms = [room for room in self.rooms.values() if not room.clients]
            if idle_rooms:
                # 释放最早的闲置房间
                self._remove_room(idle_rooms[0])
            if len(self.rooms) >= MAX_ROOMS:
                logger.warning("Max rooms reached, creating new room beyond configured limit")
        room_id = uuid.uuid4().hex[:8]
        room = Room(room_id, f"Room-{room_id}", None, max_players=4)
        room = self._register_room(room)
        logger.info(
            "Created new room: %s (invite_code: %s) [code=%s, create_new=%s]",
            room_id,
            room.invite_code,
            code,
            create_new,
        )
        return room

    async def _ensure_room(self) -> Room:
        # 保留此方法以保持向后兼容
        return await self._find_or_create_room(None, False)


async def main() -> None:
    server = Server()
    broadcast_task = asyncio.create_task(server.tick_broadcast())
    async with websockets.serve(server.handler, WS_HOST, WS_PORT, max_queue=64, ping_interval=10, ping_timeout=20):
        logger.info("WebSocket server started at ws://%s:%s", WS_HOST, WS_PORT)
        await broadcast_task


if __name__ == "__main__":
    asyncio.run(main())

