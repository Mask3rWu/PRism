from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PullRequestItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pr_number: int
    title: str
    author: str
    created_at: datetime
    head_branch: str
    base_branch: str
    review_status: str
