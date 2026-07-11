import json

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.agents.routing import DEFAULT_ENABLED_AGENTS, validate_enabled_agents
from backend.core.database import get_db
from backend.core.llm_config import MAX_FREE_REVIEWS, invalidate_llm_cache
from backend.core.security import encrypt_token
from backend.models import ApiCallLog, AppSettings
from backend.schemas.settings import (
    CallLogItem,
    LLMSettingsResponse,
    LLMVerifyRequest,
    PaginatedCallLogs,
    SettingsResponse,
    SettingsUpdate,
)
from backend.services.github.client import validate_pat_global

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_create_settings(db: Session) -> AppSettings:
    s = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if s is None:
        s = AppSettings(id=1, encrypted_pat="")
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    s = _get_or_create_settings(db)
    has_custom_llm = bool(s.encrypted_llm_api_key)
    llm = LLMSettingsResponse(
        provider=s.llm_provider or "pat",
        endpoint=s.llm_endpoint,
        model=s.llm_model,
        has_api_key=has_custom_llm,
    )
    try:
        enabled_agents_list = json.loads(s.enabled_agents or "[]")
    except (json.JSONDecodeError, TypeError):
        enabled_agents_list = DEFAULT_ENABLED_AGENTS
    return SettingsResponse(
        has_pat=bool(s.encrypted_pat),
        llm=llm,
        review_count=s.review_count,
        max_free_reviews=MAX_FREE_REVIEWS,
        agent_language=s.agent_language or "zh",
        enabled_agents=enabled_agents_list,
    )


@router.post("/verify")
async def verify_pat(body: SettingsUpdate):
    if not body.pat:
        raise HTTPException(status_code=400, detail="PAT is required")
    is_valid, error = await validate_pat_global(body.pat)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    return {"valid": True}


@router.post("/verify-llm")
async def verify_llm(body: LLMVerifyRequest):
    """Send a minimal request to verify the LLM API key and endpoint."""
    url = f"{body.endpoint}/chat/completions"
    headers = {
        "Authorization": f"Bearer {body.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": body.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return {"valid": True}
            detail = f"HTTP {resp.status_code}"
            try:
                err = resp.json()
                if "error" in err:
                    detail = str(err["error"].get("message", err["error"]))
            except Exception:
                detail = resp.text[:200] or f"HTTP {resp.status_code}"
            raise HTTPException(status_code=400, detail=detail)
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="Connection timed out — check the endpoint URL")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    s = _get_or_create_settings(db)

    # Update PAT if provided
    if body.pat is not None and body.pat != "":
        is_valid, error = await validate_pat_global(body.pat)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        s.encrypted_pat = encrypt_token(body.pat)

    # Update LLM config if provided
    if body.llm is not None:
        if body.llm.provider is not None:
            s.llm_provider = body.llm.provider
        if body.llm.endpoint is not None:
            s.llm_endpoint = body.llm.endpoint
        if body.llm.model is not None:
            s.llm_model = body.llm.model
        if body.llm.api_key is not None and body.llm.api_key != "":
            s.encrypted_llm_api_key = encrypt_token(body.llm.api_key)
        invalidate_llm_cache()

    # Update agent language
    if body.agent_language is not None:
        s.agent_language = body.agent_language

    # Update enabled agents
    if body.enabled_agents is not None:
        try:
            s.enabled_agents = json.dumps(validate_enabled_agents(body.enabled_agents))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    db.refresh(s)

    has_custom_llm = bool(s.encrypted_llm_api_key)
    llm = LLMSettingsResponse(
        provider=s.llm_provider or "pat",
        endpoint=s.llm_endpoint,
        model=s.llm_model,
        has_api_key=has_custom_llm,
    )
    try:
        enabled_agents_list = json.loads(s.enabled_agents or "[]")
    except (json.JSONDecodeError, TypeError):
        enabled_agents_list = DEFAULT_ENABLED_AGENTS
    return SettingsResponse(
        has_pat=bool(s.encrypted_pat),
        llm=llm,
        review_count=s.review_count,
        max_free_reviews=MAX_FREE_REVIEWS,
        agent_language=s.agent_language or "zh",
        enabled_agents=enabled_agents_list,
    )


@router.post("/clear-pat", response_model=SettingsResponse)
def clear_pat(db: Session = Depends(get_db)):
    """Remove the configured GitHub PAT."""
    s = _get_or_create_settings(db)
    s.encrypted_pat = ""
    db.commit()
    db.refresh(s)

    has_custom_llm = bool(s.encrypted_llm_api_key)
    llm = LLMSettingsResponse(
        provider=s.llm_provider or "pat",
        endpoint=s.llm_endpoint,
        model=s.llm_model,
        has_api_key=has_custom_llm,
    )
    try:
        enabled_agents_list = json.loads(s.enabled_agents or "[]")
    except (json.JSONDecodeError, TypeError):
        enabled_agents_list = DEFAULT_ENABLED_AGENTS
    return SettingsResponse(
        has_pat=False,
        llm=llm,
        review_count=s.review_count,
        max_free_reviews=MAX_FREE_REVIEWS,
        agent_language=s.agent_language or "zh",
        enabled_agents=enabled_agents_list,
    )


@router.post("/clear-llm", response_model=SettingsResponse)
def clear_llm(db: Session = Depends(get_db)):
    """Remove the custom LLM configuration, reverting to free LLM."""
    s = _get_or_create_settings(db)
    s.encrypted_llm_api_key = ""
    s.llm_endpoint = ""
    s.llm_model = ""
    invalidate_llm_cache()
    db.commit()
    db.refresh(s)

    llm = LLMSettingsResponse(
        provider=s.llm_provider or "pat",
        endpoint=s.llm_endpoint,
        model=s.llm_model,
        has_api_key=False,
    )
    try:
        enabled_agents_list = json.loads(s.enabled_agents or "[]")
    except (json.JSONDecodeError, TypeError):
        enabled_agents_list = DEFAULT_ENABLED_AGENTS
    return SettingsResponse(
        has_pat=bool(s.encrypted_pat),
        llm=llm,
        review_count=s.review_count,
        max_free_reviews=MAX_FREE_REVIEWS,
        agent_language=s.agent_language or "zh",
        enabled_agents=enabled_agents_list,
    )


@router.get("/call-logs", response_model=PaginatedCallLogs)
def get_call_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    call_type: str | None = Query(None, pattern="^(llm|github)$"),
    db: Session = Depends(get_db),
):
    query = db.query(ApiCallLog)
    if call_type:
        query = query.filter(ApiCallLog.call_type == call_type)
    total = query.count()
    items = (
        query.order_by(ApiCallLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return PaginatedCallLogs(
        items=[CallLogItem.from_orm(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
    )
