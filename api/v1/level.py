from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from data.dao import dao


router = APIRouter()


class LevelCreate(BaseModel):
    name: str
    difficulty: str
    enemy_waves: List[Dict[str, Any]]


@router.post("")
async def create_level(payload: LevelCreate):
    lid = await dao.create_level(payload.dict())
    return {"code": 1000, "msg": "ok", "level_id": lid}


@router.put("/{lid}/enable")
async def enable_level(lid: int):
    await dao.set_level_enabled(lid, True)
    return {"code": 1000, "msg": "ok"}

