import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectCreate(BaseModel):
    name: str
    repo_owner: str
    repo_name: str
    description: str = ""
    repo_private: bool = False


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_owner: str
    repo_name: str
    description: str
    tags: list[str]
    is_favorite: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, list):
            return v
        return []


class BatchDeleteRequest(BaseModel):
    ids: list[int]


class PaginatedProjectsResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    per_page: int
