from fastapi import APIRouter
from app.services.router_service import list_routers

router = APIRouter(
    prefix="/routers",
    tags=["Routers"]
)

@router.get("")
def get_routers():
    return list_routers()
