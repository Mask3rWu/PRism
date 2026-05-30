from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LabelItem(BaseModel):
    name: str
    color: str


class PullRequestItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pr_number: int
    title: str
    author: str
    created_at: datetime
    updated_at: datetime | None = None
    head_branch: str
    base_branch: str
    review_status: str
    state: str = "open"
    labels: list[LabelItem] = []
    is_draft: bool = False
    merged_at: datetime | None = None


class ReviewStats(BaseModel):
    total: int
    reviewed: int
    not_reviewed: int


class PaginatedPRResponse(BaseModel):
    items: list[PullRequestItem]
    total: int
    page: int
    per_page: int
    review_stats: ReviewStats | None = None
