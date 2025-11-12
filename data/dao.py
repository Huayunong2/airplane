import aiosqlite
import json
import os
from typing import Any, Dict, List, Optional
from utils.config import load_config
from utils.logger import get_logger


logger = get_logger("data.dao")
CONFIG = load_config()
DB_PATH = CONFIG["data"]["sqlite_path"]
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class DAO:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_lock = False

    async def _ensure_schema(self) -> None:
        if self._init_lock:
            return
        self._init_lock = True
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS character (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, speed REAL, hp INTEGER, damage INTEGER, img_path TEXT, enabled INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS prop (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, type TEXT, effect TEXT, duration REAL
                );
                CREATE TABLE IF NOT EXISTS prop_drop (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prop_id INTEGER, drop_rate REAL, enemy_type TEXT
                );
                CREATE TABLE IF NOT EXISTS level (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, difficulty TEXT, enemy_waves TEXT, enabled INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS battle_mode (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, rule TEXT, max_players INTEGER
                );
                CREATE TABLE IF NOT EXISTS record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT, mode TEXT, time TEXT, score INTEGER, result TEXT
                );
                """
            )
            await db.commit()

    async def create_character(self, data: Dict[str, Any]) -> int:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO character (name, speed, hp, damage, img_path) VALUES (?, ?, ?, ?, ?)",
                (data["name"], data["speed"], data["hp"], data["damage"], data.get("img_path")),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def list_characters(self) -> List[Dict[str, Any]]:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT id, name, speed, hp, damage, img_path, enabled FROM character")
            rows = await cur.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "speed": r[2],
                    "hp": r[3],
                    "damage": r[4],
                    "img_path": r[5],
                    "enabled": bool(r[6]),
                }
                for r in rows
            ]

    async def update_character(self, cid: int, fields: Dict[str, Any]) -> None:
        await self._ensure_schema()
        if not fields:
            return
        keys = ", ".join([f"{k}=?" for k in fields.keys()])
        values = list(fields.values())
        values.append(cid)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE character SET {keys} WHERE id=?", values)
            await db.commit()

    async def create_prop(self, data: Dict[str, Any]) -> int:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO prop (name, type, effect, duration) VALUES (?, ?, ?, ?)",
                (data["name"], data["type"], data["effect"], data["duration"]),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def set_prop_drop(self, data: Dict[str, Any]) -> None:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO prop_drop (prop_id, drop_rate, enemy_type) VALUES (?, ?, ?)",
                (data["prop_id"], data["drop_rate"], data["enemy_type"]),
            )
            await db.commit()

    async def create_level(self, data: Dict[str, Any]) -> int:
        await self._ensure_schema()
        waves = json.dumps(data["enemy_waves"], ensure_ascii=False, separators=(",", ":"))
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO level (name, difficulty, enemy_waves) VALUES (?, ?, ?)",
                (data["name"], data["difficulty"], waves),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def set_level_enabled(self, lid: int, enabled: bool) -> None:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE level SET enabled=? WHERE id=?", (1 if enabled else 0, lid))
            await db.commit()

    async def create_battle_mode(self, data: Dict[str, Any]) -> int:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO battle_mode (name, rule, max_players) VALUES (?, ?, ?)",
                (data["name"], data["rule"], data["max_players"]),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def list_records(self, user_id: Optional[str], mode: Optional[str], start_time: Optional[str]):
        await self._ensure_schema()
        query = "SELECT user_id, mode, time, score, result FROM record WHERE 1=1"
        params: list[Any] = []
        if user_id:
            query += " AND user_id=?"
            params.append(user_id)
        if mode:
            query += " AND mode=?"
            params.append(mode)
        if start_time:
            query += " AND time>=?"
            params.append(start_time)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(query, params)
            rows = await cur.fetchall()
            return [{"user_id": r[0], "mode": r[1], "time": r[2], "score": r[3], "result": r[4]} for r in rows]

    async def insert_record(self, user_id: str, mode: str, time_str: str, score: int, result: str) -> None:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO record (user_id, mode, time, score, result) VALUES (?, ?, ?, ?, ?)",
                (user_id, mode, time_str, score, result),
            )
            await db.commit()

    async def list_recent_records(self, limit: int = 10):
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, mode, time, score, result FROM record ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            return [{"user_id": r[0], "mode": r[1], "time": r[2], "score": r[3], "result": r[4]} for r in rows]

    async def clear_records(self) -> None:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM record")
            await db.commit()


dao = DAO(DB_PATH)

