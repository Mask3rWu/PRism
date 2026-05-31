import time

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.security import decrypt_token
from backend.models import AppSettings

MAX_FREE_REVIEWS = 15

_cache: dict | None = None
_cache_time: float = 0
_CACHE_TTL = 30


def get_llm_config() -> dict:
    """Return LLM configuration with three-tier priority.

    1. Custom LLM from app_settings (encrypted_llm_api_key non-empty)
    2. Default LLM from .env (fallback, limited to MAX_FREE_REVIEWS)
    3. Raise if neither is available

    Returns:
        {"endpoint": str, "api_key": str, "model": str, "using_default": bool}
    """
    global _cache, _cache_time
    now = time.time()
    if _cache and now - _cache_time < _CACHE_TTL:
        return _cache

    db = SessionLocal()
    try:
        s = db.query(AppSettings).filter(AppSettings.id == 1).first()
        language = s.agent_language if s else "zh"
        if s and s.encrypted_llm_api_key and s.llm_endpoint:
            _cache = {
                "endpoint": s.llm_endpoint,
                "api_key": decrypt_token(s.encrypted_llm_api_key),
                "model": s.llm_model or settings.LLM_MODEL,
                "using_default": False,
                "language": language,
            }
            _cache_time = now
            return _cache
    finally:
        db.close()

    # Tier 2: Free LLM from encrypted config (bundled with repo)
    from backend.core.free_llm import get_free_llm_config

    free = get_free_llm_config()
    if free:
        _cache = {
            "endpoint": free["endpoint"],
            "api_key": free["api_key"],
            "model": free["model"],
            "using_default": True,
            "language": "zh",
        }
        _cache_time = now
        return _cache

    if settings.LLM_ENDPOINT and settings.LLM_API_KEY:
        _cache = {
            "endpoint": settings.LLM_ENDPOINT,
            "api_key": settings.LLM_API_KEY,
            "model": settings.LLM_MODEL,
            "using_default": True,
            "language": "zh",
        }
        _cache_time = now
        return _cache

    raise RuntimeError("No LLM configuration available — configure via Settings or .env")


def invalidate_llm_cache() -> None:
    """Clear the LLM config cache so the next call re-reads from DB."""
    global _cache, _cache_time
    _cache = None
    _cache_time = 0
