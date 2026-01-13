from pydantic import BaseModel

class Router(BaseModel):
    id: str
    name: str
