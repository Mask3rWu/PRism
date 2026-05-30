from pydantic import BaseModel


class SettingsResponse(BaseModel):
    has_pat: bool


class SettingsUpdate(BaseModel):
    pat: str
