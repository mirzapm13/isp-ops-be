from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.models.base import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles"
    )

    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles"
    )