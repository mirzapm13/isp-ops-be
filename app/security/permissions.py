from fastapi import Depends, HTTPException, status
from app.security.auth import get_current_user
from app.models.user import User


def require_permission(permission_name: str):
    def permission_dependency(current_user: User = Depends(get_current_user)):

        user_permissions = {
            perm.name
            for role in current_user.roles
            for perm in role.permissions
        }

        if permission_name not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return current_user

    return permission_dependency