from fastapi import FastAPI
from fastapi.responses import JSONResponse
from utils.config import load_config
from api.v1 import character, prop, level, battle_mode, record


config = load_config()
app = FastAPI(title="Plane Battle API", version=config["api"]["version"])


@app.get("/health")
def health():
    return {"code": 1000, "msg": "ok"}


app.include_router(character.router, prefix="/api/v1/character", tags=["character"])
app.include_router(prop.router, prefix="/api/v1/prop", tags=["prop"])
app.include_router(level.router, prefix="/api/v1/level", tags=["level"])
app.include_router(battle_mode.router, prefix="/api/v1/battle-mode", tags=["battle-mode"])
app.include_router(record.router, prefix="/api/v1/record", tags=["record"])*** End Patch```} -->

