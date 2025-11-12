from fastapi import APIRouter
from pydantic import BaseModel
from data.dao import dao


router = APIRouter()


class BattleModeCreate(BaseModel):
    name: str
    rule: str
    max_players: int


@router.post("")
async def create_mode(payload: BattleModeCreate):
    mid = await dao.create_battle_mode(payload.dict())
    return {"code": 1000, "msg": "ok", "mode_id": mid}

