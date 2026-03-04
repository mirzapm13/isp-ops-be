from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db
from app.security.permissions import require_permission
from app.models.user import User
from app.models.role import Role
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    # dependencies=[Depends(require_permission("manage_users"))]
)


@router.post("/")
def create_user(
    payload: dict,
    db: Session = Depends(get_db)
):
    username = payload.get("username")
    password = payload.get("password")
    role_name = payload.get("role")

    if not username or not password or not role_name:
        raise HTTPException(status_code=400, detail="Missing fields")

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        username=username,
        password_hash=pwd_context.hash(password),
        is_active=True
    )

    user.roles.append(role)

    db.add(user)
    db.commit()

    return {"message": "User created"}