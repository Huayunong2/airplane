from dataclasses import dataclass, asdict
from typing import Any, Dict, Literal, Optional
import json


ProtocolVersion = "1.0"


@dataclass
class Envelope:
    v: str
    t: str  # type
    d: Dict[str, Any]  # data
    ts: int  # timestamp ms

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


ClientMsgType = Literal["join", "leave", "input", "chat", "ping"]
ServerMsgType = Literal["welcome", "state", "chat", "pong", "error"]


def make_envelope(msg_type: str, data: Dict[str, Any], ts: int) -> Envelope:
    return Envelope(v=ProtocolVersion, t=msg_type, d=data, ts=ts)

