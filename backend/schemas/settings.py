from pydantic import BaseModel


class LLMSettingsResponse(BaseModel):
    provider: str = "pat"
    endpoint: str = ""
    model: str = ""
    has_api_key: bool = False


class SettingsResponse(BaseModel):
    has_pat: bool
    llm: LLMSettingsResponse | None = None
    review_count: int = 0
    max_free_reviews: int = 0
    agent_language: str = "zh"


class LLMSettingsUpdate(BaseModel):
    provider: str | None = None
    endpoint: str | None = None
    model: str | None = None
    api_key: str | None = None


class SettingsUpdate(BaseModel):
    pat: str | None = None
    llm: LLMSettingsUpdate | None = None
    agent_language: str | None = None


class LLMVerifyRequest(BaseModel):
    api_key: str
    endpoint: str
    model: str


class CallLogItem(BaseModel):
    id: int
    call_type: str
    endpoint: str
    model: str | None
    request_summary: str | None
    latency_ms: int
    status_code: int | None
    error_message: str | None
    retry_count: int
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            call_type=obj.call_type,
            endpoint=obj.endpoint,
            model=obj.model,
            request_summary=obj.request_summary,
            latency_ms=obj.latency_ms,
            status_code=obj.status_code,
            error_message=obj.error_message,
            retry_count=obj.retry_count,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
        )


class PaginatedCallLogs(BaseModel):
    items: list[CallLogItem]
    total: int
    page: int
    per_page: int
