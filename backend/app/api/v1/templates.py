"""Global template CRUD endpoints — no project scope."""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.project import Template
from app.schemas.common import MessageResponse
from app.schemas.project import TemplateResponse
from app.services.local_storage_service import LocalStorageService

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Template).order_by(Template.created_at.desc()))
    templates = result.scalars().all()
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    name: str = Query(..., description="Template name"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    storage_service = LocalStorageService()
    content = await file.read()
    filename = file.filename or f"{name}.txt"
    storage_path = storage_service.save_upload(f"templates/{filename}", content)
    template = Template(name=name, storage_path=storage_path)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", response_model=MessageResponse)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Template).where(Template.id == template_id))
    template: Template | None = result.scalar_one_or_none()
    if template is None:
        raise NotFoundException("Template not found")
    storage_service = LocalStorageService()
    if template.storage_path:
        storage_service.delete_file(template.storage_path)
    await db.delete(template)
    await db.commit()
    return MessageResponse(message="Template deleted successfully")
