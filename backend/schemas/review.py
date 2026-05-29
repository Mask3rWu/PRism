from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    pr_number: int
    pr_title: str
    status: str
    stage: str | None = None
    error_message: str | None = None
    summary_result: dict | None = None
    risk_result: dict | None = None
    issue_result: dict | None = None
    test_result: dict | None = None
    comment_content: str | None = None
    writeback_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
