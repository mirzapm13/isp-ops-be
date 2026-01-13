from pydantic import BaseModel
from typing import Optional

class PPPoEConnection(BaseModel):
    ip: str
    uptime: Optional[str]

class PPPoEStatus(BaseModel):
    username: str
    status: str
    router_id: str
    connection: Optional[PPPoEConnection]
