from pydantic import BaseModel, Field
from typing import Literal, Optional,Annotated

class PPPoEConnection(BaseModel):
    ip: str
    uptime: Optional[str]

class PPPoEStatus(BaseModel):
    username: str
    status: str
    router_id: str
    connection: Optional[PPPoEConnection]


NonEmptyStr = Annotated[str, Field(min_length=1)]

class PPPoESecretCreateRequest(BaseModel):
    name: NonEmptyStr = Field(
        description="PPPoE username / secret name"
    )

    password: NonEmptyStr = Field(
        description="PPPoE password"
    )

    service: Literal["pppoe"] = Field(
        default="pppoe",
        description="Service type"
    )

    profile: str = Field(
        description="PPPoE profile name"
    )

    comment: str = Field(
        default="",
        description="Optional comment"
    )

    disabled: str = Field(
        # default="",
        description="Disable secret on creation"
    )

    router: str = Field(
        description="Target router id or 'all'"
    )

    name: str = Field(
        ...,
        min_length=1,
        description="PPPoE username / secret name"
    )

    password: str = Field(
        ...,
        min_length=1,
        description="PPPoE password"
    )

    service: Literal["pppoe"] = Field(
        "pppoe",
        description="Service type (fixed to pppoe for now)"
    )

    profile: str = Field(
        ...,
        description="PPPoE profile name (fetched from router)"
    )

    comment: str = Field(
        "",
        description="Optional comment"
    )

    disabled: bool = Field(
        False,
        description="Disable secret on creation"
    )

    router: str = Field(
        ...,
        description="Target router id or 'all'"
    )