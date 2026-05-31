from backend.core.database import SessionLocal
from backend.models import ApiCallLog


def log_api_call(
    call_type: str,
    endpoint: str,
    model: str | None = None,
    request_summary: str | None = None,
    latency_ms: int = 0,
    status_code: int | None = None,
    error_message: str | None = None,
    retry_count: int = 0,
) -> None:
    """Record an API call to the database using an independent session."""
    db = SessionLocal()
    try:
        entry = ApiCallLog(
            call_type=call_type,
            endpoint=endpoint,
            model=model,
            request_summary=request_summary,
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message,
            retry_count=retry_count,
        )
        db.add(entry)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
