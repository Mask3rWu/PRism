from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import encrypt_token
from backend.models import AppSettings
from backend.schemas.settings import SettingsResponse, SettingsUpdate
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
    return SettingsResponse(has_pat=bool(s.encrypted_pat))


@router.post("/verify")
async def verify_pat(body: SettingsUpdate):
    is_valid, error = await validate_pat_global(body.pat)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    return {"valid": True}


@router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    is_valid, error = await validate_pat_global(body.pat)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    s = _get_or_create_settings(db)
    s.encrypted_pat = encrypt_token(body.pat)
    db.commit()
    return SettingsResponse(has_pat=True)
