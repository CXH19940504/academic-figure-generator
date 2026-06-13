"""Project CRUD endpoints — personal-use (no auth)."""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.base import get_project_from_db
from app.dependencies import get_db
from app.models.document import Document
from app.models.image import Image
from app.models.project import Project
from app.models.prompt import Prompt
from app.schemas.common import MessageResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["Projects"])


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
        color_scheme=project.color_scheme,
        custom_colors=project.custom_colors,
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
    return ProjectListResponse(
        items=enriched,
        total=len(enriched),
        page=1,
        page_size=max(len(enriched), 1),
    )


@router.get("/by_name", response_model=ProjectResponse)
async def get_project_by_name_route(
    name: str = Query(..., description='Project name'),
    db: AsyncSession = Depends(get_db),
):
    # 先尝试查找现有项目
    result = await db.execute(
        select(Project).where(Project.name == name, Project.status == "active")
    )
    project: Project | None = result.scalar_one_or_none()

    # 如果不存在，自动创建
    if project is None:
        project = Project(
            name=name,
            description=f"直接创建的{name}",
        )
        db.add(project)
        await db.flush()
        await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_from_db(project_id, db)
    return await _enrich_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_from_db(project_id, db)
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
    project = await get_project_from_db(project_id, db)
    project.status = "deleted"
    await db.commit()
    return MessageResponse(message="Project deleted successfully")
