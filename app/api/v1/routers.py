from fastapi import APIRouter, Depends
from app.security.auth import get_current_user
from app.services.router_service import list_routers

router = APIRouter(
    prefix="/routers",
    tags=["Routers"],
    dependencies=[Depends(get_current_user)]
)

@router.get("")
def get_routers():
    return list_routers()
