from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from data.dao import dao


router = APIRouter()


class PropCreate(BaseModel):
    name: str
    type: str  # buff/debuff
    effect: str
    duration: float


class PropDropConfig(BaseModel):
    prop_id: int
    drop_rate: float
    enemy_type: str


@router.post("")
async def create_prop(payload: PropCreate):
    pid = await dao.create_prop(payload.dict())
    return {"code": 1000, "msg": "ok", "prop_id": pid}


@router.post("/drop")
async def set_drop(payload: PropDropConfig):
    await dao.set_prop_drop(payload.dict())
    return {"code": 1000, "msg": "ok"}

