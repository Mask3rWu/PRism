from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentTimingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_name: str
    start_time: datetime
    end_time: datetime | None = None
    model: str | None = None
    latency_ms: int = 0
    status_code: int | None = None
    retry_count: int = 0
    retry_errors: list | None = None


class ReviewStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    run_index: int = 0
    stage: str | None = None
    error_message: str | None = None
    write_comment: bool = True
    writeback_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    agent_timings: list[AgentTimingItem] = []


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    pr_number: int
    pr_title: str
    status: str
    run_index: int = 0
    stage: str | None = None
    error_message: str | None = None
    summary_result: dict | None = None
    coordinator_result: dict | None = None
    risk_result: dict | None = None
    issue_result: dict | None = None
    test_result: dict | None = None
    routing_plan: dict | None = None
    expert_results: list[dict] | None = None
    final_report: dict | None = None
    comment_content: str | None = None
    writeback_error: str | None = None
    write_comment: bool = True
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class ReviewDetailResponse(ReviewResponse):
    agent_timings: list[AgentTimingItem] = []


class ReviewTriggerRequest(BaseModel):
    enabled_agents: list[str] | None = None
    write_comment: bool = True
