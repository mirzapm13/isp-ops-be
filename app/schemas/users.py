from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class ChangePasswordRequest(BaseModel):
    new_password: str
