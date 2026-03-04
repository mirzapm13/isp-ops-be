from fastapi import Depends, HTTPException
from app.security.auth import get_current_user
from app.models.user import User


def require_permission(permission: str):
    def checker(current_user: User = Depends(get_current_user)):
        permissions = {
            perm.name
            for role in current_user.roles
            for perm in role.permissions
        }

        if permission not in permissions:
            raise HTTPException(status_code=403, detail="Forbidden")

        return current_user

    return checker