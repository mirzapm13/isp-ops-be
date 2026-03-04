from fastapi import APIRouter, Depends
from app.security.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/test", tags=["Test"], dependencies=[Depends(get_current_user)])


@router.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username
    }