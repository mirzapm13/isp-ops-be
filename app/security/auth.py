# app/security/auth.py

from datetime import datetime, timedelta
from typing import Dict, Any

import jwt
from jwt import PyJWTError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.config.database import SessionLocal
from app.models.user import User
from app.models.role import Role

# =====================================================
# CONFIG
# =====================================================

SECRET_KEY = "dev-secret-change-this"
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# =====================================================
# DB
# =====================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# TOKEN HELPERS
# =====================================================

def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user: User) -> str:
    role_names = [role.name for role in user.roles]

    permissions = list({
        perm.name
        for role in user.roles
        for perm in role.permissions
    })

    return create_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "roles": role_names,
            "permissions": permissions,
            "type": "access"
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: int) -> str:
    return create_token(
        data={
            "sub": str(user_id),
            "type": "refresh"
        },
        expires_delta=timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS)
    )


# =====================================================
# AUTH UTIL
# =====================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(
    db: Session,
    username: str,
    password: str
) -> User | None:

    user = (
        db.query(User)
        .options(
            joinedload(User.roles)
            .joinedload(Role.permissions)
        )
        .filter(User.username == username)
        .first()
    )

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


# =====================================================
# CURRENT USER DEPENDENCY
# =====================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:

    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if decoded.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = decoded.get("sub")

    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (
        db.query(User)
        .options(
            joinedload(User.roles)
            .joinedload(Role.permissions)
        )
        .filter(User.id == int(user_id))
        .first()
    )

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User disabled")

    return user