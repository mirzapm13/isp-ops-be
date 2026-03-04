from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.models.base import Base

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )