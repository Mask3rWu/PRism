from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import encrypt_token
from backend.models import Project
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from backend.services.github.client import validate_pat

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    is_valid, error = await validate_pat(body.repo_owner, body.repo_name, body.pat)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    encrypted_pat = encrypt_token(body.pat)
    project = Project(
        name=body.name,
        repo_owner=body.repo_owner,
        repo_name=body.repo_name,
        encrypted_pat=encrypted_pat,
        description=body.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.pat is not None:
        is_valid, error = await validate_pat(project.repo_owner, project.repo_name, body.pat)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        project.encrypted_pat = encrypt_token(body.pat)

    if body.description is not None:
        project.description = body.description

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return None
