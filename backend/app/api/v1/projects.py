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
        created_at=project.created_at,
        updated_at=project.updated_at,
        document_count=doc_count,
        prompt_count=prompt_count,
        image_count=image_count,
    )


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        name=data.name,
        description=data.description,
        paper_field=data.paper_field,
        color_scheme=data.color_scheme,
        custom_colors=data.custom_colors,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Project).where(Project.status != "deleted")
    if status is not None:
        base_query = base_query.where(Project.status == status)

    total: int = (await db.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(base_query.order_by(Project.created_at.desc()).offset(offset).limit(page_size))
    ).scalars().all()

    items = [await _enrich_response(p, db) for p in rows]
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    return await _enrich_response(project, db)


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
    if data.color_scheme is not None:
        project.color_scheme = data.color_scheme
    if data.custom_colors is not None:
        project.custom_colors = data.custom_colors
    if data.status is not None:
        project.status = data.status

    db.add(project)
    await db.flush()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    project.status = "deleted"
    db.add(project)
    await db.flush()
    return MessageResponse(message="Project deleted")


# -----------------------------------------------------------------------------
# Template endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/{project_id}/template",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_template(
    project_id: str,
    file: UploadFile = File(...),
    name: str = Query(..., description="Template name"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a DOCX template file and save its content to the database.

    The DOCX file is parsed and the text content is stored in the Template.content field.
    The original file is also saved to local storage.

    Args:
        project_id: The project ID to associate with the template.
        file: The DOCX file to upload.
        name: The template name.
        db: Database session.

    Returns:
        The created Template object.
    """
    # Verify project exists
    await _get_project(project_id, db)

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise ValueError("Only DOCX files are supported for templates")

    # Read file content
    contents = await file.read()
    original_filename = file.filename

    # Save to local storage
    storage = LocalStorageService()
    storage_path = storage.save_upload(f"{project_id}/templates/{original_filename}", contents)

    # Parse DOCX content
    from app.services.document_service import DocumentService  # noqa: PLC0415

    doc_service = DocumentService()
    try:
        parse_result = doc_service.parse(contents, "docx")
        content = parse_result.get("full_text", "")
    except Exception as e:
        # If parsing fails, store empty content but still save the file
        content = ""
        raise ValueError(f"Failed to parse DOCX file: {e}")

    # Create template record
    template = Template(
        project_id=project_id,
        name=name,
        content=content,
        storage_path=storage_path,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    return TemplateResponse(
        id=template.id,
        project_id=template.project_id,
        name=template.name,
        content=template.content,
        storage_path=template.storage_path,
        created_at=template.created_at,
    )


@router.get("/{project_id}/templates", response_model=list[TemplateResponse])
async def list_templates(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all templates for a project.

    Args:
        project_id: The project ID.
        db: Database session.

    Returns:
        List of Template objects.
    """
    # Verify project exists
    await _get_project(project_id, db)

    result = await db.execute(select(Template).where(Template.project_id == project_id))
    templates = result.scalars().all()

    return [
        TemplateResponse(
            id=t.id,
            project_id=project_id,
            name=t.name,
            content=t.content,
            storage_path=t.storage_path,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.delete("/{project_id}/template/{template_id}", response_model=MessageResponse)
async def delete_template(
    project_id: str,
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a template.

    Args:
        project_id: The project ID.
        template_id: The template ID.
        db: Database session.

    Returns:
        Success message.
    """
    # Verify project exists
    await _get_project(project_id, db)

    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if template is None:
        raise NotFoundException("Template not found")

    await db.delete(template)
    await db.flush()

    return MessageResponse(message="Template deleted")
