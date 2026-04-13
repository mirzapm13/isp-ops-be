from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.security.auth import get_db
from app.security.permissions import require_permission
from app.models.user import User
from app.models.role import Role
from app.schemas.users import CreateUserRequest, ChangePasswordRequest
from app.security.password import hash_password

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    # dependencies=[Depends(require_permission("manage_users"))]
)


@router.post("/")
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db)
):
    role = db.query(Role).filter(Role.name == payload.role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True
    )

    user.roles.append(role)

    db.add(user)
    db.commit()

    return {"message": "User created"}


@router.put("/{user_id}/password")
def change_user_password(
    user_id: int,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    return {"message": "Password updated"}
