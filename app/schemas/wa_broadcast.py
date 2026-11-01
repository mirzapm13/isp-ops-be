from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ButtonConfigSchema(BaseModel):
    index: int = Field(default=0, ge=0, le=9)
    sub_type: Literal["quick_reply", "url"] = "quick_reply"
    column: str = "__NO_VALUE__"


class BroadcastPreviewRequest(BaseModel):
    upload_id: str
    excel_row: int = Field(default=4, ge=1)
    phone_column: str
    namespace: Optional[str] = None
    template_name: str
    language_code: str = "id"
    body_columns: List[str] = Field(default_factory=list)
    header_columns: List[str] = Field(default_factory=list)
    buttons: List[ButtonConfigSchema] = Field(default_factory=list)
    currency_columns: List[str] = Field(default_factory=list)


class BroadcastStartRequest(BaseModel):
    upload_id: str
    phone_column: str
    namespace: Optional[str] = None
    template_name: str
    language_code: str = "id"
    body_columns: List[str] = Field(default_factory=list)
    header_columns: List[str] = Field(default_factory=list)
    buttons: List[ButtonConfigSchema] = Field(default_factory=list)
    currency_columns: List[str] = Field(default_factory=list)
    delay_seconds: float = Field(default=1.0, ge=0.0, le=3600.0)
    dry_run: bool = True
