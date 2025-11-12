from fastapi import APIRouter
from typing import Optional
from data.dao import dao


router = APIRouter()


@router.get("")
async def list_records(user_id: Optional[str] = None, mode: Optional[str] = None, start_time: Optional[str] = None):
    items = await dao.list_records(user_id=user_id, mode=mode, start_time=start_time)
    return {"code": 1000, "data": items}

