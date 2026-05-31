import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ReviewStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_pat: Mapped[str] = mapped_column(Text, nullable=True, default="")
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permission: Mapped[str] = mapped_column(String(32), default="Viewer", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    reviews: Mapped[list["Review"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.queued, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    summary_result: Mapped[dict | None] = mapped_column(JSON, default=None)
    risk_result: Mapped[dict | None] = mapped_column(JSON, default=None)
    issue_result: Mapped[dict | None] = mapped_column(JSON, default=None)
    test_result: Mapped[dict | None] = mapped_column(JSON, default=None)
    diff_content: Mapped[str | None] = mapped_column(Text, default=None)
    comment_content: Mapped[str | None] = mapped_column(Text, default=None)
    writeback_error: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="reviews")
    agent_timings: Mapped[list["AgentTiming"]] = relationship(back_populates="review", cascade="all, delete-orphan")


class AgentTiming(Base):
    __tablename__ = "agent_timings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(Integer, ForeignKey("reviews.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_errors: Mapped[dict | None] = mapped_column(JSON, default=None)

    review: Mapped["Review"] = relationship(back_populates="agent_timings")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    encrypted_pat: Mapped[str] = mapped_column(Text, nullable=False, default="")
    encrypted_llm_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="pat")
    llm_endpoint: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_type: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    request_summary: Mapped[str | None] = mapped_column(Text, default=None)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
