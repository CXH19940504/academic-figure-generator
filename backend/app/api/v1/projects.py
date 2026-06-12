"""Project CRUD endpoints — personal-use (no auth)."""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.document import Document
from app.models.image import Image
from app.models.project import Project, Template
from app.models.prompt import Prompt
from app.schemas.common import MessageResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    TemplateResponse,
)
from app.services.local_storage_service import LocalStorageService

router = APIRouter(prefix="/projects", tags=["Projects"])


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


async def _get_project_by_name(name: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.name == name))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


async def _enrich_response(project: Project, db: AsyncSession) -> ProjectResponse:
    doc_count = (
        await db.execute(
            select(func.count()).select_from(Document).where(Document.project_id == project.id)
        )
    ).scalar_one()
    prompt_count = (
        await db.execute(
            select(func.count()).select_from(Prompt).where(Prompt.project_id == project.id)
        )
    ).scalar_one()
    image_count = (
        await db.execute(
            select(func.count()).select_from(Image).where(Image.project_id == project.id)
        )
    ).scalar_one()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        paper_field=project.paper_field,
        status=project.status,
        document_count=doc_count,
        prompt_count=prompt_count,
        image_count=image_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(name=data.name, description=data.description, paper_field=data.paper_field)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.status != "deleted").order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    enriched = [await _enrich_response(p, db) for p in projects]
    return ProjectListResponse(projects=enriched)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    return await _enrich_response(project, db)


@router.get("/by_name", response_model=ProjectResponse)
async def get_project_by_name(
    name: str = Query(..., description='Project name'),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_name(name, db)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.paper_field is not None:
        project.paper_field = data.paper_field
    await db.commit()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    project.status = "deleted"
    await db.commit()
    return MessageResponse(message="Project deleted successfully")


@router.get("/{project_id}/templates", response_model=list[TemplateResponse])
async def list_project_templates(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    result = await db.execute(select(Template).where(Template.project_id == project_id))
    templates = result.scalars().all()
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("/{project_id}/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_project_template(
    project_id: str,
    name: str = Query(..., description="Template name"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    storage_service = LocalStorageService()
    storage_path = await storage_service.save_uploaded_file(file, "templates")
    template = Template(name=name, project_id=project_id, storage_path=storage_path)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{project_id}/templates/{template_id}", response_model=MessageResponse)
async def delete_project_template(
    project_id: str,
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    result = await db.execute(select(Template).where(Template.id == template_id, Template.project_id == project_id))
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundException("Template not found")
    storage_service = LocalStorageService()
    await storage_service.delete_file(template.storage_path)
    await db.delete(template)
    await db.commit()
    return MessageResponse(message="Template deleted successfully")
