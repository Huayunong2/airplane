import base64
import time
from typing import Tuple


def encode_with_timestamp(payload: bytes) -> Tuple[str, int]:
    ts_ms = int(time.time() * 1000)
    token = base64.b64encode(payload).decode("utf-8")
    return token, ts_ms


def decode_with_timestamp(token: str) -> bytes:
    return base64.b64decode(token.encode("utf-8"))

