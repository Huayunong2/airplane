from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from data.dao import dao


router = APIRouter()


class CharacterCreate(BaseModel):
    name: str
    speed: float
    hp: int
    damage: int
    img_path: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    speed: Optional[float] = None
    hp: Optional[int] = None
    damage: Optional[int] = None
    img_path: Optional[str] = None


@router.post("")
async def create_character(payload: CharacterCreate):
    cid = await dao.create_character(payload.dict())
    return {"code": 1000, "msg": "ok", "character_id": cid}


@router.get("")
async def list_character():
    items = await dao.list_characters()
    return {"code": 1000, "data": items}


@router.put("/{cid}")
async def update_character(cid: int, payload: CharacterUpdate):
    await dao.update_character(cid, {k: v for k, v in payload.dict().items() if v is not None})
    return {"code": 1000, "msg": "ok"}*** End Patch} -->

