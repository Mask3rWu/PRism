from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    repo_owner: str
    repo_name: str
    pat: str
    description: str = ""


class ProjectUpdate(BaseModel):
    description: str | None = None
    pat: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_owner: str
    repo_name: str
    description: str
    created_at: datetime
    updated_at: datetime
