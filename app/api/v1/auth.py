# app/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.auth import LoginRequest
from app.models.user import User
from app.security.auth import (
    get_db,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
)

import jwt
from jwt import PyJWTError
from app.security.auth import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/auth", tags=["Auth"])


# =====================================================
# LOGIN
# =====================================================

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):

    user = authenticate_user(db, payload.username, payload.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password"
        )

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


# =====================================================
# REFRESH
# =====================================================

@router.post("/refresh")
def refresh(payload: dict, db: Session = Depends(get_db)):

    incoming_refresh_token = payload.get("refresh_token")

    if not incoming_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing refresh token"
        )

    try:
        decoded = jwt.decode(
            incoming_refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        if decoded.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = decoded.get("sub")

    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token(user)

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


# =====================================================
# ME
# =====================================================

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):

    permissions = list({
        perm.name
        for role in current_user.roles
        for perm in role.permissions
    })

    return {
        "id": current_user.id,
        "username": current_user.username,
        "roles": [role.name for role in current_user.roles],
        "permissions": permissions
    }

# =====================================================
# LOGOUT
# =====================================================

@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}